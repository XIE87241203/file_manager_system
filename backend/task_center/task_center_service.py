from typing import Any, Dict, List, Optional, Type

from backend.album.face_service import FaceService
from backend.common.base_async_service import BaseAsyncService
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.common.repo_context import get_current_repo_id, set_current_repo_id
from backend.file_name_repository.batch_check_service import BatchCheckService
from backend.file_repository.duplicate_check.duplicate_service import DuplicateService
from backend.file_repository.recycle_bin_service import RecycleBinService
from backend.file_repository.scan_service import ScanService
from backend.file_repository.thumbnail.thumbnail_generator import ThumbnailGenerator
from backend.file_repository.thumbnail.thumbnail_service import ThumbnailService
from backend.model.face_index_result import FaceTaskStatusResult
from backend.organize.organize_task_service import organizeTaskService
from backend.repository.repository_result import RepositoryResult
from backend.repository.repository_service import repositoryService
from backend.task_center.task_models import CurrentTaskInfo, CurrentTaskListResult
from backend.user.user_service import userService


class TaskCenterService:
    """
    用途说明：聚合全系统运行或暂停的长任务与手动整理会话，并按用户仓库可见性和管理权限提供统一控制。
    说明：系统管理员可管理全部仓库；仓库管理员只能管理自己有管理员权限的仓库，成员仅可查看。
    """

    _TASK_ORDER: Dict[str, int] = {
        'scan': 1, 'metadata': 2, 'duplicate': 3, 'organize': 4, 'face': 5,
        'thumbnail': 6, 'thumbnail_sync': 7, 'batch_check': 8, 'recycle_cleanup': 9
    }

    @classmethod
    def list_tasks(cls, username: str) -> CurrentTaskListResult:
        """
        用途说明：汇总当前用户可见仓库中的全部运行或暂停任务。
        入参说明：username (str) - Token 鉴权后的当前用户名。
        返回值说明：CurrentTaskListResult - 任务列表及数量；没有任务时为空列表。
        """
        is_system_admin: bool = userService.is_admin(username)
        repos: List[RepositoryResult] = (repositoryService.list_repos() if is_system_admin
                                         else repositoryService.list_repos_for_user(username))
        if is_system_admin:
            for repo in repos:
                repo.permission = 'admin'
        repo_map: Dict[int, str] = {repo.id: repo.name for repo in repos}
        manageable_repo_ids: set[int] = {repo.id for repo in repos if repo.permission == 'admin'}
        tasks: List[CurrentTaskInfo] = []

        cls._collect_async_task(ScanService, 'metadata' if ScanService._task_kind == 'metadata' else 'scan',
                                repo_map, manageable_repo_ids, tasks)
        cls._collect_async_task(DuplicateService, 'duplicate', repo_map, manageable_repo_ids, tasks)
        cls._collect_async_task(BatchCheckService, 'batch_check', repo_map, manageable_repo_ids, tasks)
        cls._collect_async_task(RecycleBinService, 'recycle_cleanup', repo_map, manageable_repo_ids, tasks)
        cls._collect_async_task(ThumbnailService, 'thumbnail_sync', repo_map, manageable_repo_ids, tasks)

        for session in organizeTaskService.list_active_sessions():
            if session.repo_id not in repo_map:
                continue
            can_manage: bool = session.repo_id in manageable_repo_ids
            tasks.append(CurrentTaskInfo(
                key='organize', repo_id=session.repo_id, repo_name=repo_map[session.repo_id],
                status=session.status, current=max(0, session.total - len(session.queue)),
                total=session.total, remaining=len(session.queue),
                message=cls._organize_message(session.total, len(session.queue)),
                can_pause=can_manage and session.status == ProgressStatus.PROCESSING.value,
                can_resume=can_manage and session.status == ProgressStatus.PAUSED.value,
                can_stop=can_manage
            ))

        face_repo_id: Optional[int] = FaceService.get_active_repo_id()
        if face_repo_id is not None and face_repo_id in repo_map:
            previous_repo_id: int = get_current_repo_id()
            try:
                set_current_repo_id(face_repo_id)
                face_status: FaceTaskStatusResult = FaceService.get_status()
                if face_status.status in (ProgressStatus.PROCESSING.value, ProgressStatus.PAUSED.value):
                    can_manage = face_repo_id in manageable_repo_ids
                    tasks.append(CurrentTaskInfo(
                        key='face', repo_id=face_repo_id, repo_name=repo_map[face_repo_id],
                        status=face_status.status, current=face_status.completed, total=face_status.total,
                        remaining=face_status.remaining, message=face_status.message,
                        can_pause=can_manage and not face_status.paused,
                        can_resume=can_manage and face_status.paused, can_stop=can_manage
                    ))
            except Exception as e:
                LogUtils.error(t('task_center_face_status_error', error=str(e)))
            finally:
                set_current_repo_id(previous_repo_id)

        for progress in ThumbnailGenerator().get_repo_statuses():
            if progress.repo_id not in repo_map:
                continue
            can_manage: bool = progress.repo_id in manageable_repo_ids
            tasks.append(CurrentTaskInfo(
                key='thumbnail', repo_id=progress.repo_id, repo_name=repo_map[progress.repo_id],
                status=ProgressStatus.PAUSED.value if progress.paused else ProgressStatus.PROCESSING.value,
                current=progress.completed, total=progress.total, remaining=progress.remaining,
                message=t('task_thumbnail_progress', current=progress.completed,
                          total=progress.total, remaining=progress.remaining),
                can_pause=can_manage and not progress.paused,
                can_resume=can_manage and progress.paused, can_stop=can_manage
            ))

        tasks.sort(key=lambda item: (item.repo_id, cls._TASK_ORDER.get(item.key, 99)))
        return CurrentTaskListResult(tasks=tasks, count=len(tasks))

    @classmethod
    def _collect_async_task(cls, service: Type[BaseAsyncService], key: str, repo_map: Dict[int, str],
                            manageable_repo_ids: set[int], tasks: List[CurrentTaskInfo]) -> None:
        """
        用途说明：读取一个 BaseAsyncService 子类的活动任务并加入聚合列表。
        入参说明：
            service (Type[BaseAsyncService]): 异步任务服务类。
            key (str): 统一任务类型标识。
            repo_map (Dict[int, str]): 可见仓库 ID 与名称映射。
            manageable_repo_ids (set[int]): 当前用户可管理的仓库 ID 集合。
            tasks (List[CurrentTaskInfo]): 待追加的任务列表。
        返回值说明：无；任务不属于可见仓库或已结束时跳过。
        """
        if not service.is_task_active():
            return
        repo_id: Optional[int] = service.get_active_repo_id()
        if repo_id is None or repo_id not in repo_map:
            return
        status: Dict[str, Any] = service.get_status()
        progress: Dict = status.get('progress', {})
        current: int = int(progress.get('current', 0) or 0)
        total: int = int(progress.get('total', 0) or 0)
        can_manage: bool = repo_id in manageable_repo_ids
        tasks.append(CurrentTaskInfo(
            key=key, repo_id=repo_id, repo_name=repo_map[repo_id], status=status['status'],
            current=current, total=total, remaining=max(0, total - current),
            message=str(progress.get('message', '')), can_pause=can_manage and status['status'] == 'processing',
            can_resume=can_manage and status['status'] == 'paused', can_stop=can_manage
        ))

    @staticmethod
    def _organize_message(total: int, remaining: int) -> str:
        """
        用途说明：生成与整理页面一致的已完成数量和总数文案。
        入参说明：total (int) - 本次整理总数；remaining (int) - 当前剩余数量。
        返回值说明：str - 整理进度文案。
        """
        return t('task_organize_progress', done=max(0, total - remaining), total=total)

    @classmethod
    def control_task(cls, username: str, key: str, repo_id: int, action: str) -> bool:
        """
        用途说明：校验任务权限后分发暂停、恢复或停止操作。
        入参说明：
            username (str): 当前用户名。
            key (str): 任务类型标识。
            repo_id (int): 任务所属仓库 ID。
            action (str): pause / resume / stop。
        返回值说明：bool - 操作是否已被对应任务服务接受。
        异常说明：ValueError - 任务不存在、无权限或操作不受支持时抛出。
        """
        tasks: List[CurrentTaskInfo] = cls.list_tasks(username).tasks
        task: Optional[CurrentTaskInfo] = next((item for item in tasks if item.key == key and item.repo_id == repo_id), None)
        if task is None:
            raise ValueError(t('task_center_not_found'))
        allowed: bool = ((action == 'pause' and task.can_pause)
                         or (action == 'resume' and task.can_resume)
                         or (action == 'stop' and task.can_stop))
        if not allowed:
            raise ValueError(t('task_center_action_denied'))

        previous_repo_id: int = get_current_repo_id()
        set_current_repo_id(repo_id)
        try:
            return cls._dispatch(key, action, repo_id)
        except Exception as e:
            LogUtils.error(t('task_center_control_error', key=key, repo_id=repo_id, action=action, error=str(e)))
            raise
        finally:
            set_current_repo_id(previous_repo_id)

    @staticmethod
    def _dispatch(key: str, action: str, repo_id: int) -> bool:
        """
        用途说明：按任务类型调用真实服务的暂停、恢复或停止方法。
        入参说明：key (str) - 任务类型；action (str) - 操作；repo_id (int) - 仓库 ID。
        返回值说明：bool - 服务是否接受操作。
        """
        services: Dict[str, Type[BaseAsyncService]] = {
            'scan': ScanService, 'metadata': ScanService, 'duplicate': DuplicateService,
            'batch_check': BatchCheckService, 'recycle_cleanup': RecycleBinService,
            'thumbnail_sync': ThumbnailService
        }
        if key in services:
            service: Type[BaseAsyncService] = services[key]
            if action == 'pause':
                return service.pause_task(repo_id)
            if action == 'resume':
                return service.resume_task(repo_id)
            return service.stop_task(repo_id)
        if key == 'organize':
            if action == 'pause':
                return organizeTaskService.pause_task(repo_id)
            if action == 'resume':
                return organizeTaskService.resume_task(repo_id)
            return organizeTaskService.stop_task(repo_id)
        if key == 'face':
            if action == 'pause':
                return FaceService.pause_task(repo_id)
            if action == 'resume':
                return FaceService.start_task(enqueue_pending=False, resume_paused=True)
            return FaceService.stop_task(repo_id)
        if key == 'thumbnail':
            if action == 'pause':
                return ThumbnailService.pause_thumbnail_generation(repo_id)
            if action == 'resume':
                return ThumbnailService.resume_thumbnail_generation(repo_id)
            ThumbnailService.stop_thumbnail_generation(repo_id)
            return True
        return False


taskCenterService: TaskCenterService = TaskCenterService()
