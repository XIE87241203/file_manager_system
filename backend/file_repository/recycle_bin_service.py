from typing import List, Optional

from backend.common.base_async_service import BaseAsyncService
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.common.thread_pool import ThreadPoolManager
from backend.db.db_operations import DBOperations
from backend.file_repository.base_file_service import BaseFileService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.pagination_result import PaginationResult


class RecycleBinService(BaseAsyncService):
    """
    用途说明：回收站专项服务类，负责回收站文件的查询、恢复、彻底删除及清空逻辑。继承自 BaseAsyncService 以支持标准的异步任务控制。
    """

    @classmethod
    def init_task(cls, params: Optional[List[str]]) -> Optional[List[str]]:
        """
        用途说明：初始化删除任务。校验运行状态并重置进度条。
        入参说明：
            params (Optional[List[str]]): 指定要删除的文件路径列表。None 表示清空回收站。
        返回值说明：Optional[List[str]] - 传递给后续任务的删除路径列表。
        """
        if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            LogUtils.error("批量删除任务已在运行中，拒绝初始化")
            raise RuntimeError("批量删除任务已在运行中")

        cls._progress_manager.set_status(ProgressStatus.PROCESSING)
        cls._progress_manager.set_stop_flag(False)
        msg: str = "正在准备删除任务..." if params else "正在准备清空回收站..."
        cls._progress_manager.reset_progress(message=msg)
        
        return params

    @classmethod
    def stop_task(cls) -> None:
        """
        用途说明：请求停止当前正在进行的删除任务。
        入参说明：无
        返回值说明：无
        """
        if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            cls._progress_manager.set_stop_flag(True)
            LogUtils.info("用户请求停止删除任务，已设置停止标志位")

    @classmethod
    def start_task(cls, file_paths: Optional[List[str]] = None) -> bool:
        """
        用途说明：异步启动批量删除任务。
        入参说明：
            file_paths (Optional[List[str]]): 指定要删除的文件路径列表。None 表示清空回收站。
        返回值说明：bool: 是否成功启动任务。
        """
        try:
            params = cls.init_task(file_paths)
            ThreadPoolManager.submit(cls._internal_delete, params)
            LogUtils.info(f"异步删除任务已提交 (指定路径数: {len(params) if params else 'ALL'})")
            return True
        except Exception as e:
            LogUtils.error(f"启动删除任务失败: {e}")
            return False

    @staticmethod
    def get_recycle_bin_list(page: int, limit: int, sort_by: str, order_asc: bool, search_query: str) -> PaginationResult[FileIndexDBModel]:
        """
        用途说明：分页获取回收站中的文件列表。
        入参说明：
            page (int): 当前页码。
            limit (int): 每页限制数量。
            sort_by (str): 排序字段。
            order_asc (bool): 是否升序。
            search_query (str): 搜索关键词。
        返回值说明：PaginationResult[FileIndexDBModel] - 分页结果对象。
        """
        return DBOperations.search_file_index_list(page, limit, sort_by, order_asc, search_query, is_in_recycle_bin=True)

    @staticmethod
    def batch_move_to_recycle_bin(file_paths: List[str]) -> bool:
        """
        用途说明：批量将指定文件移入回收站标记状态。
        入参说明：file_paths (List[str]): 文件路径列表。
        返回值说明：bool: 操作是否成功。
        """
        try:
            return DBOperations.batch_move_to_recycle_bin(file_paths)
        except Exception as e:
            LogUtils.error(f"批量移入回收站失败: {e}")
            return False

    @staticmethod
    def batch_restore_from_recycle_bin(file_paths: List[str]) -> bool:
        """
        用途说明：批量将文件从回收站状态恢复。
        入参说明：file_paths (List[str]): 文件路径列表。
        返回值说明：bool: 操作是否成功。
        """
        try:
            return DBOperations.batch_restore_from_recycle_bin(file_paths)
        except Exception as e:
            LogUtils.error(f"批量恢复文件失败: {e}")
            return False

    @classmethod
    def _internal_delete(cls, file_paths_to_delete: Optional[List[str]] = None) -> None:
        """
        用途说明：执行物理删除的内部实现逻辑，增加了对停止标志位的检测。
        入参说明：file_paths_to_delete (Optional[List[str]]): 要删除的文件列表。
        """
        try:
            total_deleted: int = 0
            
            if file_paths_to_delete is not None:
                # 情况 A：指定了文件列表（批量删除）
                total_to_delete: int = len(file_paths_to_delete)
                if total_to_delete == 0:
                    cls._progress_manager.set_status(ProgressStatus.IDLE)
                    return

                cls._progress_manager.update_progress(total=total_to_delete, current=0, message=f"准备删除 {total_to_delete} 个文件...")
                
                for path in file_paths_to_delete:
                    if cls._progress_manager.is_stopped():
                        LogUtils.info("删除任务已由用户手动停止")
                        break
                        
                    success, _ = BaseFileService.delete_file(path)
                    if success:
                        total_deleted += 1
                    
                    if total_deleted % 10 == 0 or total_deleted == total_to_delete:
                        cls._progress_manager.update_progress(
                            current=total_deleted, 
                            message=f"正在删除文件: {total_deleted}/{total_to_delete}"
                        )
                msg: str = f"批量删除完成，共计删除 {total_deleted} 个文件"
            else:
                # 情况 B：未指定文件列表（清空回收站）
                limit: int = 100
                initial_res = DBOperations.search_file_index_list(1, limit, "file_path", True, "", is_in_recycle_bin=True)
                total_to_delete = initial_res.total
                
                if total_to_delete == 0:
                    cls._progress_manager.set_status(ProgressStatus.IDLE)
                    cls._progress_manager.update_progress(message="回收站本就是空的哦")
                    return

                cls._progress_manager.update_progress(total=total_to_delete, current=0, message=f"准备清空回收站，共 {total_to_delete} 个文件...")

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
                                message=f"正在清空回收站: {total_deleted}/{total_to_delete}"
                            )
                    
                    if len(batch_paths) < limit:
                        break
                msg = f"回收站已彻底清空，共计删除 {total_deleted} 个实体及其记录"

            if cls._progress_manager.is_stopped():
                msg = f"任务已停止。已处理: {total_deleted}"
                cls._progress_manager.set_status(ProgressStatus.IDLE)
                cls._progress_manager.set_stop_flag(False)
            else:
                cls._progress_manager.set_status(ProgressStatus.IDLE)
            
            cls._progress_manager.update_progress(message=msg)
            LogUtils.info(msg)
            
        except Exception as e:
            LogUtils.error(f"执行删除任务时发生崩溃: {e}")
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=f"操作失败: {str(e)}")

    @classmethod
    def clear_recycle_bin(cls, file_paths: Optional[List[str]] = None) -> bool:
        """
        用途说明：(旧接口兼容) 彻底清空回收站。
        返回值说明：bool: 是否成功触发任务。
        """
        return cls.start_task(file_paths)
