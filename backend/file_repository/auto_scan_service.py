import schedule

from typing import Dict, Any

from backend.common.heartbeat_service import HeartbeatService
from backend.common.i18n_utils import t
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
        LogUtils.info(t('repo_auto_scan_trigger'))
        success: bool = ScanService.start_scan_task(ScanMode.INDEX_SCAN)
        if success:
            LogUtils.info(t('repo_auto_scan_success'))
        else:
            LogUtils.error(t('repo_auto_scan_failed'))

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
                LogUtils.info(t('repo_auto_scan_updated', time=target_time))
                
                # 注册到心跳服务
                HeartbeatService.register_task(cls.TASK_NAME, cls._on_heartbeat)
            else:
                cls._current_time_str = ""
                LogUtils.info(t('repo_auto_scan_disabled'))
                # 从心跳服务中反注册
                HeartbeatService.unregister_task(cls.TASK_NAME)

        except Exception as e:
            LogUtils.error(t('repo_auto_scan_config_error', error=str(e)))

    @classmethod
    def on_config_changed(cls, data: Dict[str, Any]) -> None:
        """
        用途说明：配置变更观察者回调。仅当文件仓库自动刷新相关配置发生变化时刷新定时扫描任务。
        入参说明：data (Dict[str, Any]): 本次更新的配置字典。
        返回值说明：无
        """
        file_repo_data = data.get('file_repository')
        if isinstance(file_repo_data, dict):
            if 'auto_refresh_time' in file_repo_data or 'auto_refresh_enabled' in file_repo_data:
                cls.refresh_config()

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
            LogUtils.error(t('repo_auto_scan_schedule_error', error=str(e)))
