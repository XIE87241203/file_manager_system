from typing import List, Optional

from backend.common.base_async_service import BaseAsyncService
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.db.db_operations import DBOperations
from backend.file_repository.base_file_service import BaseFileService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.pagination_result import PaginationResult


class RecycleBinService(BaseAsyncService):
    """
    用途说明：回收站专项服务类，负责回收站文件的查询、恢复、彻底删除及清空逻辑。继承自 BaseAsyncService 以支持标准的异步任务控制。
    """

    @classmethod
    def start_batch_delete_task(cls, file_paths: Optional[List[str]] = None) -> bool:
        """
        用途说明：启动异步批量删除任务（或清空回收站）。包含初始化状态校验、进度重置及提交线程池逻辑。
        入参说明：
            file_paths (Optional[List[str]]): 指定要删除的文件路径列表。None 表示清空回收站。
        返回值说明：bool: 是否成功启动任务。
        """
        try:
            # --- 初始化逻辑开始 ---
            if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
                LogUtils.error(t('repo_delete_running'))
                raise RuntimeError(t('repo_delete_running'))

            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            msg: str = t('repo_delete_preparing') if file_paths else t('repo_recycle_clear_preparing')
            cls._progress_manager.reset_progress(message=msg)
            # --- 初始化逻辑结束 ---

            # 使用基类的私有方法启动删除任务
            return cls._start_task(cls._internal_delete, file_paths)
        except Exception as e:
            LogUtils.error(t('repo_delete_start_failed', error=str(e)))
            return False

    @staticmethod
    def get_recycle_bin_list(page: int, limit: int, sort_by: str, order_asc: bool, search_query: str) -> PaginationResult[FileIndexDBModel]:
        """
        用途说明：分页获取回收站中的文件列表。
        """
        return DBOperations.search_file_index_list(page, limit, sort_by, order_asc, search_query, is_in_recycle_bin=True)

    @staticmethod
    def batch_move_to_recycle_bin(file_paths: List[str]) -> bool:
        """
        用途说明：批量将指定文件移入回收站标记状态。
        """
        try:
            return DBOperations.batch_move_to_recycle_bin(file_paths)
        except Exception as e:
            LogUtils.error(t('repo_clear_error', error=str(e)))
            return False

    @staticmethod
    def batch_restore_from_recycle_bin(file_paths: List[str]) -> bool:
        """
        用途说明：批量将文件从回收站状态恢复。
        """
        try:
            return DBOperations.batch_restore_from_recycle_bin(file_paths)
        except Exception as e:
            LogUtils.error(t('repo_clear_error', error=str(e)))
            return False

    @classmethod
    def _internal_delete(cls, file_paths_to_delete: Optional[List[str]] = None) -> None:
        """
        用途说明：执行物理删除的内部实现逻辑，增加了对停止标志位的检测。
        """
        try:
            total_deleted: int = 0
            
            if file_paths_to_delete is not None:
                # 情况 A：指定了文件列表（批量删除）
                total_to_delete: int = len(file_paths_to_delete)
                if total_to_delete == 0:
                    cls._progress_manager.set_status(ProgressStatus.IDLE)
                    return

                cls._progress_manager.update_progress(total=total_to_delete, current=0, message=t('repo_delete_ready', count=total_to_delete))
                
                for path in file_paths_to_delete:
                    if cls._progress_manager.is_stopped():
                        LogUtils.info(t('repo_task_stopped_log', count=total_deleted))
                        break
                        
                    success, _ = BaseFileService.delete_file(path)
                    if success:
                        total_deleted += 1
                    
                    if total_deleted % 10 == 0 or total_deleted == total_to_delete:
                        cls._progress_manager.update_progress(
                            current=total_deleted, 
                            message=t('repo_deleting_progress', current=total_deleted, total=total_to_delete)
                        )
                msg: str = t('repo_delete_batch_done', count=total_deleted)
            else:
                # 情况 B：未指定文件列表（清空回收站）
                limit: int = 100
                initial_res = DBOperations.search_file_index_list(1, limit, "file_path", True, "", is_in_recycle_bin=True)
                total_to_delete = initial_res.total
                
                if total_to_delete == 0:
                    cls._progress_manager.set_status(ProgressStatus.IDLE)
                    cls._progress_manager.update_progress(message=t('repo_recycle_empty'))
                    return

                cls._progress_manager.update_progress(total=total_to_delete, current=0, message=t('repo_recycle_clear_ready', count=total_to_delete))

                while not cls._progress_manager.is_stopped():
                    res = DBOperations.search_file_index_list(1, limit, "file_path", True, "", is_in_recycle_bin=True)
                    batch_paths: List[str] = [f.file_path for f in res.list]
                    
                    if not batch_paths:
                        break

                    for path in batch_paths:
                        if cls._progress_manager.is_stopped():
                            break
                        success, _ = BaseFileService.delete_file(path)
                        if success:
                            total_deleted += 1
                        
                        if total_deleted % 10 == 0 or total_deleted == total_to_delete:
                            cls._progress_manager.update_progress(
                                current=total_deleted, 
                                message=t('repo_recycle_clearing_progress', current=total_deleted, total=total_to_delete)
                            )
                    
                    if len(batch_paths) < limit:
                        break
                msg = t('repo_recycle_clear_done', count=total_deleted)

            if cls._progress_manager.is_stopped():
                msg = t('repo_task_stopped_log', count=total_deleted)
                cls._progress_manager.set_status(ProgressStatus.IDLE)
                cls._progress_manager.set_stop_flag(False)
            else:
                cls._progress_manager.set_status(ProgressStatus.IDLE)
            
            cls._progress_manager.update_progress(message=msg)
            LogUtils.info(msg)
            
        except Exception as e:
            LogUtils.error(t('repo_delete_crash', error=str(e)))
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=t('operation_failed', error=str(e)))
