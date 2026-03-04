import os
from concurrent.futures import as_completed, Future
from datetime import datetime
from enum import Enum
from typing import List, Tuple, Optional

from backend.common.base_async_service import BaseAsyncService
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.common.thread_pool import ThreadPoolManager
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.file_service import FileService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.setting.setting_models import FileRepositorySettings
from backend.setting.setting_service import settingService


class ScanMode(Enum):
    """
    用途：定义扫描模式
    """
    FULL_SCAN = "full_scan"  # 全量扫描模式
    INDEX_SCAN = "index_scan"  # 增量索引模式


class ScanService(BaseAsyncService):
    """
    用途：文件仓库扫描服务类，支持全量与增量索引逻辑，利用全局线程池进行异步扫描。
    """

    @classmethod
    def start_scan_task(cls, scan_mode: ScanMode = ScanMode.INDEX_SCAN) -> bool:
        """
        用途说明：启动异步扫描任务。包含初始化逻辑与线程池提交。
        入参说明：
            scan_mode (ScanMode): 扫描模式。
        返回值说明：bool - 是否成功启动。
        """
        try:
            # --- 初始化逻辑开始 ---
            if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
                LogUtils.error(t('repo_scan_running'))
                raise RuntimeError(t('repo_scan_running'))

            mode: ScanMode = scan_mode if isinstance(scan_mode, ScanMode) else ScanMode.INDEX_SCAN
            
            # 获取配置快照
            repo_config: FileRepositorySettings = settingService.get_config().file_repository

            # 重置进度状态
            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            cls._progress_manager.reset_progress(message=t('repo_scan_initializing'))
            # --- 初始化逻辑结束 ---
            
            # 调用基类的私有方法启动任务
            return cls._start_task(cls._internal_scan, mode, repo_config)
        except Exception as e:
            LogUtils.error(t('repo_scan_start_failed', error=str(e)))
            return False

    @classmethod
    def _internal_scan(cls, scan_mode: ScanMode, repo_config: FileRepositorySettings) -> None:
        """
        用途说明：扫描任务调度核心逻辑。
        """
        try:
            # 初始化：获取本次扫描的时间戳
            current_scan_time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if scan_mode == ScanMode.FULL_SCAN:
                LogUtils.info(t('repo_scan_full_mode'))
                FileService.clear_repository(False)
            else:
                LogUtils.info(t('repo_scan_incremental_mode'))

            # 执行合并后的扫描与特征提取阶段
            new_count, updated_count = cls._combined_scan_logic(scan_mode, current_scan_time, repo_config)
            
            if cls._progress_manager.is_stopped():
                cls._handle_stopped()
                return

            # 第三阶段：清理失效索引与备份
            deleted_count: int = cls._phase_cleanup(current_scan_time)

            # 扫描完成后自动重新计算文件仓库统计详情
            FileService.calculate_repo_detail()

            # 完成
            cls._progress_manager.set_status(ProgressStatus.COMPLETED)
            msg: str = t('repo_scan_completed', new_count=new_count, updated_count=updated_count, deleted_count=deleted_count)
            cls._progress_manager.update_progress(message=msg)
            LogUtils.info(msg)

        except Exception as e:
            LogUtils.error(t('repo_scan_error', error=str(e)))
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=t('internal_error', error=str(e)))

    @classmethod
    def _combined_scan_logic(cls, scan_mode: ScanMode, current_scan_time: str, repo_config: FileRepositorySettings) -> Tuple[int, int]:
        """
        用途说明：合并阶段 - 在一次目录遍历中完成文件发现、存在校验与特征提取。
        """
        LogUtils.info(t('repo_scan_phase_combined'))
        cls._progress_manager.update_progress(message=t('repo_scan_traversing'))

        directories: List[str] = repo_config.directories
        suffixes: List[str] = [s.replace('.', '').lower() for s in repo_config.scan_suffixes]
        scan_all: bool = "*" in suffixes

        new_count: int = 0
        updated_count: int = 0
        
        paths_to_update_time: List[str] = []
        info_futures: List[Future] = []
        all_files_info: List[FileIndexDBModel] = []

        batch_update_size: int = 500
        batch_insert_size: int = 100
        max_concurrent_tasks: int = 20

        for repo_path in directories:
            if cls._progress_manager.is_stopped(): break
            if not os.path.exists(repo_path):
                LogUtils.error(t('repo_scan_path_not_found', path=repo_path))
                continue

            for root, _, files in os.walk(repo_path):
                if cls._progress_manager.is_stopped(): break
                for file in files:
                    if cls._progress_manager.is_stopped(): break
                    
                    full_path: str = os.path.join(root, file)
                    if Utils.should_ignore(full_path, 
                                           repo_config.ignore_filenames, 
                                           repo_config.ignore_paths, 
                                           repo_config.ignore_filenames_case_insensitive, 
                                           repo_config.ignore_paths_case_insensitive):
                        continue

                    file_ext: str = os.path.splitext(file)[1].replace('.', '').lower()
                    if scan_all or file_ext in suffixes:
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
                            # 修改点：改调用 getFileInfo
                            info_futures.append(ThreadPoolManager.submit(Utils.get_file_info, full_path))
                            
                            if len(info_futures) >= max_concurrent_tasks:
                                new_count += cls._process_info_futures(info_futures, all_files_info, current_scan_time, batch_insert_size)
                                info_futures = []

                        cls._progress_manager.update_progress(
                            message=t('repo_scan_progress', count=new_count + updated_count, new=new_count)
                        )

        if paths_to_update_time and not cls._progress_manager.is_stopped():
            DBOperations.batch_update_files_scan_time(paths_to_update_time, current_scan_time)
        
        if info_futures and not cls._progress_manager.is_stopped():
            new_count += cls._process_info_futures(info_futures, all_files_info, current_scan_time, batch_insert_size)
        
        if all_files_info and not cls._progress_manager.is_stopped():
            DBOperations.batch_insert_files_index(all_files_info)

        return new_count, updated_count

    @classmethod
    def _process_info_futures(cls, futures: List[Future], info_list: List[FileIndexDBModel], 
                             current_scan_time: str, batch_size: int) -> int:
        """
        用途说明：处理已完成的文件信息获取任务。
        """
        success_count: int = 0
        for future in as_completed(futures):
            if cls._progress_manager.is_stopped(): break
            try:
                file_info: Optional[FileIndexDBModel] = future.result()
                if file_info:
                    file_info.scan_time = current_scan_time
                    info_list.append(file_info)
                    success_count += 1
            except Exception as e:
                LogUtils.error(t('repo_scan_info_error', error=str(e)))

            if len(info_list) >= batch_size:
                DBOperations.batch_insert_files_index(info_list)
                info_list.clear()
        
        return success_count

    @classmethod
    def _phase_cleanup(cls, current_scan_time: str) -> int:
        """
        用途说明：清理失效索引。
        """
        LogUtils.info(t('repo_scan_phase_cleanup'))
        cls._progress_manager.update_progress(message=t('repo_scan_cleaning'))
        deleted_count: int = DBOperations.delete_files_by_not_scan_time(current_scan_time)
        DBOperations.copy_file_index_to_history()
        return deleted_count

    @classmethod
    def _handle_stopped(cls) -> None:
        """
        用途说明：处理任务手动停止。
        """
        cls._progress_manager.set_status(ProgressStatus.IDLE)
        cls._progress_manager.set_stop_flag(False)
        cls._progress_manager.update_progress(message=t('user_stop_task'))
        LogUtils.info(t('repo_scan_stop_ack'))
