import threading
import time
from typing import Callable, List, Dict, Optional

from backend.common.log_utils import LogUtils
from backend.common.thread_pool import ThreadPoolManager


class HeartbeatService:
    """
    用途说明：全局心跳发生器（单例），每秒触发一次已注册的任务。
    """
    _instance: Optional['HeartbeatService'] = None
    _lock: threading.Lock = threading.Lock()
    
    # 心跳间隔时间（秒）
    HEARTBEAT_INTERVAL: float = 1.0

    _tasks: Dict[str, Callable[[], None]] = {}
    _running: bool = False
    _task_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> 'HeartbeatService':
        """
        用途说明：实现单例模式。
        入参说明：无
        返回值说明：HeartbeatService: 单例实例。
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HeartbeatService, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register_task(cls, name: str, task: Callable[[], None]) -> None:
        """
        用途说明：注册一个心跳任务。采用锁机制确保线程安全，并防止重复注册。
        入参说明：
            name (str): 任务唯一标识。
            task (Callable): 任务回调函数。
        返回值说明：无
        """
        with cls._task_lock:
            if name in cls._tasks:
                LogUtils.debug(f"心跳服务：任务 [{name}] 已存在，无需重复注册")
                return
            cls._tasks[name] = task
            LogUtils.debug(f"心跳服务：成功注册新任务 [{name}]")

    @classmethod
    def unregister_task(cls, name: str) -> None:
        """
        用途说明：取消注册一个心跳任务。
        入参说明：
            name (str): 任务唯一标识。
        返回值说明：无
        """
        with cls._task_lock:
            if name in cls._tasks:
                del cls._tasks[name]
                LogUtils.debug(f"心跳服务：已移除任务 [{name}]")

    @classmethod
    def start(cls) -> None:
        """
        用途说明：启动心跳服务。在 main.py 初始化时调用。
        入参说明：无
        返回值说明：无
        """
        with cls._lock:
            if cls._running:
                return
            cls._running = True
            ThreadPoolManager.submit(cls._run_loop)
            LogUtils.info("心跳服务已启动")

    @classmethod
    def stop(cls) -> None:
        """
        用途说明：停止心跳服务。
        入参说明：无
        返回值说明：无
        """
        with cls._lock:
            cls._running = False
            LogUtils.info("心跳服务已停止")

    @classmethod
    def _run_loop(cls) -> None:
        """
        用途说明：心跳主循环，根据 HEARTBEAT_INTERVAL 定时执行。
        入参说明：无
        返回值说明：无
        """
        while cls._running:
            try:
                # 获取当前所有任务的快照，避免执行时长时间占用锁
                tasks_snapshot: List[Callable[[], None]] = []
                with cls._task_lock:
                    tasks_snapshot = list(cls._tasks.values())
                
                for task in tasks_snapshot:
                    try:
                        task()
                    except Exception as e:
                        LogUtils.error(f"心跳任务执行异常: {e}")
                
            except Exception as e:
                LogUtils.error(f"心跳循环核心异常: {e}")
            
            time.sleep(cls.HEARTBEAT_INTERVAL)
