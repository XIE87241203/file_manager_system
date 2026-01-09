from typing import List

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.pagination_result import PaginationResult


class HistoryFileIndexProcessor(BaseDBProcessor):
    """
    用途：历史文件索引数据库处理器，负责 history_file_index 表的相关操作
    """

    @staticmethod
    def batch_insert_data(data_list: List[HistoryFileIndexDBModule]) -> int:
        """
        用途：批量插入历史文件索引数据
        入参说明：
            data_list (List[HistoryFileIndexDBModule]): 待插入的历史文件索引对象列表
        返回值说明：
            int: 成功插入的行数
        """
        if not data_list:
            return 0

        # 准备数据元组列表
        data: List[tuple] = [
            (
                item.file_path,
                item.file_md5,
                item.file_size,
                item.scan_time,
            )
            for item in data_list
        ]

        query: str = f'''
            INSERT OR IGNORE INTO {DBConstants.HistoryFileIndex.TABLE_NAME} (
                {DBConstants.HistoryFileIndex.COL_FILE_PATH},
                {DBConstants.HistoryFileIndex.COL_FILE_MD5},
                {DBConstants.HistoryFileIndex.COL_FILE_SIZE},
                {DBConstants.HistoryFileIndex.COL_SCAN_TIME},
                {DBConstants.HistoryFileIndex.COL_DELETE_TIME}
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''

        return BaseDBProcessor._execute_batch(query, data)

    @staticmethod
    def copy_file_index_to_history() -> int:
        """
        用途：将 file_index 表中的所有数据通过 SQL 批量添加到 history_file_index 表中
        入参说明：无
        返回值说明：
            int: 成功插入的行数
        """
        query: str = f'''
            INSERT OR IGNORE INTO {DBConstants.HistoryFileIndex.TABLE_NAME} (
                {DBConstants.HistoryFileIndex.COL_FILE_PATH},
                {DBConstants.HistoryFileIndex.COL_FILE_MD5},
                {DBConstants.HistoryFileIndex.COL_FILE_SIZE},
                {DBConstants.HistoryFileIndex.COL_SCAN_TIME},
                {DBConstants.HistoryFileIndex.COL_DELETE_TIME}
            )
            SELECT 
                {DBConstants.FileIndex.COL_FILE_PATH},
                {DBConstants.FileIndex.COL_FILE_MD5},
                {DBConstants.FileIndex.COL_FILE_SIZE},
                {DBConstants.FileIndex.COL_SCAN_TIME},
                CURRENT_TIMESTAMP
            FROM {DBConstants.FileIndex.TABLE_NAME}
        '''
        result: int = BaseDBProcessor._execute(query)
        return result if result is not None else 0

    @staticmethod
    def clear_all_table() -> bool:
        """
        用途：清空历史文件索引表
        入参说明：无
        返回值说明：
            bool: 是否清空成功
        """
        return BaseDBProcessor._clear_table(DBConstants.HistoryFileIndex.TABLE_NAME)

    @staticmethod
    def get_paged_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[HistoryFileIndexDBModule]:
        """
        用途：分页查询历史文件索引列表，支持模糊搜索。
        入参说明：
            page (int): 当前页码
            limit (int): 每页记录数
            sort_by (str): 排序字段
            order (bool): 排序方向 (True 为 ASC, False 为 DESC)
            search_query (str): 搜索关键词
        返回值说明：
            PaginationResult[HistoryFileIndexDBModule]: 包含 total, list, page, limit 等分页信息的对象
        """
        allowed_cols: List[str] = [
            DBConstants.HistoryFileIndex.COL_ID,
            DBConstants.HistoryFileIndex.COL_FILE_PATH,
            DBConstants.HistoryFileIndex.COL_FILE_MD5,
            DBConstants.HistoryFileIndex.COL_FILE_SIZE,
            DBConstants.HistoryFileIndex.COL_SCAN_TIME,
            DBConstants.HistoryFileIndex.COL_DELETE_TIME
        ]

        return BaseDBProcessor._search_paged_list(
            table_name=DBConstants.HistoryFileIndex.TABLE_NAME,
            model_class=HistoryFileIndexDBModule,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            search_query=search_query,
            search_column=DBConstants.HistoryFileIndex.COL_FILE_PATH,
            allowed_sort_columns=allowed_cols,
            default_sort_column=DBConstants.HistoryFileIndex.COL_DELETE_TIME
        )
