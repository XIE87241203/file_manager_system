import sqlite3
from typing import List

from backend.common.log_utils import LogUtils
from backend.db.db_manager import db_manager
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModule


class DuplicateGroupDBModuleProcessor(BaseDBProcessor):
    """
    用途：重复文件分组数据库处理器，负责 duplicate_groups 和 duplicate_files 表的结构维护及相关操作
    """

    # 表名
    TABLE_GROUPS = 'duplicate_groups'
    TABLE_FILES = 'duplicate_files'

    # 分组表列名常量
    COL_GRP_ID_PK = 'id'
    COL_GRP_GROUP_NAME = 'group_name'

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
                {self.COL_GRP_GROUP_NAME} TEXT NOT NULL
            )
        ''')

        # 创建重复文件详情表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.TABLE_FILES} (
                {self.COL_FILE_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self.COL_FILE_GROUP_ID} INTEGER NOT NULL,
                {self.COL_FILE_ID} INTEGER NOT NULL
            )
        ''')

        conn.commit()

    @staticmethod
    def batch_save_duplicate_groups(groups: List[DuplicateGroupDBModule]) -> bool:
        """
        用途：批量存储重复文件分组及其详情
        入参说明：
            groups (List[DuplicateGroupDBModule]): 重复文件分组模型列表
        返回值说明：
            bool: 是否全部成功存储
        """
        conn = None
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()

            for group in groups:
                # 1. 插入分组并获取生成的组 ID
                cursor.execute(
                    f"INSERT INTO {DuplicateGroupDBModuleProcessor.TABLE_GROUPS} ({DuplicateGroupDBModuleProcessor.COL_GRP_GROUP_NAME}) VALUES (?)",
                    (group.group_name,)
                )
                group_id = cursor.lastrowid

                # 2. 准备该组的文件详情数据
                files_data = [(group_id, file_id) for file_id in group.file_ids]

                # 3. 批量插入该组的文件记录
                if files_data:
                    cursor.executemany(
                        f"INSERT INTO {DuplicateGroupDBModuleProcessor.TABLE_FILES} "
                        f"({DuplicateGroupDBModuleProcessor.COL_FILE_GROUP_ID}, {DuplicateGroupDBModuleProcessor.COL_FILE_ID}) "
                        f"VALUES (?, ?)",
                        files_data
                    )

            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            LogUtils.error(f"批量存储重复分组失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def delete_file_by_id(file_id: int) -> bool:
        """
        用途：根据 ID 从文件索引表中删除记录
        入参说明：
            file_id (int): 记录的唯一标识 ID
        返回值说明：
            bool: 是否删除成功（受影响行数 > 0）
        """
        query = f"DELETE FROM {DuplicateGroupDBModuleProcessor.TABLE_FILES} WHERE {DuplicateGroupDBModuleProcessor.COL_FILE_ID} = ?"
        result = BaseDBProcessor._execute(query, (file_id,))
        return bool(result and result > 0)

    @staticmethod
    def clear_all_table() -> bool:
        """
        用途：清空重复文件相关的两张表
        入参说明：无
        返回值说明：
            bool: 是否清空成功
        """
        result_clear_groups = BaseDBProcessor._clear_table(DuplicateGroupDBModuleProcessor.TABLE_GROUPS)
        result_clear_files = BaseDBProcessor._clear_table(DuplicateGroupDBModuleProcessor.TABLE_FILES)
        return result_clear_groups and result_clear_files
