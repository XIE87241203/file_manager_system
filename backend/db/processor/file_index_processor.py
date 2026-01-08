import sqlite3
from typing import Optional, List
from backend.db.base_db_processor import BaseDBProcessor
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.pagination_result import PaginationResult


class FileIndexProcessor(BaseDBProcessor):
    """
    用途：文件索引数据库处理器，负责 file_index 表的结构维护及相关操作
    """

    # 表名
    TABLE_NAME = 'file_index'

    # 列名常量
    COL_ID = 'id'
    COL_FILE_PATH = 'file_path'
    COL_FILE_MD5 = 'file_md5'
    COL_FILE_SIZE = 'file_size'
    COL_IS_IN_RECYCLE_BIN = 'is_in_recycle_bin'
    COL_THUMBNAIL_PATH = 'thumbnail_path'
    COL_SCAN_TIME = 'scan_time'

    def create_table(self, conn: sqlite3.Connection) -> None:
        """
        用途：创建文件索引表，用于记录文件仓库下的所有文件的文件信息
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
                {self.COL_THUMBNAIL_PATH} TEXT,
                {self.COL_IS_IN_RECYCLE_BIN} INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

    @staticmethod
    def batch_insert_data(data_list: List[FileIndexDBModel]) -> int:
        """
        用途：批量插入或更新文件索引
        入参说明：
            data_list (List[FileIndex]): 文件索引对象列表
        返回值说明：
            int: 成功插入的行数
        """
        if not data_list:
            return 0
        
        # 准备数据，确保元组顺序与 SQL 语句中的列顺序一致
        data = [
            (
                f.file_path,
                f.file_md5,
                f.file_size,
                f.thumbnail_path,
                f.is_in_recycle_bin)
            for f in data_list
        ]
        
        # 使用常量列名构建 SQL，防止硬编码错误
        query = f'''
            INSERT OR REPLACE INTO {FileIndexProcessor.TABLE_NAME} (
                {FileIndexProcessor.COL_FILE_PATH},
                {FileIndexProcessor.COL_FILE_MD5},
                {FileIndexProcessor.COL_FILE_SIZE},
                {FileIndexProcessor.COL_THUMBNAIL_PATH},
                {FileIndexProcessor.COL_IS_IN_RECYCLE_BIN},
                {FileIndexProcessor.COL_SCAN_TIME}
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''

        return BaseDBProcessor._execute_batch(query, data)

    @staticmethod
    def get_file_index_by_path(file_path: str) -> Optional[FileIndexDBModel]:
        """
        用途：通过文件路径从表中获取 FileIndex
        入参说明：
            file_path (str): 文件绝对路径
        返回值说明：
            Optional[FileIndex]: 找到的 FileIndex 对象，否则返回 None
        """
        query = f"SELECT * FROM {FileIndexProcessor.TABLE_NAME} WHERE {FileIndexProcessor.COL_FILE_PATH} = ?"
        result = BaseDBProcessor._execute(query, (file_path,), is_query=True, fetch_one=True)
        if result:
            return FileIndexDBModel(**result)
        return None

    @staticmethod
    def delete_by_id(file_id: int) -> bool:
        """
        用途：根据 ID 从文件索引表中删除记录
        入参说明：
            file_id (int): 记录的唯一标识 ID
        返回值说明：
            bool: 是否删除成功（受影响行数 > 0）
        """
        query = f"DELETE FROM {FileIndexProcessor.TABLE_NAME} WHERE {FileIndexProcessor.COL_ID} = ?"
        result = BaseDBProcessor._execute(query, (file_id,))
        return bool(result and result > 0)


    @staticmethod
    def clear_all_table() -> bool:
        return BaseDBProcessor._clear_table(FileIndexProcessor.TABLE_NAME)

    @staticmethod
    def get_paged_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[FileIndexDBModel]:
        """
        用途：分页查询文件索引列表，支持模糊搜索。
        入参说明：
            page (int): 当前页码
            limit (int): 每页记录数
            sort_by (str): 排序字段
            order (bool): 排序方向 (True 为 ASC, False 为 DESC)
            search_query (str): 搜索关键词
        返回值说明：
            PaginationResult[FileIndex]: 包含 total, list, page, limit 等分页信息的对象
        """
        allowed_cols = [
            FileIndexProcessor.COL_ID,
            FileIndexProcessor.COL_FILE_PATH,
            FileIndexProcessor.COL_FILE_MD5,
            FileIndexProcessor.COL_FILE_SIZE,
            FileIndexProcessor.COL_SCAN_TIME,
            FileIndexProcessor.COL_IS_IN_RECYCLE_BIN
        ]
        
        return BaseDBProcessor._search_paged_list(
            table_name=FileIndexProcessor.TABLE_NAME,
            model_class=FileIndexDBModel,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            search_query=search_query,
            search_column=FileIndexProcessor.COL_FILE_PATH,
            allowed_sort_columns=allowed_cols,
            default_sort_column=FileIndexProcessor.COL_SCAN_TIME
        )

    @staticmethod
    def get_list_by_condition(offset: int, limit: int, only_no_thumbnail: bool = False) -> List[FileIndexDBModel]:
        """
        用途：获取文件列表数据，支持分页及缩略图状态过滤
        入参说明：
            offset (int): 查询起始偏移量
            limit (int): 查询数量限制
            only_no_thumbnail (bool): 是否仅查询没有缩略图的文件
        返回值说明：
            List[FileIndex]: 文件索引模型列表
        """
        where_clause = ""
        if only_no_thumbnail:
            where_clause = f"WHERE ({FileIndexProcessor.COL_THUMBNAIL_PATH} IS NULL OR {FileIndexProcessor.COL_THUMBNAIL_PATH} = '')"

        query = f"""
            SELECT * FROM {FileIndexProcessor.TABLE_NAME}
            {where_clause}
            LIMIT ? OFFSET ?
        """
        rows = BaseDBProcessor._execute(query, (limit, offset), is_query=True)
        return [FileIndexDBModel(**row) for row in rows]

    @staticmethod
    def get_count(only_no_thumbnail: bool = False) -> int:
        """
        用途：获取文件索引表中的记录数量
        入参说明：
            only_no_thumbnail (bool): 是否仅统计没有缩略图的记录。默认为 False，统计所有记录。
        返回值说明：
            int: 满足条件的记录总数
        """
        where_clause = ""
        if only_no_thumbnail:
            where_clause = f"WHERE ({FileIndexProcessor.COL_THUMBNAIL_PATH} IS NULL OR {FileIndexProcessor.COL_THUMBNAIL_PATH} = '')"

        query = f"SELECT COUNT(*) as total FROM {FileIndexProcessor.TABLE_NAME} {where_clause}"
        res = BaseDBProcessor._execute(query, is_query=True, fetch_one=True)
        return res['total'] if res else 0
