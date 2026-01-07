import sqlite3
from dataclasses import dataclass
from typing import Optional
from backend.db.base_db_processor import BaseDBProcessor


@dataclass
class DuplicateGroup:
    """
    用途：重复文件分组数据类，对应 duplicate_groups 表
    """
    id: Optional[int] = None
    group_id: str = ""


@dataclass
class DuplicateFile:
    """
    用途：重复文件详情数据类，对应 duplicate_files 表
    """
    id: Optional[int] = None
    group_id: str = ""
    file_id: Optional[int] = None


class DuplicateGroupProcessor(BaseDBProcessor):
    """
    用途：重复文件分组数据库处理器，负责 duplicate_groups 和 duplicate_files 表的结构维护及相关操作
    """

    # 表名
    TABLE_GROUPS = 'duplicate_groups'
    TABLE_FILES = 'duplicate_files'

    # 分组表列名常量
    COL_GRP_ID_PK = 'id'
    COL_GRP_GROUP_ID = 'group_id'

    # 详情表列名常量
    COL_FILE_ID_PK = 'id'
    COL_FILE_GROUP_ID = 'group_id'
    COL_FILE_ID = 'file_id'

    def create_table(self, conn: sqlite3.Connection) -> None:
        """
        用途：创建重复文件分组表及详情表
            其中COL_FILE_ID对应file_index的id
        入参说明：
            conn: sqlite3.Connection 数据库连接对象
        返回值说明：无
        """
        cursor = conn.cursor()

        # 创建重复文件分组表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.TABLE_GROUPS} (
                {self.COL_GRP_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self.COL_GRP_GROUP_ID} TEXT NOT NULL UNIQUE,
            )
        ''')

        # 创建重复文件详情表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.TABLE_FILES} (
                {self.COL_FILE_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self.COL_FILE_GROUP_ID} TEXT NOT NULL,
                {self.COL_FILE_ID} INTEGER NOT NULL UNIQUE,
            )
        ''')

        conn.commit()

    @staticmethod
    def delete_file_by_id(file_id: int) -> bool:
        """
        用途：根据 ID 从文件索引表中删除记录
        入参说明：
            file_id (int): 记录的唯一标识 ID
        返回值说明：
            bool: 是否删除成功（受影响行数 > 0）
        """
        query = f"DELETE FROM {DuplicateGroupProcessor.TABLE_FILES} WHERE {DuplicateGroupProcessor.COL_FILE_ID} = ?"
        result = BaseDBProcessor._execute(query, (file_id,))
        return bool(result and result > 0)

    @staticmethod
    def clear_all_table() -> bool:
        result_clear_groups = BaseDBProcessor._clear_table(DuplicateGroupProcessor.TABLE_GROUPS)
        result_clear_files = BaseDBProcessor._clear_table(DuplicateGroupProcessor.TABLE_FILES)
        return result_clear_groups and result_clear_files
