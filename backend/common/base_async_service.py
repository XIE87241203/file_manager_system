import threading
from abc import ABC
from typing import Any, Callable, Dict, Optional

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressManager, ProgressStatus
from backend.common.repo_context import get_current_repo_id
from backend.common.thread_pool import ThreadPoolManager


class BaseAsyncService(ABC):
    """
    用途说明：基础异步任务服务基类，提供统一的任务管理、进度追踪、暂停恢复及线程池调用接口。
    说明：每个子类有独立进度管理器；同一子类全局只允许一个任务，并记录任务所属仓库以便统一任务入口控制。
    """
    _progress_manager: ProgressManager
    _active_repo_id: Optional[int] = None
    _resume_event: threading.Event = threading.Event()
    _pre_pause_message: str = ''

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        用途说明：为每个子类创建独立的进度管理器与恢复事件。
        入参说明：kwargs (Any) - Python 子类定义时传入的关键字参数。
        返回值说明：无。
        """
        super().__init_subclass__(**kwargs)
        cls._progress_manager = ProgressManager()
        cls._active_repo_id = None
        cls._resume_event = threading.Event()
        cls._resume_event.set()
        cls._pre_pause_message = ''

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """
        用途说明：获取当前异步任务的状态和进度。
        入参说明：无。
        返回值说明：Dict[str, Any] - 包含 status 和 progress 详情的字典。
        """
        return cls._progress_manager.get_status()

    @classmethod
    def get_active_repo_id(cls) -> Optional[int]:
        """
        用途说明：获取当前任务所属仓库；没有运行或暂停任务时返回 None。
        入参说明：无。
        返回值说明：Optional[int] - 仓库 ID。
        """
        return cls._active_repo_id if cls.is_task_active() else None

    @classmethod
    def is_task_active(cls) -> bool:
        """
        用途说明：判断本服务是否有运行中或已暂停的任务。
        入参说明：无。
        返回值说明：bool - 正在运行或暂停时返回 True。
        """
        return cls._progress_manager.get_raw_status() in (ProgressStatus.PROCESSING, ProgressStatus.PAUSED)

    @classmethod
    def pause_task(cls, repo_id: Optional[int] = None) -> bool:
        """
        用途说明：暂停指定仓库的任务，工作线程在下一个检查点等待，已完成的处理结果保留。
        入参说明：repo_id (Optional[int]) - 目标仓库；为空时使用当前请求仓库。
        返回值说明：bool - 已接受暂停请求时返回 True。
        """
        target_repo_id: int = get_current_repo_id() if repo_id is None else repo_id
        if not cls.is_task_active() or cls._active_repo_id != target_repo_id \
                or cls._progress_manager.get_raw_status() != ProgressStatus.PROCESSING:
            return False
        cls._resume_event.clear()
        cls._pre_pause_message = cls._progress_manager.get_raw_progress_info().message
        cls._progress_manager.set_status(ProgressStatus.PAUSED)
        cls._progress_manager.update_progress(message=t('async_task_paused'))
        LogUtils.info(t('async_pause_requested', name=cls.__name__, repo_id=target_repo_id))
        return True

    @classmethod
    def resume_task(cls, repo_id: Optional[int] = None) -> bool:
        """
        用途说明：恢复指定仓库的暂停任务，使工作线程从等待点继续。
        入参说明：repo_id (Optional[int]) - 目标仓库；为空时使用当前请求仓库。
        返回值说明：bool - 已恢复时返回 True。
        """
        target_repo_id: int = get_current_repo_id() if repo_id is None else repo_id
        if not cls.is_task_active() or cls._active_repo_id != target_repo_id \
                or cls._progress_manager.get_raw_status() != ProgressStatus.PAUSED:
            return False
        cls._progress_manager.set_status(ProgressStatus.PROCESSING)
        if cls._pre_pause_message:
            cls._progress_manager.update_progress(message=cls._pre_pause_message)
        cls._pre_pause_message = ''
        cls._resume_event.set()
        LogUtils.info(t('async_task_resumed', name=cls.__name__, repo_id=target_repo_id))
        return True

    @classmethod
    def wait_if_paused(cls) -> bool:
        """
        用途说明：在任务检查点等待恢复；停止请求可同时解除等待。
        入参说明：无。
        返回值说明：bool - 可以继续返回 True，已停止返回 False。
        """
        while cls.is_task_active() and cls._progress_manager.get_raw_status() == ProgressStatus.PAUSED:
            if cls._progress_manager.is_stopped():
                return False
            cls._resume_event.wait(timeout=0.1)
        return not cls._progress_manager.is_stopped()

    @classmethod
    def stop_task(cls, repo_id: Optional[int] = None) -> bool:
        """
        用途说明：请求停止指定仓库的任务，具体业务在下一个检查点安全退出。
        入参说明：repo_id (Optional[int]) - 目标仓库；为空时使用当前请求仓库。
        返回值说明：bool - 已向运行或暂停任务发送停止请求时返回 True。
        """
        target_repo_id: int = get_current_repo_id() if repo_id is None else repo_id
        if not cls.is_task_active() or cls._active_repo_id != target_repo_id:
            return False
        cls._resume_event.set()
        cls._progress_manager.set_stop_flag(True)
        LogUtils.info(t('async_stop_requested', name=cls.__name__, repo_id=target_repo_id))
        return True

    @classmethod
    def _start_task(cls, task_callable: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
        """
        用途说明：通过全局线程池启动异步任务，并记录提交时的仓库上下文。
        入参说明：
            task_callable (Callable[..., Any]): 后台执行的方法。
            *args (Any): 传递给目标方法的位置参数。
            **kwargs (Any): 传递给目标方法的关键字参数。
        返回值说明：bool - 是否成功提交到线程池。
        """
        try:
            cls._active_repo_id = get_current_repo_id()
            cls._resume_event.set()
            cls._pre_pause_message = ''
            ThreadPoolManager.submit(task_callable, *args, **kwargs)
            LogUtils.info(t('async_task_submitted', name=cls.__name__))
            return True
        except Exception as e:
            cls._active_repo_id = None
            LogUtils.error(t('async_task_submit_failed', name=cls.__name__, error=str(e)))
            return False
