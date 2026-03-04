from typing import Any, List, Optional

from backend.common.base_async_service import BaseAsyncService
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.duplicate_check.duplicate_check_helper import DuplicateCheckHelper
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.duplicate_group_result import DuplicateGroupResult
from backend.model.pagination_result import PaginationResult


class DuplicateService(BaseAsyncService):
    """
    用途：文件查重服务类，支持异步查重、进度查询、任务停止以及结果查询。
    继承自 BaseAsyncService 以支持标准的异步任务控制。
    """

    @classmethod
    def init_service(cls) -> None:
        """
        用途：初始化服务状态，检测数据库中是否已存在查重数据。
        如果存在，则将进度管理器初始化为“已完成”状态。
        """
        try:
            count: int = DBOperations.get_duplicate_group_count()
            if count > 0:
                cls._progress_manager.set_status(ProgressStatus.COMPLETED)
                cls._progress_manager.update_progress(
                    current=1,
                    total=1,
                    message=t('dup_found_count', count=count)
                )
                LogUtils.info(t('dup_init_log', count=count))
        except Exception as e:
            LogUtils.error(t('dup_init_failed', error=str(e)))

    @classmethod
    def start_duplicate_check_task(cls) -> bool:
        """
        用途说明：启动异步查重任务。包含初始化检查、清空旧数据及提交线程池逻辑。
        入参说明：params: 预留参数。
        返回值说明：bool: 是否成功启动。
        """
        try:
            # --- 初始化逻辑开始 ---
            if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
                LogUtils.error(t('dup_task_running'))
                raise RuntimeError(t('dup_task_running'))

            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            cls._progress_manager.reset_progress(message=t('dup_initializing'))

            # 清空旧的重复数据
            DBOperations.clear_duplicate_results()
            # --- 初始化逻辑结束 ---

            # 使用基类的私有方法提交任务
            return cls._start_task(cls._internal_check)
        except Exception as e:
            LogUtils.error(t('dup_start_failed', error=str(e)))
            return False

    @classmethod
    def _complete_check(cls, results: List[Any], status_text: str) -> None:
        """
        用途：完成查重任务，将结果保存至数据库并更新最终状态。
        """
        DBOperations.save_duplicate_results(results)

        cls._progress_manager.set_status(ProgressStatus.COMPLETED)
        current_info = cls._progress_manager.get_raw_progress_info()
        cls._progress_manager.update_progress(
            current=current_info.total,
            message=status_text
        )
        LogUtils.info(status_text)

    @classmethod
    def _internal_check(cls) -> None:
        """
        用途：内部查重逻辑，在独立线程中执行耗时扫描。
        """
        try:
            LogUtils.info(t('dup_internal_check_start'))

            total_files: int = DBOperations.get_file_index_count()
            if total_files == 0:
                cls._complete_check([], t('dup_no_files'))
                return

            cls._progress_manager.update_progress(
                total=total_files,
                message=t('dup_preparing')
            )

            helper: DuplicateCheckHelper = DuplicateCheckHelper()
            batch_size: int = 500
            processed_count: int = 0
            current_processed: int = 0

            while processed_count < total_files:
                if cls._progress_manager.is_stopped():
                    cls._handle_stopped()
                    return

                files: List[FileIndexDBModel] = DBOperations.get_file_index_list_by_condition(
                    limit=batch_size,
                    offset=processed_count,
                    only_no_thumbnail=False
                )

                if not files:
                    break

                for file_info in files:
                    if cls._progress_manager.is_stopped():
                        cls._handle_stopped()
                        return
                    
                    current_processed += 1
                    file_name: str = Utils.get_filename(file_info.file_path)
                    cls._progress_manager.update_progress(
                        current=current_processed,
                        total=total_files,
                        message=t('dup_analyzing', file_name=file_name)
                    )
                    helper.add_file(file_info)

                processed_count += batch_size

            if cls._progress_manager.is_stopped():
                cls._handle_stopped()
                return

            cls._progress_manager.update_progress(message=t('dup_generating_report'))
            results: List[Any] = helper.get_all_results()
            cls._complete_check(results, t('dup_found_count', count=len(results)))

        except Exception as e:
            LogUtils.error(t('dup_async_error', error=str(e)))
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=t('dup_failed', error=str(e)))

    @classmethod
    def _handle_stopped(cls) -> None:
        """
        用途：处理查重任务被手动停止时的状态重设。
        """
        cls._progress_manager.set_status(ProgressStatus.IDLE)
        cls._progress_manager.set_stop_flag(False)
        cls._progress_manager.update_progress(message=t('user_stop_task'))
        LogUtils.info(t('dup_stop_ack'))

    @staticmethod
    def get_all_duplicate_results(page: int, limit: int, similarity_type: Optional[str] = None) -> PaginationResult[DuplicateGroupResult]:
        """
        用途：分页获取所有查重结果分组，支持按相似度类型筛选。
        """
        from backend.db.processor_manager import processor_manager
        return processor_manager.duplicate_group_processor.get_duplicate_groups_paged(page, limit, similarity_type)

    @staticmethod
    def get_latest_check_time() -> Optional[str]:
        """
        用途说明：获取最近一次查重的完成时间。
        返回值说明：Optional[str]: 格式化后的时间字符串。
        """
        return DBOperations.get_latest_duplicate_check_time()


# 在模块加载时执行初始化
DuplicateService.init_service()
