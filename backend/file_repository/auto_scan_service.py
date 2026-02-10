import schedule

from backend.common.heartbeat_service import HeartbeatService
from backend.common.log_utils import LogUtils
from backend.file_repository.scan_service import ScanService, ScanMode
from backend.setting.setting_models import FileRepositorySettings
from backend.setting.setting_service import settingService


class AutoScanService:
    """
    用途：后台定时任务服务，负责根据配置自动执行文件扫描。
    通过注册到全局 HeartbeatService 实现定时检查。
    """
    _current_time_str: str = ""
    TASK_NAME: str = "scheduler_scan_task"

    @classmethod
    def _trigger_scan(cls) -> None:
        """
        用途说明：触发扫描的具体执行逻辑。
        入参说明：无
        返回值说明：无
        """
        LogUtils.info("定时任务：到达自动刷新时间，准备开始增量扫描...")
        success: bool = ScanService.start_scan_task(ScanMode.INDEX_SCAN)
        if success:
            LogUtils.info("定时任务：扫描任务已成功启动")
        else:
            LogUtils.error("定时任务：启动扫描任务失败（可能已有任务在运行）")

    @classmethod
    def refresh_config(cls) -> None:
        """
        用途说明：根据最新配置刷新或重置定时扫描任务，并控制其在心跳服务中的注册状态。
        入参说明：无
        返回值说明：无
        """
        try:
            # 获取最新配置
            config: FileRepositorySettings = settingService.get_config().file_repository

            # 先清除旧任务，避免重复或残留
            schedule.clear('auto_scan')

            if config.auto_refresh_enabled:
                target_time: str = config.auto_refresh_time
                schedule.every().day.at(target_time).do(cls._trigger_scan).tag('auto_scan')
                cls._current_time_str = target_time
                LogUtils.info(f"已更新定时扫描任务配置：每天 {target_time}")
                
                # 注册到心跳服务
                HeartbeatService.register_task(cls.TASK_NAME, cls._on_heartbeat)
            else:
                cls._current_time_str = ""
                LogUtils.info("定时扫描配置已关闭，准备从心跳服务中反注册")
                # 从心跳服务中反注册
                HeartbeatService.unregister_task(cls.TASK_NAME)

        except Exception as e:
            LogUtils.error(f"刷新定时任务配置异常: {e}")

    @classmethod
    def _on_heartbeat(cls) -> None:
        """
        用途说明：心跳服务每秒调用的回调函数，用于驱动 schedule 检查待执行任务。
        入参说明：无
        返回值说明：无
        """
        try:
            schedule.run_pending()
        except Exception as e:
            LogUtils.error(f"定时任务调度检查异常: {e}")
