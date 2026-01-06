import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

class ThreadPoolManager:
    """
    用途：后端全局共享的线程池管理类，采用单例模式实现。
    提供统一的后台任务执行入口，避免重复创建线程池。
    """
    
    _instance = None
    _executor: ThreadPoolExecutor = None

    def __new__(cls) -> 'ThreadPoolManager':
        """
        用途：实现单例模式，确保整个应用只存在一个线程池管理器。
        入参说明：无
        返回值说明：ThreadPoolManager - 单例实例
        """
        if cls._instance is None:
            cls._instance = super(ThreadPoolManager, cls).__new__(cls)
            # 根据 CPU 核心数动态调整线程池大小，IO 密集型任务推荐 核心数 * 2 到 * 5
            # 此处取 16 和 核心数*4 的最小值，确保不会过度占用资源
            max_workers = min(16, (os.cpu_count() or 4) * 4)
            cls._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="GlobalPool")
        return cls._instance

    @staticmethod
    def submit(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        用途：向全局线程池提交一个异步任务。
        入参说明：
            fn (Callable): 要执行的函数。
            *args: 函数的位置参数。
            **kwargs: 函数的关键字参数。
        返回值说明：Future - 返回一个 Future 对象，用于获取任务执行结果或状态。
        """
        manager = ThreadPoolManager()
        return manager._executor.submit(fn, *args, **kwargs)

    @staticmethod
    def shutdown(wait: bool = True) -> None:
        """
        用途：关闭全局线程池。通常在后端应用停止时调用。
        入参说明：
            wait (bool): 是否等待所有任务完成后再关闭。
        返回值说明：无
        """
        if ThreadPoolManager._executor:
            ThreadPoolManager._executor.shutdown(wait=wait)
