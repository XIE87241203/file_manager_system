from typing import List, Optional

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.pagination_result import PaginationResult


class HistoryFileIndexProcessor(BaseDBProcessor):
    """
    用途：历史文件索引数据库处理器，负责 history_file_index 表的相关操作
    """

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
                {DBConstants.HistoryFileIndex.COL_FILE_NAME},
                {DBConstants.HistoryFileIndex.COL_FILE_MD5},
                {DBConstants.HistoryFileIndex.COL_FILE_SIZE},
                {DBConstants.HistoryFileIndex.COL_FILE_TYPE},
                {DBConstants.HistoryFileIndex.COL_VIDEO_DURATION},
                {DBConstants.HistoryFileIndex.COL_VIDEO_CODEC},
                {DBConstants.HistoryFileIndex.COL_SCAN_TIME},
                {DBConstants.HistoryFileIndex.COL_DELETE_TIME}
            )
            SELECT 
                {DBConstants.FileIndex.COL_FILE_PATH},
                {DBConstants.FileIndex.COL_FILE_NAME},
                {DBConstants.FileIndex.COL_FILE_MD5},
                {DBConstants.FileIndex.COL_FILE_SIZE},
                {DBConstants.FileIndex.COL_FILE_TYPE},
                {DBConstants.FileIndex.COL_VIDEO_DURATION},
                {DBConstants.FileIndex.COL_VIDEO_CODEC},
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
    def get_paged_list(page: int, limit: int, sort_by: str, order: bool, search_query: str, file_type: Optional[str] = None) -> PaginationResult[HistoryFileIndexDBModule]:
        """
        用途：分页查询历史文件索引列表，支持模糊搜索及文件类型筛选。
        入参说明：
            page (int): 当前页码
            limit (int): 每页记录数
            sort_by (str): 排序字段
            order (bool): 排序方向 (True 为 ASC, False 为 DESC)
            search_query (str): 搜索关键词
            file_type (Optional[str]): 文件类型筛选 (video/image/other)
        返回值说明：
            PaginationResult[HistoryFileIndexDBModule]: 包含 total, list, page, limit 等分页信息的对象
        """
        allowed_cols: List[str] = [
            DBConstants.HistoryFileIndex.COL_ID,
            DBConstants.HistoryFileIndex.COL_FILE_PATH,
            DBConstants.HistoryFileIndex.COL_FILE_NAME,
            DBConstants.HistoryFileIndex.COL_FILE_MD5,
            DBConstants.HistoryFileIndex.COL_FILE_SIZE,
            DBConstants.HistoryFileIndex.COL_FILE_TYPE,
            DBConstants.HistoryFileIndex.COL_VIDEO_DURATION,
            DBConstants.HistoryFileIndex.COL_VIDEO_CODEC,
            DBConstants.HistoryFileIndex.COL_SCAN_TIME,
            DBConstants.HistoryFileIndex.COL_DELETE_TIME
        ]

        extra_where: str = ""
        extra_params: tuple = ()
        if file_type:
            extra_where += f" AND {DBConstants.HistoryFileIndex.COL_FILE_TYPE} = ?"
            extra_params += (file_type,)

        return BaseDBProcessor._search_paged_list(
            table_name=DBConstants.HistoryFileIndex.TABLE_NAME,
            model_class=HistoryFileIndexDBModule,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            search_query=search_query,
            search_column=DBConstants.HistoryFileIndex.COL_FILE_NAME, # 改为按文件名搜索
            allowed_sort_columns=allowed_cols,
            default_sort_column=DBConstants.HistoryFileIndex.COL_DELETE_TIME,
            extra_where=extra_where,
            extra_params=extra_params
        )
