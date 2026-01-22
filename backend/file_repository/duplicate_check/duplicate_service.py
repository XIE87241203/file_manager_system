from typing import Any, List, Optional

from backend.common.base_async_service import BaseAsyncService
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
                    message=f"查重完成，共发现 {count} 组重复文件"
                )
                LogUtils.info(f"查重服务初始化：检测到已有 {count} 组重复记录，已自动恢复进度状态")
        except Exception as e:
            LogUtils.error(f"查重服务初始化失败: {e}")

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
                LogUtils.error("查重任务已在运行中，请勿重复启动")
                raise RuntimeError("查重任务已在运行中")

            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            cls._progress_manager.reset_progress(message="正在初始化...")

            # 清空旧的重复数据
            DBOperations.clear_duplicate_results()
            # --- 初始化逻辑结束 ---

            # 使用基类的私有方法提交任务
            return cls._start_task(cls._internal_check)
        except Exception as e:
            LogUtils.error(f"启动查重任务失败: {e}")
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
            LogUtils.info("开始执行文件查重逻辑...")

            total_files: int = DBOperations.get_file_index_count()
            if total_files == 0:
                cls._complete_check([], "未发现可检查的文件")
                return

            cls._progress_manager.update_progress(
                total=total_files,
                message="正在准备分析文件..."
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
                        message=f"正在分析 ({current_processed}/{total_files}): {file_name}"
                    )
                    helper.add_file(file_info)

                processed_count += batch_size

            if cls._progress_manager.is_stopped():
                cls._handle_stopped()
                return

            cls._progress_manager.update_progress(message="正在生成查重报告，请稍候...")
            results: List[Any] = helper.get_all_results()
            cls._complete_check(results, f"查重完成，共发现 {len(results)} 组重复文件")

        except Exception as e:
            LogUtils.error(f"异步查重任务发生异常: {e}")
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=f"查重失败: {str(e)}")

    @classmethod
    def _handle_stopped(cls) -> None:
        """
        用途：处理查重任务被手动停止时的状态重设。
        """
        cls._progress_manager.set_status(ProgressStatus.IDLE)
        cls._progress_manager.set_stop_flag(False)
        cls._progress_manager.update_progress(message="任务已由用户停止")
        LogUtils.info("查重任务已手动终止并重置状态")

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
