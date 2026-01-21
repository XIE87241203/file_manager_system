from abc import ABC, abstractmethod
from typing import Any, Dict

from backend.common.progress_manager import ProgressManager


class BaseAsyncService(ABC):
    """
    用途说明：基础异步任务服务基类，封装了 ProgressManager 并提供任务控制与初始化的抽象接口。
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
    @abstractmethod
    def start_task(cls, params: Any) -> bool:
        """
        用途说明：启动异步任务的抽象接口。
        入参说明：
            params (Any): 启动任务所需的参数。
        返回值说明：bool - 是否成功启动。
        """
        pass

    @classmethod
    @abstractmethod
    def stop_task(cls) -> None:
        """
        用途说明：停止正在运行的异步任务。
        入参说明：无
        返回值说明：无
        """
        pass

    @classmethod
    @abstractmethod
    def init_task(cls, params: Any) -> Any:
        """
        用途说明：任务启动前的初始化准备工作（如状态校验、参数预处理、环境准备等）。
        入参说明：
            params (Any): 初始参数。
        返回值说明：Any - 返回初始化后的上下文数据或配置。
        """
        pass
