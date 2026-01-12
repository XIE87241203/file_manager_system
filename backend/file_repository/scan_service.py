import os
from concurrent.futures import as_completed
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
        用途说明：扫描任务调度核心逻辑。
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

            # 第一阶段：文件发现 (改为数据库实时校验，不加载全量路径到内存)
            new_file_list: List[str] = ScanService._phase_discovery(scan_mode, current_scan_time)
            if ScanService._progress_manager.is_stopped():
                ScanService._handle_stopped()
                return

            # 第二阶段：特征提取
            processed_count: int = ScanService._phase_extraction(new_file_list, current_scan_time)
            if ScanService._progress_manager.is_stopped():
                ScanService._handle_stopped()
                return

            # 第三阶段：清理失效索引与备份
            deleted_count: int = ScanService._phase_cleanup(current_scan_time)

            # 完成
            ScanService._progress_manager.set_status(ProgressStatus.COMPLETED)
            msg: str = f"扫描任务完成。新增: {processed_count}, 清理失效: {deleted_count}"
            ScanService._progress_manager.update_progress(message=msg)
            LogUtils.info(msg)

        except Exception as e:
            LogUtils.error(f"扫描服务运行异常: {e}")
            ScanService._progress_manager.set_status(ProgressStatus.ERROR)
            ScanService._progress_manager.update_progress(message=f"内部异常: {str(e)}")

    @staticmethod
    def _phase_discovery(scan_mode: ScanMode, current_scan_time: str) -> List[str]:
        """
        用途说明：第一阶段 - 文件发现。遍历配置目录，识别新增文件，并更新已有文件的扫描时间。
        策略说明：通过逐一查询数据库检查路径是否存在，避免全量加载路径导致内存溢出。
        入参说明：
            scan_mode (ScanMode): 扫描模式。
            current_scan_time (str): 本次扫描的时间戳。
        返回值说明：
            List[str]: 发现的新增文件路径列表。
        """
        LogUtils.info("进入第一阶段：文件发现...")
        ScanService._progress_manager.update_progress(message="正在扫描文件目录...")
        
        repo_config = settingService.get_config().file_repository
        directories: List[str] = repo_config.directories
        suffixes: List[str] = [s.replace('.', '').lower() for s in repo_config.scan_suffixes]
        scan_all: bool = "*" in suffixes
        
        new_file_list: List[str] = []
        paths_to_update_time: List[str] = []
        
        for repo_path in directories:
            if ScanService._progress_manager.is_stopped(): break
            if not os.path.exists(repo_path):
                LogUtils.error(f"扫描路径不存在: {repo_path}")
                continue
            
            for root, _, files in os.walk(repo_path):
                if ScanService._progress_manager.is_stopped(): break
                for file in files:
                    full_path: str = os.path.join(root, file)
                    
                    if Utils.should_ignore(full_path, 
                                           repo_config.ignore_filenames, 
                                           repo_config.ignore_paths, 
                                           repo_config.ignore_filenames_case_insensitive, 
                                           repo_config.ignore_paths_case_insensitive):
                        continue

                    file_ext: str = os.path.splitext(file)[1].replace('.', '').lower()
                    if scan_all or file_ext in suffixes:
                        # 全量扫描模式下，所有发现的文件都是“新增”的（因为索引已在初始化阶段清空）
                        # 增量扫描模式下，需要逐一检查数据库
                        is_existing = False
                        if scan_mode == ScanMode.INDEX_SCAN:
                            is_existing = DBOperations.check_file_path_exists(full_path)
                        
                        if is_existing:
                            paths_to_update_time.append(full_path)
                            if len(paths_to_update_time) >= 500:
                                DBOperations.batch_update_files_scan_time(paths_to_update_time, current_scan_time)
                                paths_to_update_time = []
                        else:
                            new_file_list.append(full_path)

        if paths_to_update_time and not ScanService._progress_manager.is_stopped():
            DBOperations.batch_update_files_scan_time(paths_to_update_time, current_scan_time)
            
        return new_file_list

    @staticmethod
    def _phase_extraction(new_file_list: List[str], current_scan_time: str) -> int:
        """
        用途说明：第二阶段 - 特征提取。对新增文件并行计算 MD5，并分批写入数据库。
        入参说明：
            new_file_list (List[str]): 发现的新增文件路径列表。
            current_scan_time (str): 本次扫描的时间戳。
        返回值说明：
            int: 成功入库的新增文件数量。
        """
        total_new_count: int = len(new_file_list)
        if total_new_count == 0:
            return 0
            
        LogUtils.info(f"进入第二阶段：特征提取 (总计 {total_new_count} 个文件)...")
        ScanService._progress_manager.update_progress(total=total_new_count, message="开始提取新增文件特征...")
        
        all_files_info: List[FileIndexDBModel] = []
        processed_count: int = 0
        batch_size: int = 1000
        
        for i in range(0, total_new_count, batch_size):
            if ScanService._progress_manager.is_stopped(): break
                
            batch_paths: List[str] = new_file_list[i : i + batch_size]
            futures = [ThreadPoolManager.submit(Utils.calculate_md5, path) for path in batch_paths]
            
            for future in as_completed(futures):
                if ScanService._progress_manager.is_stopped(): break
                try:
                    f_path, f_md5 = future.result()
                    if f_md5:
                        f_size: int = os.path.getsize(f_path)
                        all_files_info.append(
                            FileIndexDBModel(
                                file_path=f_path, 
                                file_md5=f_md5,
                                file_size=f_size,
                                scan_time=current_scan_time
                            )
                        )
                except Exception as e:
                    LogUtils.error(f"MD5 计算任务异常: {e}")

                processed_count += 1
                if len(all_files_info) >= 100:
                    DBOperations.batch_insert_files_index(all_files_info)
                    all_files_info = []
                
                if processed_count % 50 == 0 or processed_count == total_new_count:
                    ScanService._progress_manager.update_progress(current=processed_count, message="正在建立新增文件索引")

        if all_files_info and not ScanService._progress_manager.is_stopped():
            DBOperations.batch_insert_files_index(all_files_info)
            
        return processed_count

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
