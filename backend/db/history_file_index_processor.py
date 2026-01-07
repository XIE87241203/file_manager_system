import sqlite3
from dataclasses import dataclass
from typing import Optional, List
from backend.db.base_db_processor import BaseDBProcessor


@dataclass
class HistoryFileIndex:
    """
    用途：历史文件索引数据类，对应 history_file_index 表
    """
    id: Optional[int] = None
    file_path: str = ""
    file_md5: str = ""
    file_size: int = 0
    scan_time: Optional[str] = None
    delete_time: Optional[str] = None


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
    def batch_insert_data(data_list: List[HistoryFileIndex]) -> int:
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
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''

        return HistoryFileIndexProcessor._execute_batch(query, data)

    @staticmethod
    def clear_all_table() -> bool:
        return BaseDBProcessor._clear_table(HistoryFileIndexProcessor.TABLE_NAME)