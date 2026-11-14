import schedule

from typing import Dict, Any

from backend.common.heartbeat_service import HeartbeatService
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import set_current_repo_id
from backend.file_repository.scan_service import ScanService, ScanMode
from backend.repository.repository_service import repositoryService
from backend.setting.setting_models import FileRepositorySettings


class AutoScanService:
    """
    用途：后台定时任务服务，按仓库独立调度自动扫描。
    每个仓库依据自身配置的自动刷新开关与时间注册定时任务，通过全局 HeartbeatService 驱动。
    """
    TASK_NAME: str = "scheduler_scan_task"
    COMMON_TAG: str = "auto_scan"

    @classmethod
    def _trigger_scan_for_repo(cls, repo_id: int) -> None:
        """
        用途说明：在指定仓库上下文中触发扫描，并在扫描完成后按配置决定是否执行自动新增查重。
        入参说明：repo_id (int): 仓库 ID。
        返回值说明：无
        """
        set_current_repo_id(repo_id)
        LogUtils.info(t('repo_auto_scan_trigger'))

        def _on_scan_complete() -> None:
            """
            用途说明：自动刷新完成回调，读取仓库配置，若启用自动新增查重则触发增量查重。
            入参说明：无
            返回值说明：无
            """
            set_current_repo_id(repo_id)
            config: FileRepositorySettings = repositoryService.get_config(repo_id)
            if not config.auto_duplicate_check_enabled:
                return
            from backend.file_repository.duplicate_check.duplicate_service import DuplicateService
            LogUtils.info(t('repo_auto_dup_trigger'))
            if DuplicateService.start_duplicate_check_task('incremental'):
                LogUtils.info(t('repo_auto_dup_success'))
            else:
                LogUtils.error(t('repo_auto_dup_failed'))

        success: bool = ScanService.start_scan_task(ScanMode.INDEX_SCAN, on_complete=_on_scan_complete)
        if success:
            LogUtils.info(t('repo_auto_scan_success'))
        else:
            LogUtils.error(t('repo_auto_scan_failed'))

    @classmethod
    def refresh_config(cls) -> None:
        """
        用途说明：遍历所有仓库，按各自配置重建定时扫描任务，并控制心跳服务注册状态。
        入参说明：无
        返回值说明：无
        """
        try:
            # 先清除所有旧的自动扫描任务，避免重复或残留
            schedule.clear(cls.COMMON_TAG)

            any_enabled: bool = False
            for repo in repositoryService.list_repos():
                config: FileRepositorySettings = repositoryService.get_config(repo.id)
                if config.auto_refresh_enabled:
                    any_enabled = True
                    target_time: str = config.auto_refresh_time
                    schedule.every().day.at(target_time).do(
                        cls._trigger_scan_for_repo, repo.id
                    ).tag(cls.COMMON_TAG, f"auto_scan_repo_{repo.id}")
                    LogUtils.info(t('repo_auto_scan_updated', time=target_time))

            if any_enabled:
                HeartbeatService.register_task(cls.TASK_NAME, cls._on_heartbeat)
            else:
                LogUtils.info(t('repo_auto_scan_disabled'))
                HeartbeatService.unregister_task(cls.TASK_NAME)

        except Exception as e:
            LogUtils.error(t('repo_auto_scan_config_error', error=str(e)))

    @classmethod
    def on_config_changed(cls, data: Dict[str, Any]) -> None:
        """
        用途说明：全局配置变更观察者回调（兼容旧入口），涉及文件仓库自动刷新配置时重建调度。
        入参说明：data (Dict[str, Any]): 本次更新的配置字典。
        返回值说明：无
        """
        file_repo_data = data.get('file_repository')
        if isinstance(file_repo_data, dict):
            if 'auto_refresh_time' in file_repo_data or 'auto_refresh_enabled' in file_repo_data:
                cls.refresh_config()

    @classmethod
    def on_repo_config_changed(cls, repo_id: int, data: Dict[str, Any]) -> None:
        """
        用途说明：仓库独立配置变更观察者回调，自动刷新相关字段变化时重建调度。
        入参说明：
            repo_id (int): 仓库 ID。
            data (Dict[str, Any]): 本次更新的配置字段字典。
        返回值说明：无
        """
        if 'auto_refresh_time' in data or 'auto_refresh_enabled' in data:
            cls.refresh_config()

    @classmethod
    def on_repo_deleted(cls, repo_id: int) -> None:
        """
        用途说明：仓库删除观察者回调，重建调度以移除被删除仓库的定时任务。
        入参说明：repo_id (int): 被删除的仓库 ID。
        返回值说明：无
        """
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