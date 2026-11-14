from datetime import datetime
from typing import Any, List, Optional, Set

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

    # 本次查重任务的开始时间，用于在完成时计算耗时
    _check_start_time: Optional[datetime] = None

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
    def start_duplicate_check_task(cls, mode: str = 'global') -> bool:
        """
        用途说明：启动异步查重任务。包含初始化检查、按模式清空旧数据及提交线程池逻辑。
        入参说明：mode (str): 查重模式，'global' 全局查重（清空重扫），'incremental' 新增查重（仅扫新文件）。
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
            cls._check_start_time = datetime.now()

            if mode == 'incremental':
                # 新增查重：保留旧结果，仅清理失效数据并扫描新索引文件
                return cls._start_task(cls._internal_incremental_check)

            # 全局查重：清空旧的重复数据后全量扫描
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
        用途：完成查重任务，将结果保存至数据库并更新最终状态及查重时间点。
        """
        DBOperations.save_duplicate_results(results)

        cls._progress_manager.set_status(ProgressStatus.COMPLETED)
        current_info = cls._progress_manager.get_raw_progress_info()
        cls._progress_manager.update_progress(
            current=current_info.total,
            message=status_text
        )
        duration: float = (datetime.now() - cls._check_start_time).total_seconds() if cls._check_start_time else 0.0
        DBOperations.set_last_check_time(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), duration)
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
    def _complete_incremental(cls, results: List[Any], new_file_paths: List[str], status_text: str) -> None:
        """
        用途：完成新增查重任务，合并保存结果并更新最终状态及查重时间点。
        """
        DBOperations.save_incremental_results(results, new_file_paths)

        cls._progress_manager.set_status(ProgressStatus.COMPLETED)
        current_info = cls._progress_manager.get_raw_progress_info()
        cls._progress_manager.update_progress(
            current=current_info.total,
            message=status_text
        )
        duration: float = (datetime.now() - cls._check_start_time).total_seconds() if cls._check_start_time else 0.0
        DBOperations.set_last_check_time(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), duration)
        LogUtils.info(status_text)

    @classmethod
    def _internal_incremental_check(cls) -> None:
        """
        用途：新增查重内部逻辑。先清理失效结果，再按查重时间点筛选新索引文件，
        仅对新文件进行特征分析，并与仓库已有文件及新文件之间比对，最后合并入库。
        """
        try:
            LogUtils.info(t('dup_incremental_check_start'))

            # 1. 清理失效的查重结果（删除已不存在文件的关联，解散成员不足 2 个的分组）
            DBOperations.self_heal_duplicate_results()

            # 2. 依据最近查重时间点筛选新索引文件
            last_check_time: Optional[str] = DBOperations.get_last_check_time()
            new_files: List[FileIndexDBModel] = DBOperations.get_files_by_scan_time(last_check_time, newer=True)
            if not new_files:
                cls._complete_incremental([], [], t('dup_no_new_files'))
                return

            total_new: int = len(new_files)
            cls._progress_manager.update_progress(total=total_new, message=t('dup_preparing'))

            helper: DuplicateCheckHelper = DuplicateCheckHelper()

            # 3. 分析新文件（计算特征）
            for index, file_info in enumerate(new_files):
                if cls._progress_manager.is_stopped():
                    cls._handle_stopped()
                    return
                file_name: str = Utils.get_filename(file_info.file_path)
                cls._progress_manager.update_progress(
                    current=index + 1,
                    total=total_new,
                    message=t('dup_analyzing', file_name=file_name)
                )
                helper.add_file(file_info)

            if cls._progress_manager.is_stopped():
                cls._handle_stopped()
                return

            # 4. 载入仓库已有文件作为比对参考（图片/视频全量，其余仅 MD5 命中者）
            cls._progress_manager.update_progress(message=t('dup_comparing_existing'))
            old_files: List[FileIndexDBModel] = DBOperations.get_files_by_scan_time(last_check_time, newer=False)
            new_md5_set: Set[str] = {f.file_md5 for f in new_files if f.file_md5}
            for file_info in old_files:
                if cls._progress_manager.is_stopped():
                    cls._handle_stopped()
                    return
                if file_info.file_type in ('image', 'video'):
                    helper.add_file(file_info)
                elif file_info.file_md5 in new_md5_set:
                    helper.add_file(file_info)

            # 5. 汇总结果并合并入库（仅统计涉及新文件的分组）
            cls._progress_manager.update_progress(message=t('dup_generating_report'))
            results: List[Any] = helper.get_all_results()
            new_file_paths: List[str] = [f.file_path for f in new_files]
            new_path_set: Set[str] = set(new_file_paths)
            found_count: int = sum(1 for g in results if any(f.file_path in new_path_set for f in g.files))
            cls._complete_incremental(results, new_file_paths, t('dup_found_count', count=found_count))

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
    def get_all_duplicate_results(page: int, limit: int, similarity_type: Optional[str] = None, file_type: Optional[str] = None) -> PaginationResult[DuplicateGroupResult]:
        """
        用途：分页获取所有查重结果分组，支持按相似度类型及文件类型筛选。
        """
        from backend.db.processor_manager import processor_manager
        return processor_manager.duplicate_group_processor.get_duplicate_groups_paged(page, limit, similarity_type, file_type)

    @staticmethod
    def get_latest_check_time() -> Optional[str]:
        """
        用途说明：获取最近一次查重的完成时间。
        返回值说明：Optional[str]: 格式化后的时间字符串。
        """
        return DBOperations.get_latest_duplicate_check_time()

    @staticmethod
    def get_last_check_duration() -> Optional[float]:
        """
        用途说明：获取最近一次查重的耗时（秒）。
        返回值说明：Optional[float]: 耗时秒数，若从未查重则返回 None。
        """
        return DBOperations.get_last_check_duration()


# 在模块加载时执行初始化
DuplicateService.init_service()
