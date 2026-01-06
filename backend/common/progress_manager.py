import threading
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from enum import Enum

class ProgressStatus(Enum):
    """
    用途：进度状态枚举类。
    """
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class ProgressInfo:
    """
    用途：统一的进度信息数据类。
    入参说明：
        total (int) - 总任务数。
        current (int) - 当前已完成的任务数。
        message (str) - 进度描述文本或当前处理的文件名。
    返回值说明：无
    """
    total: int = 0
    current: int = 0
    message: str = ""

class ProgressManager:
    """
    用途：通用的异步任务进度管理类，提供线程安全的状态、进度和停止标志管理。
    """
    def __init__(self, initial_status: ProgressStatus = ProgressStatus.IDLE):
        """
        用途：初始化 ProgressManager。
        入参说明：
            initial_status (ProgressStatus) - 初始状态枚举。
        返回值说明：无
        """
        self._status: ProgressStatus = initial_status  # 任务状态枚举
        self._progress: ProgressInfo = ProgressInfo()  # 进度信息
        self._stop_flag: bool = False  # 任务控制标志位
        self._lock: threading.Lock = threading.Lock()  # 锁，保证状态更新的线程安全

    def get_status(self) -> Dict[str, Any]:
        """
        用途：获取当前任务状态和进度信息。
        入参说明：无
        返回值说明：Dict[str, Any] - 包含 status (状态字符串) 和 progress (进度详情) 的字典。
        """
        with self._lock:
            return {
                "status": self._status.value,
                "progress": asdict(self._progress)
            }

    def set_status(self, status: ProgressStatus) -> None:
        """
        用途：设置当前任务的状态。
        入参说明：
            status (ProgressStatus) - 目标状态枚举。
        返回值说明：无
        """
        with self._lock:
            self._status = status

    def update_progress(self, current: Optional[int] = None, total: Optional[int] = None,
                        message: Optional[str] = None) -> None:
        """
        用途：更新任务的进度信息（线程安全）。
        入参说明：
            current (int, optional) - 当前完成的任务数。
            total (int, optional) - 总任务数。
            message (str, optional) - 进度描述文本。
        返回值说明：无
        """
        with self._lock:
            if current is not None:
                self._progress.current = current
            if total is not None:
                self._progress.total = total
            if message is not None:
                self._progress.message = message

    def reset_progress(self, message: str = "", total: int = 0) -> None:
        """
        用途：重置进度信息。
        入参说明：
            message (str) - 初始进度消息。
            total (int) - 初始总数。
        返回值说明：无
        """
        with self._lock:
            self._progress = ProgressInfo(total=total, current=0, message=message)

    def is_stopped(self) -> bool:
        """
        用途：检查停止标志位（线程安全）。
        入参说明：无
        返回值说明：bool - 是否已请求停止。
        """
        with self._lock:
            return self._stop_flag

    def set_stop_flag(self, value: bool) -> None:
        """
        用途：设置停止标志位（线程安全）。
        入参说明：
            value (bool) - 停止标志的布尔值。
        返回值说明：无
        """
        with self._lock:
            self._stop_flag = value

    def get_raw_progress_info(self) -> ProgressInfo:
        """
        用途：获取原始的进度信息对象。
        入参说明：无
        返回值说明：ProgressInfo - 原始进度信息对象。
        """
        with self._lock:
            return self._progress

    def get_raw_status(self) -> ProgressStatus:
        """
        用途：获取原始状态枚举。
        入参说明：无
        返回值说明：ProgressStatus - 原始状态枚举。
        """
        with self._lock:
            return self._status
