import os
from concurrent.futures import as_completed, Future
from datetime import datetime
from enum import Enum
from typing import Callable, List, Tuple, Optional

from backend.common.base_async_service import BaseAsyncService
from backend.album.face_service import FaceService
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.common.thread_pool import ThreadPoolManager
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.file_info_service import FileInfoService
from backend.file_repository.file_service import FileService
from backend.file_repository.thumbnail.thumbnail_service import ThumbnailService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.repository.repository_service import repositoryService
from backend.setting.setting_service import settingService
from backend.setting.setting_models import FileRepositorySettings


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

    _task_kind: str = 'scan'

    @classmethod
    def start_scan_task(cls, scan_mode: ScanMode = ScanMode.INDEX_SCAN,
                        on_complete: Optional[Callable[[], None]] = None) -> bool:
        """
        用途说明：启动异步扫描任务。包含初始化逻辑与线程池提交。
        入参说明：
            scan_mode (ScanMode): 扫描模式。
            on_complete (Optional[Callable[[], None]]): 扫描成功完成后的回调函数，可为空。
        返回值说明：bool - 是否成功启动。
        """
        try:
            # --- 初始化逻辑开始 ---
            if cls.is_task_active():
                LogUtils.error(t('repo_scan_running'))
                raise RuntimeError(t('repo_scan_running'))

            mode: ScanMode = scan_mode if isinstance(scan_mode, ScanMode) else ScanMode.INDEX_SCAN
            cls._task_kind = 'scan'
            
            # 获取当前仓库配置快照
            repo_config: FileRepositorySettings = repositoryService.get_current_config()

            # 重置进度状态
            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            cls._progress_manager.reset_progress(message=t('repo_scan_initializing'))
            # --- 初始化逻辑结束 ---
            
            # 调用基类的私有方法启动任务
            return cls._start_task(cls._internal_scan, mode, repo_config, on_complete)
        except Exception as e:
            LogUtils.error(t('repo_scan_start_failed', error=str(e)))
            return False

    @classmethod
    def start_metadata_refresh_task(cls) -> bool:
        """
        用途说明：启动异步补全任务，只处理当前索引中缺少媒体信息的有效图片和视频。
        入参说明：无；仓库 ID 来自当前请求上下文。
        返回值说明：bool - 是否成功提交任务；已有索引任务运行时返回 False。
        """
        try:
            if cls.is_task_active():
                LogUtils.error(t('repo_scan_running'))
                return False
            cls._task_kind = 'metadata'
            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            cls._progress_manager.reset_progress(message=t('repo_metadata_refresh_preparing'))
            started: bool = cls._start_task(cls._internal_metadata_refresh)
            if not started:
                cls._progress_manager.set_status(ProgressStatus.ERROR)
            return started
        except Exception as e:
            LogUtils.error(t('repo_metadata_refresh_error', error=str(e)))
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            return False

    @classmethod
    def _internal_metadata_refresh(cls) -> None:
        """
        用途说明：按主键游标分批补全缺失媒体信息，不遍历仓库目录、不修改扫描时间和回收站状态。
        入参说明：无；仓库 ID 来自异步任务上下文。
        返回值说明：无；更新进度状态，可由现有停止接口请求中断。
        """
        try:
            total_count: int = DBOperations.count_missing_album_metadata()
            cls._progress_manager.update_progress(total=total_count)
            if total_count == 0:
                message: str = t('repo_metadata_refresh_no_missing')
                cls._progress_manager.set_status(ProgressStatus.COMPLETED)
                cls._progress_manager.update_progress(message=message)
                LogUtils.info(message)
                return

            LogUtils.info(t('repo_metadata_refresh_started_log', count=total_count))
            after_id: int = 0
            processed_count: int = 0
            updated_count: int = 0
            failed_count: int = 0
            batch_size: int = 200

            while not cls._progress_manager.is_stopped():
                if not cls.wait_if_paused():
                    break
                candidates: List[FileIndexDBModel] = DBOperations.get_missing_album_metadata(
                    after_id, batch_size
                )
                if not candidates:
                    break
                metadata_list: List[FileIndexDBModel] = []
                for candidate in candidates:
                    if not cls.wait_if_paused():
                        break
                    after_id = candidate.id or after_id
                    processed_count += 1
                    metadata: Optional[FileIndexDBModel] = FileInfoService.get_album_metadata(
                        candidate.file_path
                    )
                    if metadata is None:
                        failed_count += 1
                        LogUtils.error(t('repo_metadata_refresh_file_failed_log', path=candidate.file_path))
                    else:
                        metadata_list.append(metadata)
                    cls._progress_manager.update_progress(
                        current=processed_count,
                        message=t('repo_metadata_refresh_progress', current=processed_count,
                                  total=total_count, path=candidate.file_path)
                    )

                if metadata_list:
                    updated_count += DBOperations.batch_update_album_metadata(metadata_list)

            if cls._progress_manager.is_stopped():
                message = t('repo_metadata_refresh_stopped', processed=processed_count, updated=updated_count)
                cls._progress_manager.set_status(ProgressStatus.STOPPED)
            else:
                message = t('repo_metadata_refresh_completed', updated=updated_count, failed=failed_count)
                cls._progress_manager.set_status(ProgressStatus.COMPLETED)
            cls._progress_manager.update_progress(message=message)
            LogUtils.info(message)
        except Exception as e:
            LogUtils.error(t('repo_metadata_refresh_error', error=str(e)))
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=t('repo_metadata_refresh_error', error=str(e)))

    @classmethod
    def _internal_scan(cls, scan_mode: ScanMode, repo_config: FileRepositorySettings,
                       on_complete: Optional[Callable[[], None]] = None) -> None:
        """
        用途说明：扫描任务调度核心逻辑。
        入参说明：
            scan_mode (ScanMode): 扫描模式。
            repo_config (FileRepositorySettings): 本次扫描的仓库配置快照。
            on_complete (Optional[Callable[[], None]]): 扫描成功完成后的回调函数，可为空。
        返回值说明：无
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
            
            if not cls.wait_if_paused():
                cls._handle_stopped()
                return

            # 第三阶段：清理失效索引与备份
            deleted_count: Optional[int] = cls._phase_cleanup(current_scan_time)
            if deleted_count is None:
                return

            # 扫描完成后自动重新计算文件仓库统计详情
            FileService.calculate_repo_detail()

            # 完成
            cls._progress_manager.set_status(ProgressStatus.COMPLETED)
            msg: str = t('repo_scan_completed', new_count=new_count, updated_count=updated_count, deleted_count=deleted_count)
            cls._progress_manager.update_progress(message=msg)
            LogUtils.info(msg)

            # 扫描成功完成后触发回调（如自动新增查重），回调异常不影响扫描结果
            if on_complete is not None:
                try:
                    on_complete()
                except Exception as e:
                    LogUtils.error(t('repo_scan_callback_error', error=str(e)))

            # 索引、失效清理和扫描回调均完成后再尝试启动，避免读取到尚未提交的数据。
            cls._try_start_face_queue()

        except Exception as e:
            LogUtils.error(t('repo_scan_error', error=str(e)))
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=t('internal_error', error=str(e)))

    @classmethod
    def _combined_scan_logic(cls, scan_mode: ScanMode, current_scan_time: str, repo_config: FileRepositorySettings) -> Tuple[int, int]:
        """
        用途说明：在一次目录遍历中完成文件发现、存在校验与新增文件特征提取；全量索引重建全部记录，增量索引只处理新增文件。
            每批文件信息成功写入索引后，按配置加入人脸或缩略图队列，不补处理已有文件。
        入参说明：
            scan_mode (ScanMode): 全量或增量索引模式。
            current_scan_time (str): 本次扫描的统一时间戳。
            repo_config (FileRepositorySettings): 本次扫描的仓库配置快照。
        返回值说明：Tuple[int, int] - (新增文件数, 已有文件数)。
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
            if not cls.wait_if_paused(): break
            if not os.path.exists(repo_path):
                LogUtils.error(t('repo_scan_path_not_found', path=repo_path))
                continue

            for root, _, files in os.walk(repo_path):
                if not cls.wait_if_paused(): break
                for file in files:
                    if not cls.wait_if_paused(): break
                    
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
                            info_futures.append(ThreadPoolManager.submit(FileInfoService.get_file_info, full_path))
                            
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
            if DBOperations.batch_insert_files_index(all_files_info):
                cls._enqueue_new_face_images(all_files_info)
                ThumbnailService.enqueue_new_file_thumbnails(all_files_info)
            all_files_info.clear()

        return new_count, updated_count

    @classmethod
    def _process_info_futures(cls, futures: List[Future], info_list: List[FileIndexDBModel], 
                             current_scan_time: str, batch_size: int) -> int:
        """
        用途说明：处理已完成的文件信息获取任务，分批写入索引并按开关为新媒体入队。
        入参说明：
            futures (List[Future]): 待获取文件信息的异步任务列表。
            info_list (List[FileIndexDBModel]): 尚未写入索引的文件信息累积列表。
            current_scan_time (str): 本次扫描的统一时间戳。
            batch_size (int): 单批写入索引的最大记录数。
        返回值说明：int - 成功获取文件信息的数量。
        """
        success_count: int = 0
        for future in as_completed(futures):
            if not cls.wait_if_paused(): break
            try:
                file_info: Optional[FileIndexDBModel] = future.result()
                if file_info:
                    file_info.scan_time = current_scan_time
                    info_list.append(file_info)
                    success_count += 1
            except Exception as e:
                LogUtils.error(t('repo_scan_info_error', error=str(e)))

            if len(info_list) >= batch_size:
                if DBOperations.batch_insert_files_index(info_list):
                    cls._enqueue_new_face_images(info_list)
                    ThumbnailService.enqueue_new_file_thumbnails(info_list)
                info_list.clear()
        
        return success_count

    @classmethod
    def _enqueue_new_face_images(cls, images: List[FileIndexDBModel]) -> None:
        """
        用途说明：自动识别开启时，将本批真正新增的图片去重加入人脸队列，不提前启动任务。
        入参说明：images (List[FileIndexDBModel]) - 本批已成功写入文件索引的记录，数量不超过 100 条。
        返回值说明：无；设置关闭或没有图片时不处理。
        """
        auto_face_recognition: bool = settingService.get_config().album.auto_face_recognition
        if auto_face_recognition is True and images:
            DBOperations.enqueue_face_images(images)

    @classmethod
    def _try_start_face_queue(cls) -> None:
        """
        用途说明：扫描和失效索引清理完成后，自动识别开启时尝试消费当前仓库已有队列。
        入参说明：无（仓库 ID 来自扫描线程上下文）。
        返回值说明：无；任务被其他仓库占用或当前任务暂停时保持排队，不擅自恢复。
        """
        auto_face_recognition: bool = settingService.get_config().album.auto_face_recognition
        if auto_face_recognition is True:
            FaceService.start_task(enqueue_pending=False, resume_paused=False)

    @classmethod
    def _phase_cleanup(cls, current_scan_time: str) -> Optional[int]:
        """
        用途说明：清理失效索引；暂停时等待恢复，停止时终止后续清理。
        入参说明：current_scan_time (str) - 本次扫描的统一时间戳。
        返回值说明：Optional[int] - 清理数量；已停止时返回 None。
        """
        if not cls.wait_if_paused():
            cls._handle_stopped()
            return None
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
