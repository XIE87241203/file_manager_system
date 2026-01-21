from abc import ABC
from typing import Any, Dict, Callable

from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressManager, ProgressStatus
from backend.common.thread_pool import ThreadPoolManager


class BaseAsyncService(ABC):
    """
    用途说明：基础异步任务服务基类，提供统一的任务管理逻辑、进度追踪以及线程池调用接口。
    """
    # 每个子类都会通过 __init_subclass__ 自动获得一个独立的 ProgressManager 实例
    _progress_manager: ProgressManager

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._progress_manager = ProgressManager()

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """
        用途说明：获取当前异步任务的状态和进度。
        入参说明：无
        返回值说明：Dict[str, Any] - 包含 status 和 progress 详情的字典。
        """
        return cls._progress_manager.get_status()

    @classmethod
    def stop_task(cls) -> None:
        """
        用途说明：停止正在运行的异步任务。封装了通用的停止逻辑，将停止标志位置为 True。
        入参说明：无
        返回值说明：无
        """
        if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            cls._progress_manager.set_stop_flag(True)
            LogUtils.info(f"{cls.__name__}: 用户请求停止任务，已设置停止标志位")

    @classmethod
    def _start_task(cls, task_callable: Callable, *args: Any, **kwargs: Any) -> bool:
        """
        用途说明：通过全局线程池启动异步任务的内部方法。
        入参说明：
            task_callable (Callable): 要在后台执行的目标函数或方法。
            *args: 传递给目标函数的位置参数。
            **kwargs: 传递给目标函数的关键字参数。
        返回值说明：bool - 任务是否成功提交到线程池。
        """
        try:
            ThreadPoolManager.submit(task_callable, *args, **kwargs)
            LogUtils.info(f"{cls.__name__}: 异步任务已成功提交至线程池")
            return True
        except Exception as e:
            LogUtils.error(f"{cls.__name__}: 提交异步任务失败: {e}")
            return False
