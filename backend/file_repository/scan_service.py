import os
from concurrent.futures import as_completed, Future
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any

from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressManager, ProgressStatus
from backend.common.thread_pool import ThreadPoolManager
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.file_service import FileService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.setting.setting_service import settingService


class ScanMode(Enum):
    """
    用途：定义扫描模式
    """
    FULL_SCAN: str = "full_scan"  # 全量扫描模式
    INDEX_SCAN: str = "index_scan"  # 增量索引模式


class ScanService:
    """
    用途：文件仓库扫描服务类，支持全量与增量索引逻辑，利用全局线程池进行异步扫描。
    """

    _progress_manager: ProgressManager = ProgressManager()

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """
        用途说明：以线程安全的方式获取当前扫描状态和进度信息。
        入参说明：无
        返回值说明：Dict[str, Any] - 包含 status (str) 和 progress (dict) 的字典。
        """
        return ScanService._progress_manager.get_status()

    @staticmethod
    def stop_scan() -> None:
        """
        用途说明：请求停止当前正在进行的扫描任务。
        入参说明：无
        返回值说明：无
        """
        if ScanService._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            ScanService._progress_manager.set_stop_flag(True)
            LogUtils.info("用户请求停止扫描任务，已设置停止标志位")

    @staticmethod
    def start_async_scan(scan_mode: ScanMode = ScanMode.INDEX_SCAN) -> bool:
        """
        用途说明：通过全局线程池启动异步扫描任务。
        入参说明：
            scan_mode (ScanMode): 扫描模式，可选 FULL_SCAN 或 INDEX_SCAN，默认为 INDEX_SCAN。
        返回值说明：bool - 如果成功启动返回 True，如果任务已在运行则返回 False。
        """
        if ScanService._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            LogUtils.error("扫描任务已在运行中，忽略此次请求")
            return False

        ScanService._progress_manager.set_status(ProgressStatus.PROCESSING)
        ScanService._progress_manager.set_stop_flag(False)
        ScanService._progress_manager.reset_progress(message="正在初始化...")

        ThreadPoolManager.submit(ScanService._internal_scan, scan_mode)
        LogUtils.info(f"异步扫描任务已提交，模式为: {scan_mode.value}")
        return True

    @staticmethod
    def _internal_scan(scan_mode: ScanMode) -> None:
        """
        用途说明：扫描任务调度核心逻辑。已优化为单次遍历完成发现与提取。
        入参说明：
            scan_mode (ScanMode): 扫描模式。
        返回值说明：无
        """
        try:
            # 初始化：获取本次扫描的时间戳
            current_scan_time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if scan_mode == ScanMode.FULL_SCAN:
                LogUtils.info("全量扫描模式：清空现有索引...")
                FileService.clear_repository(False)
            else:
                LogUtils.info("增量扫描模式：开始文件扫描...")

            # 执行合并后的扫描与特征提取阶段
            new_count, updated_count = ScanService._combined_scan_logic(scan_mode, current_scan_time)
            
            if ScanService._progress_manager.is_stopped():
                ScanService._handle_stopped()
                return

            # 第三阶段：清理失效索引与备份
            deleted_count: int = ScanService._phase_cleanup(current_scan_time)

            # 完成
            ScanService._progress_manager.set_status(ProgressStatus.COMPLETED)
            msg: str = f"扫描任务完成。新增: {new_count}, 更新: {updated_count}, 清理失效: {deleted_count}"
            ScanService._progress_manager.update_progress(message=msg)
            LogUtils.info(msg)

        except Exception as e:
            LogUtils.error(f"扫描服务运行异常: {e}")
            ScanService._progress_manager.set_status(ProgressStatus.ERROR)
            ScanService._progress_manager.update_progress(message=f"内部异常: {str(e)}")

    @staticmethod
    def _combined_scan_logic(scan_mode: ScanMode, current_scan_time: str) -> (int, int):
        """
        用途说明：合并阶段 - 在一次目录遍历中完成文件发现、存在校验与特征提取。
        入参说明：
            scan_mode (ScanMode): 扫描模式。
            current_scan_time (str): 本次扫描的时间戳。
        返回值说明：
            (int, int): (新增文件数, 更新扫描时间的文件数)
        """
        LogUtils.info("进入综合扫描阶段...")
        ScanService._progress_manager.update_progress(message="正在遍历目录并提取特征...")

        repo_config = settingService.get_config().file_repository
        directories: List[str] = repo_config.directories
        suffixes: List[str] = [s.replace('.', '').lower() for s in repo_config.scan_suffixes]
        scan_all: bool = "*" in suffixes

        new_count: int = 0
        updated_count: int = 0
        
        # 用于分批更新扫描时间的列表
        paths_to_update_time: List[str] = []
        # 用于并发处理计算MD5的任务列表
        md5_futures: List[Future] = []
        # 用于待入库的对象列表
        all_files_info: List[FileIndexDBModel] = []

        batch_update_size: int = 500
        batch_insert_size: int = 100
        max_concurrent_tasks: int = 20 # 限制并发计算MD5的数量，避免IO压力过大

        for repo_path in directories:
            if ScanService._progress_manager.is_stopped(): break
            if not os.path.exists(repo_path):
                LogUtils.error(f"扫描路径不存在: {repo_path}")
                continue

            for root, _, files in os.walk(repo_path):
                if ScanService._progress_manager.is_stopped(): break
                for file in files:
                    if ScanService._progress_manager.is_stopped(): break
                    
                    full_path: str = os.path.join(root, file)
                    if Utils.should_ignore(full_path, 
                                           repo_config.ignore_filenames, 
                                           repo_config.ignore_paths, 
                                           repo_config.ignore_filenames_case_insensitive, 
                                           repo_config.ignore_paths_case_insensitive):
                        continue

                    file_ext: str = os.path.splitext(file)[1].replace('.', '').lower()
                    if scan_all or file_ext in suffixes:
                        # 检查数据库中是否存在
                        is_existing: bool = False
                        if scan_mode == ScanMode.INDEX_SCAN:
                            is_existing = DBOperations.check_file_path_exists(full_path)
                        
                        if is_existing:
                            paths_to_update_time.append(full_path)
                            updated_count += 1
                            if len(paths_to_update_time) >= batch_update_size:
                                DBOperations.batch_update_files_scan_time(paths_to_update_time, current_scan_time)
                                paths_to_update_time = []
                        else:
                            # 新文件，提交MD5计算任务
                            md5_futures.append(ThreadPoolManager.submit(Utils.calculate_fast_md5, full_path))
                            
                            # 当并发任务积累到一定量或遍历结束，处理结果
                            if len(md5_futures) >= max_concurrent_tasks:
                                new_count += ScanService._process_md5_futures(md5_futures, all_files_info, current_scan_time, batch_insert_size)
                                md5_futures = []

                        # 定期更新进度条（仅显示已扫描的数量感官上更连贯）
                        if (new_count + updated_count) % 100 == 0:
                            ScanService._progress_manager.update_progress(
                                message=f"已扫描: {new_count + updated_count} (新增: {new_count})"
                            )

        # 处理剩余的更新
        if paths_to_update_time and not ScanService._progress_manager.is_stopped():
            DBOperations.batch_update_files_scan_time(paths_to_update_time, current_scan_time)
        
        # 处理剩余的MD5计算任务
        if md5_futures and not ScanService._progress_manager.is_stopped():
            new_count += ScanService._process_md5_futures(md5_futures, all_files_info, current_scan_time, batch_insert_size)
        
        # 处理最后剩余的入库对象
        if all_files_info and not ScanService._progress_manager.is_stopped():
            DBOperations.batch_insert_files_index(all_files_info)

        return new_count, updated_count

    @staticmethod
    def _process_md5_futures(futures: List[Future], info_list: List[FileIndexDBModel], 
                             current_scan_time: str, batch_size: int) -> int:
        """
        用途说明：内部辅助方法，处理已完成的MD5计算任务并准备入库。
        入参说明：
            futures (List[Future]): 线程池返回的任务列表。
            info_list (List[FileIndexDBModel]): 外部维护的待入库对象列表。
            current_scan_time (str): 本次扫描时间戳。
            batch_size (int): 分批入库的阈值。
        返回值说明：
            int: 本次处理成功的文件数量。
        """
        success_count: int = 0
        for future in as_completed(futures):
            if ScanService._progress_manager.is_stopped(): break
            try:
                f_path, f_md5 = future.result()
                if f_md5:
                    f_size: int = os.path.getsize(f_path)
                    info_list.append(
                        FileIndexDBModel(
                            file_path=f_path, 
                            file_md5=f_md5,
                            file_size=f_size,
                            scan_time=current_scan_time
                        )
                    )
                    success_count += 1
            except Exception as e:
                LogUtils.error(f"MD5 计算任务异常: {e}")

            if len(info_list) >= batch_size:
                DBOperations.batch_insert_files_index(info_list)
                info_list.clear()
        
        return success_count

    @staticmethod
    def _phase_cleanup(current_scan_time: str) -> int:
        """
        用途说明：第三阶段 - 清理与收尾。删除失效记录，并将结果备份至历史表。
        入参说明：
            current_scan_time (str): 本次有效扫描的时间戳。
        返回值说明：
            int: 已删除的失效索引记录数。
        """
        LogUtils.info("进入第三阶段：清理失效索引...")
        ScanService._progress_manager.update_progress(message="正在清理失效索引并备份...")
        
        # 删除扫描时间不匹配的记录（即磁盘上已不存在的文件）
        deleted_count: int = DBOperations.delete_files_by_not_scan_time(current_scan_time)
        
        # 同步当前索引至历史表
        DBOperations.copy_file_index_to_history()
        
        return deleted_count

    @staticmethod
    def _handle_stopped() -> None:
        """
        用途说明：处理任务被手动停止时的清理工作。
        入参说明：无
        返回值说明：无
        """
        ScanService._progress_manager.set_status(ProgressStatus.IDLE)
        ScanService._progress_manager.set_stop_flag(False)
        ScanService._progress_manager.update_progress(message="任务已手动停止")
        LogUtils.info("扫描任务已响应停止指令，重置为待机状态")
