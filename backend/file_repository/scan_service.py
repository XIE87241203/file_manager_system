import os
from typing import List, Dict, Any, Optional
from concurrent.futures import as_completed

from backend.db.model.file_index import FileIndex
from backend.setting.setting import settings
from backend.db.db_operations import DBOperations
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.common.thread_pool import ThreadPoolManager
from backend.common.progress_manager import ProgressManager, ProgressInfo, ProgressStatus
from backend.file_repository.thumbnail.thumbnail_service import ThumbnailService


class ScanService:
    """
    用途：文件仓库扫描服务类，支持利用全局线程池进行异步扫描、进度查询和任务控制
    """

    _progress_manager: ProgressManager = ProgressManager() # New ProgressManager instance

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """
        用途：以线程安全的方式获取当前扫描状态和进度信息
        入参说明：无
        返回值说明：Dict[str, Any] - 包含 status (str) 和 progress (dict) 的字典
        """
        return ScanService._progress_manager.get_status()

    @staticmethod
    def stop_scan() -> None:
        """
        用途：请求停止当前正在进行的扫描任务
        入参说明：无
        返回值说明：无
        """
        if ScanService._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            ScanService._progress_manager.set_stop_flag(True)
            LogUtils.info("用户请求停止扫描任务，已设置停止标志位")

    @staticmethod
    def start_async_scan() -> bool:
        """
        用途：通过全局线程池启动异步扫描任务
        入参说明：无
        返回值说明：bool - 如果成功启动返回 True，如果任务已在运行则返回 False
        """
        if ScanService._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            LogUtils.error("扫描任务已在运行中，忽略此次请求")
            return False

        # 初始化扫描状态和进度
        ScanService._progress_manager.set_status(ProgressStatus.PROCESSING)
        ScanService._progress_manager.set_stop_flag(False)
        ScanService._progress_manager.reset_progress(message="正在初始化...")

        # 使用全局共享线程池提交任务
        ThreadPoolManager.submit(ScanService._internal_scan)
        LogUtils.info(f"异步扫描任务已提交至全局线程池")
        return True

    @staticmethod
    def _internal_scan() -> None:
        """
        用途：后台扫描核心逻辑，包含文件发现、利用线程池并行计算 MD5 及批量入库
        入参说明：无
        返回值说明：无
        """
        try:

            repo_config = settings.file_repository
            directories = repo_config.get("directories", [])
            suffixes = repo_config.get("scan_suffixes", ["*"])
            suffixes = [s.replace('.', '').lower() for s in suffixes]
            scan_all = "*" in suffixes
            
            ignore_filenames = repo_config.get("ignore_filenames", [])
            ignore_paths = repo_config.get("ignore_paths", [])
            ignore_filenames_case_insensitive = repo_config.get("ignore_filenames_case_insensitive", True)
            ignore_paths_case_insensitive = repo_config.get("ignore_paths_case_insensitive", True)

            # --- 第一阶段：文件发现 (File Discovery) ---
            LogUtils.info("第一阶段：开始发现文件并统计总数...")
            temp_file_list: List[str] = []
            for repo_path in directories:
                if ScanService._progress_manager.is_stopped(): return
                if not os.path.exists(repo_path):
                    LogUtils.error(f"配置的扫描路径不存在: {repo_path}")
                    continue
                
                for root, _, files in os.walk(repo_path):
                    if ScanService._progress_manager.is_stopped(): break
                    for file in files:
                        full_path = os.path.join(root, file)
                        
                        # 检查是否在忽略列表中
                        if Utils.should_ignore(full_path, 
                                               ignore_filenames, 
                                               ignore_paths, 
                                               ignore_filenames_case_insensitive, 
                                               ignore_paths_case_insensitive):
                            continue

                        file_ext = os.path.splitext(file)[1].replace('.', '').lower()
                        if scan_all or file_ext in suffixes:
                            temp_file_list.append(full_path)

            total_count = len(temp_file_list)
            LogUtils.info(f"文件发现完成，共计 {total_count} 个文件待处理")
            ScanService._progress_manager.update_progress(total=total_count, message="开始提取文件特征...")

            # --- 第二阶段：分批并行特征提取与入库 (Parallel Processing) ---
            all_files_info: List[FileIndex] = []
            processed_count = 0
            
            # 修复点 5：分批提交任务到线程池，避免在大仓库下内存中堆积过多的 Future 对象
            batch_size = 1000
            for i in range(0, total_count, batch_size):
                if ScanService._progress_manager.is_stopped(): 
                    break
                    
                batch_paths = temp_file_list[i : i + batch_size]
                futures = [ThreadPoolManager.submit(Utils.calculate_md5, path) for path in batch_paths]
                
                for future in as_completed(futures):
                    if ScanService._progress_manager.is_stopped(): 
                        break
                    
                    try:
                        f_path, f_md5 = future.result()
                        if f_md5:
                            all_files_info.append(
                                FileIndex(
                                    file_path=f_path, 
                                    file_name=os.path.basename(f_path), 
                                    file_md5=f_md5
                                )
                            )
                    except Exception as e:
                        LogUtils.error(f"处理任务执行异常: {e}")

                    processed_count += 1
                    
                    # 批量写入数据库（每 100 条）以平衡 IO 性能
                    if len(all_files_info) >= 100:
                        DBOperations.batch_insert_files(all_files_info)
                        all_files_info = []
                    
                    # 定期更新进度
                    if processed_count % 50 == 0 or processed_count == total_count:
                        ScanService._progress_manager.update_progress(current=processed_count, message="正在建立索引")

            # 写入剩余数据
            if all_files_info and not ScanService._progress_manager.is_stopped():
                DBOperations.batch_insert_files(all_files_info)

            # --- 第三阶段：收尾工作 ---
            if ScanService._progress_manager.is_stopped():
                ScanService._handle_stopped()
            else:
                LogUtils.info("所有文件处理完成，正在同步至历史表...")
                if DBOperations.copy_to_history():
                    ScanService._progress_manager.set_status(ProgressStatus.COMPLETED)
                    ScanService._progress_manager.update_progress(message=f"扫描任务正常完成，共索引 {processed_count} 个文件")
                    LogUtils.info(f"扫描任务正常完成，共索引 {processed_count} 个文件")
                else:
                    ScanService._progress_manager.set_status(ProgressStatus.ERROR)
                    ScanService._progress_manager.update_progress(message="备份至历史表失败")

        except Exception as e:
            LogUtils.error(f"扫描服务运行异常: {e}")
            ScanService._progress_manager.set_status(ProgressStatus.ERROR)
            ScanService._progress_manager.update_progress(message=f"内部异常: {str(e)}")

    @staticmethod
    def _handle_stopped() -> None:
        """
        用途：处理任务中途停止时的状态清理。
        入参说明：无
        返回值说明：无
        """
        ScanService._progress_manager.set_status(ProgressStatus.IDLE)
        ScanService._progress_manager.set_stop_flag(False)
        ScanService._progress_manager.update_progress(message="任务已手动停止")
        LogUtils.info("扫描任务已清理并重置为待机状态")
