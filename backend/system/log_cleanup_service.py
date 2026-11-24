from datetime import date
from typing import Optional

from backend.common.heartbeat_service import HeartbeatService
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.timezone_utils import TimezoneUtils
from backend.setting.setting_service import settingService
from backend.system.system_service import SystemService


class LogCleanupService:
    """
    用途说明：日志自动清理服务，每天 12:00（系统设置时区）清理超过保留天数的日志文件。
    """

    # 心跳任务名称
    TASK_NAME: str = "log_cleanup_task"
    # 每日执行小时（系统设置时区）
    CLEANUP_HOUR: int = 12

    _registered: bool = False
    _last_run_date: Optional[date] = None

    @classmethod
    def start(cls) -> None:
        """
        用途说明：注册日志清理心跳任务（重复调用不会重复注册）。
        入参说明：无
        返回值说明：无
        """
        if cls._registered:
            return
        cls._registered = True
        HeartbeatService.register_task(cls.TASK_NAME, cls._on_heartbeat)
        LogUtils.info(t('sys_log_cleanup_scheduler_started', hour=cls.CLEANUP_HOUR))

    @classmethod
    def _on_heartbeat(cls) -> None:
        """
        用途说明：心跳回调，在系统设置时区的 12 点时段内当天首次触发时执行一次清理。
        入参说明：无
        返回值说明：无
        """
        now = TimezoneUtils.now()
        if now.hour != cls.CLEANUP_HOUR:
            return
        if cls._last_run_date == now.date():
            return

        # 先标记当天已执行，避免清理异常时心跳每秒重复触发
        cls._last_run_date = now.date()
        cls.run_cleanup()

    @classmethod
    def run_cleanup(cls) -> None:
        """
        用途说明：读取当前日志保留配置并执行过期日志清理，异常仅记录日志不影响心跳。
        入参说明：无
        返回值说明：无
        """
        try:
            retention_days: Optional[int] = settingService.get_config().log_management.retention_days
            SystemService.cleanup_expired_logs(retention_days)
        except Exception as e:
            LogUtils.error(t('sys_log_cleanup_task_error', error=str(e)))