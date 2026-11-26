import os
import threading
from contextvars import Context, copy_context
from typing import Dict, List, Optional

from backend.album.face_engine import FaceRecognitionEngine
from backend.album.face_pipeline import BATCH_SIZE, PIPELINE_VERSION
from backend.common.i18n_utils import t
from backend.common.file_type_enum import FileType
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressInfo, ProgressManager, ProgressStatus
from backend.common.repo_context import get_current_repo_id, set_current_repo_id
from backend.db.db_operations import DBOperations
from backend.model.db.face_embedding_db_model import FaceEmbeddingDBModel
from backend.model.db.face_queue_item_db_model import FaceQueueItemDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.face_index_result import FaceIndexSummaryResult, FaceTaskStatusResult
from backend.repository.repository_service import repositoryService
from backend.setting.setting_service import settingService


class FaceService:
    """
    用途说明：人脸索引任务服务，保证全系统同一时间只有一个识别任务、一个工作线程并按队列顺序处理。
    线程模型：持久化队列按文件路径去重；暂停只阻塞工作线程并保留队列，停止等待当前图片结束后清空队列。
    """

    _task_guard: threading.Lock = threading.Lock()
    _clear_guard: threading.Lock = threading.Lock()
    _progress_by_repo: Dict[int, ProgressManager] = {}
    _failed_by_repo: Dict[int, int] = {}
    _active_repo_id: Optional[int] = None
    _active_thread: Optional[threading.Thread] = None
    _stop_event: Optional[threading.Event] = None
    _resume_event: Optional[threading.Event] = None

    @classmethod
    def _get_progress_manager(cls, repo_id: int) -> ProgressManager:
        """
        用途说明：获取指定仓库的进度管理器，调用方需持有任务控制锁。
        入参说明：repo_id (int) - 仓库 ID。
        返回值说明：ProgressManager - 该仓库独立的任务状态与进度信息。
        """
        if repo_id not in cls._progress_by_repo:
            cls._progress_by_repo[repo_id] = ProgressManager()
        return cls._progress_by_repo[repo_id]

    @classmethod
    def get_active_repo_id(cls) -> Optional[int]:
        """
        用途说明：获取当前全局人脸任务所属仓库。
        入参说明：无。
        返回值说明：Optional[int] - 正在运行或暂停的仓库 ID；无任务时返回 None。
        """
        with cls._task_guard:
            if cls._active_thread is not None and cls._active_thread.is_alive():
                return cls._active_repo_id
            return None

    @classmethod
    def start_task(cls, enqueue_pending: bool = True, resume_paused: bool = True) -> bool:
        """
        用途说明：启动当前仓库的单线程人脸队列任务；手动开始时先批量去重入队。
        入参说明：
            enqueue_pending (bool): 是否把当前仓库所有未处理图片加入队列；扫描自动启动时传 False。
            resume_paused (bool): 当前仓库任务暂停时是否允许恢复；自动启动传 False，避免擅自解除暂停。
        返回值说明：bool - 是否成功启动或恢复任务；已有其他任务、同仓库处理中或入队失败时返回 False。
        """
        repo_id: int = get_current_repo_id()
        progress: Optional[ProgressManager] = None
        thread: Optional[threading.Thread] = None
        try:
            # 与停止、清除共用门闩，避免任务切换期间插入相互覆盖的新线程。
            with cls._clear_guard:
                with cls._task_guard:
                    if cls._active_thread is not None and cls._active_thread.is_alive():
                        if cls._active_repo_id == repo_id and resume_paused \
                                and cls._resume_event is not None and not cls._resume_event.is_set():
                            cls._resume_event.set()
                            progress = cls._get_progress_manager(repo_id)
                            progress.set_status(ProgressStatus.PROCESSING)
                            progress.update_progress(message=t('face_task_preparing'))
                            return True
                        LogUtils.info(t('face_task_already_running_log', repo_id=repo_id))
                        return False

                    if enqueue_pending and not DBOperations.enqueue_pending_face_images(PIPELINE_VERSION):
                        progress = cls._get_progress_manager(repo_id)
                        progress.set_status(ProgressStatus.ERROR)
                        progress.update_progress(message=t('face_queue_enqueue_failed'))
                        return False

                    progress = cls._get_progress_manager(repo_id)
                    progress.set_stop_flag(False)
                    progress.set_status(ProgressStatus.PROCESSING)
                    queue_count: int = DBOperations.get_face_queue_count()
                    progress.reset_progress(total=queue_count, message=t('face_task_preparing'))
                    cls._failed_by_repo[repo_id] = 0
                    if queue_count == 0:
                        progress.set_status(ProgressStatus.COMPLETED)
                        progress.update_progress(message=t('face_task_no_queue'))
                        return True

                    stop_event: threading.Event = threading.Event()
                    resume_event: threading.Event = threading.Event()
                    resume_event.set()
                    context: Context = copy_context()
                    thread = threading.Thread(
                        target=context.run,
                        args=(cls._run_task, repo_id, progress, stop_event, resume_event),
                        name=f'FaceIndex-{repo_id}',
                        daemon=True
                    )
                    cls._active_repo_id = repo_id
                    cls._active_thread = thread
                    cls._stop_event = stop_event
                    cls._resume_event = resume_event
                    thread.start()
            LogUtils.info(t('face_task_started_log', repo_id=repo_id))
            return True
        except Exception as e:
            LogUtils.error(t('face_task_start_failed_log', repo_id=repo_id, error=str(e)))
            with cls._clear_guard:
                with cls._task_guard:
                    # 仅清理本次启动创建的线程，避免误伤后续接管的新任务。
                    if thread is None or cls._active_thread is thread:
                        cls._active_repo_id = None
                        cls._active_thread = None
                        cls._stop_event = None
                        cls._resume_event = None
                        if progress is not None:
                            progress.set_status(ProgressStatus.ERROR)
                            progress.update_progress(message=t('face_task_start_failed', error=str(e)))
            return False

    @classmethod
    def pause_task(cls, repo_id: Optional[int] = None) -> bool:
        """
        用途说明：暂停指定仓库的识别任务，当前图片处理完成后等待恢复，队列和已处理数据保持不变。
        入参说明：repo_id (Optional[int]) - 目标仓库；为空时使用当前请求仓库。
        返回值说明：bool - 当前仓库存在可暂停任务时返回 True。
        """
        target_repo_id: int = get_current_repo_id() if repo_id is None else repo_id
        with cls._task_guard:
            if cls._active_repo_id != target_repo_id or cls._active_thread is None \
                    or not cls._active_thread.is_alive() or cls._resume_event is None \
                    or not cls._resume_event.is_set():
                return False
            cls._resume_event.clear()
            progress: ProgressManager = cls._get_progress_manager(target_repo_id)
            remaining: int = DBOperations.get_face_queue_count()
            progress.set_status(ProgressStatus.PAUSED)
            progress.update_progress(message=t('face_task_paused', remaining=remaining))
        LogUtils.info(t('face_task_paused_log', repo_id=target_repo_id))
        return True

    @classmethod
    def stop_task(cls, repo_id: Optional[int] = None) -> bool:
        """
        用途说明：停止指定仓库的人脸识别任务，并在线程退出后清空该仓库整个待识别队列。
        入参说明：repo_id (Optional[int]) - 要停止的仓库 ID；为空时读取当前请求仓库上下文。
        返回值说明：bool - 任务已停止且队列已清空时返回 True；其他仓库运行中或停止超时返回 False。
        """
        target_repo_id: int = get_current_repo_id() if repo_id is None else repo_id
        with cls._clear_guard:
            return cls._stop_task_internal(target_repo_id)

    @classmethod
    def _stop_task_internal(cls, repo_id: int) -> bool:
        """
        用途说明：在持有清除门闩时执行停止、等待和队列清空，供停止与清除人脸数据共用。
        入参说明：repo_id (int) - 目标仓库 ID。
        返回值说明：bool - 是否完成停止与队列清空。
        """
        thread: Optional[threading.Thread] = None
        with cls._task_guard:
            active_repo_id: Optional[int] = cls._active_repo_id
            if cls._active_thread is not None and cls._active_thread.is_alive() \
                    and active_repo_id != repo_id:
                return False
            if active_repo_id == repo_id and cls._active_thread is not None \
                    and cls._active_thread.is_alive():
                thread = cls._active_thread
                if cls._stop_event is not None:
                    cls._stop_event.set()
                if cls._resume_event is not None:
                    cls._resume_event.set()
                progress: ProgressManager = cls._get_progress_manager(repo_id)
                progress.set_stop_flag(True)
                progress.update_progress(message=t('face_task_stopping'))

        if thread is not None:
            thread.join(timeout=30.0)
        with cls._task_guard:
            if thread is not None and thread.is_alive():
                return False
            if cls._active_thread is thread:
                cls._active_repo_id = None
                cls._active_thread = None
                cls._stop_event = None
                cls._resume_event = None

        previous_repo_id: int = get_current_repo_id()
        set_current_repo_id(repo_id)
        try:
            if not DBOperations.clear_face_queue():
                return False
        finally:
            set_current_repo_id(previous_repo_id)

        progress = cls._get_progress_manager(repo_id)
        progress.set_stop_flag(False)
        progress.set_status(ProgressStatus.STOPPED)
        completed: int = progress.get_raw_progress_info().current
        progress.update_progress(message=t('face_task_stopped', completed=completed))
        LogUtils.info(t('face_queue_cleared_log', repo_id=repo_id))
        return True

    @classmethod
    def clear_data(cls) -> bool:
        """
        用途说明：先停止并清空当前仓库队列，再清空该仓库的人脸特征与图片处理状态。
        入参说明：无（仓库 ID 从当前请求上下文读取）。
        返回值说明：bool - 当前仓库任务已停止且三张人脸队列表清空时返回 True；其他仓库正在运行时返回 False。
        """
        repo_id: int = get_current_repo_id()
        try:
            # 清除与启动互斥，避免等待旧任务期间又启动一个新任务。
            with cls._clear_guard:
                if not cls._stop_task_internal(repo_id):
                    return False
                if not DBOperations.clear_face_data():
                    return False
                progress: ProgressManager = cls._get_progress_manager(repo_id)
                progress.set_stop_flag(False)
                progress.set_status(ProgressStatus.IDLE)
                progress.reset_progress(message=t('face_data_cleared'))
                cls._failed_by_repo[repo_id] = 0
            LogUtils.info(t('face_data_cleared_log', repo_id=repo_id))
            return True
        except Exception as e:
            LogUtils.error(t('face_data_clear_failed', repo_id=repo_id, error=str(e)))
            return False

    @classmethod
    def get_status(cls) -> FaceTaskStatusResult:
        """
        用途说明：获取全局任务状态与当前仓库的待处理数、队列数、已保存人脸数。
        入参说明：无（仓库 ID 从当前请求上下文读取）。
        返回值说明：FaceTaskStatusResult - 状态、运行仓库、暂停标志、进度、队列与失败数量。
        """
        repo_id: int = get_current_repo_id()
        summary: FaceIndexSummaryResult = DBOperations.get_face_index_summary(PIPELINE_VERSION)
        with cls._task_guard:
            active_repo_id: Optional[int] = cls._active_repo_id
            running: bool = cls._active_thread is not None and cls._active_thread.is_alive()
            failed: int = cls._failed_by_repo.get(repo_id, 0)

            if running and active_repo_id is not None:
                active_progress: ProgressManager = cls._get_progress_manager(active_repo_id)
                raw_status: dict = active_progress.get_status()
                progress: ProgressInfo = active_progress.get_raw_progress_info()
                failed = cls._failed_by_repo.get(active_repo_id, 0)
                return FaceTaskStatusResult(
                    status=raw_status['status'],
                    running=True,
                    paused=raw_status['status'] == ProgressStatus.PAUSED.value,
                    repo_id=repo_id,
                    active_repo_id=active_repo_id,
                    total=progress.total,
                    completed=progress.current,
                    pending=summary.pending,
                    remaining=summary.queued,
                    queued=summary.queued,
                    faces=summary.faces,
                    failed=failed,
                    message=progress.message
                )

            progress_manager: ProgressManager = cls._get_progress_manager(repo_id)
            raw_status = progress_manager.get_status()
            message: str = raw_status['progress']['message']
            if not message or raw_status['status'] == ProgressStatus.IDLE.value:
                message = t('face_status_ready', remaining=summary.queued)
            return FaceTaskStatusResult(
                status=raw_status['status'],
                running=False,
                paused=False,
                repo_id=repo_id,
                active_repo_id=None,
                total=summary.total,
                completed=max(0, summary.total - summary.pending),
                pending=summary.pending,
                remaining=summary.queued,
                queued=summary.queued,
                faces=summary.faces,
                failed=failed,
                message=message
            )

    @staticmethod
    def _wait_for_resume(progress: ProgressManager, stop_event: threading.Event,
                         resume_event: threading.Event) -> bool:
        """
        用途说明：在批次或单张图片开始前等待恢复；暂停期间保留队列且仍占用全局单任务名额。
        入参说明：
            progress (ProgressManager): 当前任务进度管理器。
            stop_event (threading.Event): 停止事件。
            resume_event (threading.Event): 恢复事件。
        返回值说明：bool - True 表示可以继续；False 表示收到停止信号。
        """
        while not stop_event.is_set():
            if resume_event.is_set():
                if progress.get_raw_status() == ProgressStatus.PAUSED:
                    progress.set_status(ProgressStatus.PROCESSING)
                return True
            if progress.get_raw_status() != ProgressStatus.PAUSED:
                progress.set_status(ProgressStatus.PAUSED)
                progress.update_progress(message=t('face_task_paused', remaining=DBOperations.get_face_queue_count()))
            resume_event.wait(timeout=0.2)
        return False

    @classmethod
    def _start_next_queued_repo(cls, skip_repo_id: Optional[int] = None) -> None:
        """
        用途说明：当前任务完成后按仓库 ID 查找下一个已有队列的仓库，继续维持全系统单任务串行处理。
        入参说明：skip_repo_id (Optional[int]) - 需要跳过的仓库；当前任务有失败项时跳过自身，避免立即反复重试。
        返回值说明：无；自动识别关闭、没有队列或其他任务已启动时不处理。
        """
        if settingService.get_config().album.auto_face_recognition is not True:
            return
        previous_repo_id: int = get_current_repo_id()
        try:
            for repo in repositoryService.list_repos():
                if repo.id == skip_repo_id:
                    continue
                set_current_repo_id(repo.id)
                queue_count: int = DBOperations.get_face_queue_count()
                if queue_count > 0:
                    if cls.start_task(enqueue_pending=False, resume_paused=False):
                        LogUtils.info(t('face_task_auto_dispatch_log', repo_id=repo.id))
                    return
        except Exception as e:
            LogUtils.error(t('face_task_auto_dispatch_failed_log', error=str(e)))
        finally:
            set_current_repo_id(previous_repo_id)

    @classmethod
    def _run_task(cls, repo_id: int, progress: ProgressManager, stop_event: threading.Event,
                  resume_event: threading.Event) -> None:
        """
        用途说明：人脸任务工作线程，按持久化队列游标分批读取并顺序处理图片。
        入参说明：
            repo_id (int): 本次任务仓库 ID。
            progress (ProgressManager): 该仓库的进度信息。
            stop_event (threading.Event): 停止事件。
            resume_event (threading.Event): 暂停与恢复事件。
        返回值说明：无；完成、停止或异常都会更新状态，并在 finally 中释放全局任务占用。
        """
        set_current_repo_id(repo_id)
        processed_count: int = 0
        failed_count: int = 0
        face_count: int = 0
        dispatch_next: bool = False
        try:
            if not DBOperations.cleanup_orphan_face_data():
                raise RuntimeError(t('face_data_orphan_cleanup_failed'))

            queue_count: int = DBOperations.get_face_queue_count()
            progress.reset_progress(total=queue_count, message=t('face_task_loading_models'))
            if queue_count == 0:
                progress.set_status(ProgressStatus.COMPLETED)
                progress.update_progress(message=t('face_task_no_queue'))
                dispatch_next = True
                return

            after_queue_id: int = 0
            with FaceRecognitionEngine() as engine:
                while not stop_event.is_set():
                    if not cls._wait_for_resume(progress, stop_event, resume_event):
                        break
                    batch: List[FaceQueueItemDBModel] = DBOperations.get_queued_face_images(
                        after_queue_id, BATCH_SIZE
                    )
                    if not batch:
                        break

                    for queue_item in batch:
                        if not cls._wait_for_resume(progress, stop_event, resume_event):
                            break
                        file_info: Optional[FileIndexDBModel] = DBOperations.get_file_by_path(
                            queue_item.file_path
                        )
                        is_stale: bool = (
                            file_info is None
                            or file_info.file_type != FileType.IMAGE.value
                            or (file_info.recycle_bin_time is not None and file_info.recycle_bin_time != '')
                            or file_info.file_md5 != queue_item.file_md5
                        )
                        if is_stale:
                            if not DBOperations.delete_face_queue_item(queue_item.id, queue_item.file_md5):
                                raise RuntimeError(t('face_queue_delete_failed'))
                        else:
                            try:
                                if not os.path.isfile(file_info.file_path):
                                    raise FileNotFoundError(t('face_image_not_found', path=file_info.file_path))
                                faces: List[FaceEmbeddingDBModel] = engine.recognize(
                                    file_info.file_path, file_info.file_md5
                                )
                                if stop_event.is_set():
                                    break
                                if not DBOperations.save_face_file_result(
                                    file_info, faces, PIPELINE_VERSION,
                                    queue_item.id, queue_item.file_md5
                                ):
                                    raise RuntimeError(t('face_data_save_failed'))
                                face_count += len(faces)
                            except Exception as e:
                                failed_count += 1
                                cls._failed_by_repo[repo_id] = failed_count
                                LogUtils.error(t('face_image_process_failed_log',
                                                 path=file_info.file_path, error=str(e)))

                        processed_count += 1
                        progress.update_progress(
                            current=processed_count,
                            message=t('face_task_progress', current=processed_count,
                                      total=queue_count, path=queue_item.file_path)
                        )

                    after_queue_id = batch[-1].id
                    if stop_event.is_set():
                        break

            if stop_event.is_set():
                progress.set_status(ProgressStatus.STOPPED)
                progress.update_progress(message=t('face_task_stopped', completed=processed_count))
                LogUtils.info(t('face_task_stopped_log', repo_id=repo_id, completed=processed_count))
            else:
                progress.set_status(ProgressStatus.COMPLETED)
                message: str = t('face_task_completed', completed=processed_count,
                                 faces=face_count, failed=failed_count)
                progress.update_progress(message=message)
                dispatch_next = failed_count == 0
                LogUtils.info(t('face_task_completed_log', repo_id=repo_id,
                                completed=processed_count, faces=face_count, failed=failed_count))
        except Exception as e:
            LogUtils.error(t('face_task_failed_log', repo_id=repo_id, error=str(e)))
            progress.set_status(ProgressStatus.ERROR)
            progress.update_progress(message=t('face_task_failed', error=str(e)))
        finally:
            with cls._task_guard:
                if cls._active_thread is threading.current_thread():
                    cls._active_repo_id = None
                    cls._active_thread = None
                    cls._stop_event = None
                    cls._resume_event = None
            if stop_event.is_set():
                # 停止或清除已接管任务收尾时，不再自动接续其他仓库队列。
                dispatch_next = False
            if dispatch_next:
                cls._start_next_queued_repo(repo_id if failed_count > 0 else None)
