import sqlite3
from dataclasses import dataclass
from typing import Optional, List

from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.pagination_result import PaginationResult



class HistoryFileIndexProcessor(BaseDBProcessor):
    """
    用途：历史文件索引数据库处理器，负责 history_file_index 表的结构维护及相关操作
    """

    # 表名
    TABLE_NAME = 'history_file_index'

    # 列名常量
    COL_ID = 'id'
    COL_FILE_PATH = 'file_path'
    COL_FILE_MD5 = 'file_md5'
    COL_FILE_SIZE = 'file_size'
    COL_SCAN_TIME = 'scan_time'
    COL_DELETE_TIME = 'delete_time'

    def create_table(self, conn: sqlite3.Connection) -> None:
        """
        用途：创建文件索引历史表，
        入参说明：
            conn: sqlite3.Connection 数据库连接对象
        返回值说明：无
        """
        cursor = conn.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                {self.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self.COL_FILE_PATH} TEXT NOT NULL UNIQUE,
                {self.COL_FILE_MD5} TEXT NOT NULL UNIQUE,
                {self.COL_FILE_SIZE} INTEGER DEFAULT 0,
                {self.COL_SCAN_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP,
                {self.COL_DELETE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

    @staticmethod
    def batch_insert_data(data_list: List[HistoryFileIndexDBModule]) -> int:
        """
        用途：批量插入历史文件索引数据
        入参说明：
            data_list (List[HistoryFileIndex]): 待插入的历史文件索引对象列表
        返回值说明：
            int: 成功插入的行数
        """
        if not data_list:
            return 0
        # 准备数据元组列表
        data = [
            (
                item.file_path,
                item.file_md5,
                item.file_size,
                item.scan_time,
            )
            for item in data_list
        ]

        query = f'''
            INSERT OR IGNORE INTO {HistoryFileIndexProcessor.TABLE_NAME} (
                {HistoryFileIndexProcessor.COL_FILE_PATH},
                {HistoryFileIndexProcessor.COL_FILE_MD5},
                {HistoryFileIndexProcessor.COL_FILE_SIZE},
                {HistoryFileIndexProcessor.COL_SCAN_TIME},
                {HistoryFileIndexProcessor.COL_DELETE_TIME}
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''

        return BaseDBProcessor._execute_batch(query, data)

    @staticmethod
    def clear_all_table() -> bool:
        return BaseDBProcessor._clear_table(HistoryFileIndexProcessor.TABLE_NAME)

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
            PaginationResult[HistoryFileIndex]: 包含 total, list, page, limit 等分页信息的对象
        """
        allowed_cols = [
            HistoryFileIndexProcessor.COL_ID,
            HistoryFileIndexProcessor.COL_FILE_PATH,
            HistoryFileIndexProcessor.COL_FILE_MD5,
            HistoryFileIndexProcessor.COL_FILE_SIZE,
            HistoryFileIndexProcessor.COL_SCAN_TIME,
            HistoryFileIndexProcessor.COL_DELETE_TIME
        ]
        
        return BaseDBProcessor._search_paged_list(
            table_name=HistoryFileIndexProcessor.TABLE_NAME,
            model_class=HistoryFileIndexDBModule,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            search_query=search_query,
            search_column=HistoryFileIndexProcessor.COL_FILE_PATH,
            allowed_sort_columns=allowed_cols,
            default_sort_column=HistoryFileIndexProcessor.COL_DELETE_TIME
        )
