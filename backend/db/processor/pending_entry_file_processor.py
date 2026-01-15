import sqlite3
from typing import Optional, List

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.pending_entry_file_db_model import PendingEntryFileDBModel
from backend.model.pagination_result import PaginationResult


class PendingEntryFileProcessor(BaseDBProcessor):
    """
    用途说明：待录入文件库数据库处理器，负责 pending_entry_file 表的相关 CRUD 操作。
    """

    @staticmethod
    def add_pending_entry_files(file_names: List[str], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量添加待录入文件名。
        入参说明：
            file_names (List[str]): 待添加的文件名列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回成功插入的条数。
        """
        if not file_names:
            return 0
        
        query: str = f'''
            INSERT OR IGNORE INTO {DBConstants.PendingEntryFile.TABLE_NAME} (
                {DBConstants.PendingEntryFile.COL_FILE_NAME}
            )
            VALUES (?)
        '''
        data = [(name,) for name in file_names]
        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def batch_delete_pending_entry_files(file_ids: List[int], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量删除指定的待录入文件记录。
        入参说明：
            file_ids (List[int]): 记录 ID 列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：成功删除的条数。
        """
        if not file_ids:
            return 0
        query: str = f"DELETE FROM {DBConstants.PendingEntryFile.TABLE_NAME} WHERE {DBConstants.PendingEntryFile.COL_ID} = ?"
        data = [(f_id,) for f_id in file_ids]
        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def get_paged_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[PendingEntryFileDBModel]:
        """
        用途说明：分页搜索待录入文件列表。
        """
        allowed_cols: List[str] = [
            DBConstants.PendingEntryFile.COL_ID,
            DBConstants.PendingEntryFile.COL_FILE_NAME,
            DBConstants.PendingEntryFile.COL_ADD_TIME
        ]
        
        return BaseDBProcessor._search_paged_list(
            table_name=DBConstants.PendingEntryFile.TABLE_NAME,
            model_class=PendingEntryFileDBModel,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            search_query=search_query,
            search_column=DBConstants.PendingEntryFile.COL_FILE_NAME,
            allowed_sort_columns=allowed_cols,
            default_sort_column=DBConstants.PendingEntryFile.COL_ADD_TIME
        )

    @staticmethod
    def clear_all_table() -> bool:
        """
        用途说明：清空待录入文件表。
        """
        return BaseDBProcessor._clear_table(DBConstants.PendingEntryFile.TABLE_NAME)
