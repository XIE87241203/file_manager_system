from typing import Optional, List

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.pagination_result import PaginationResult


class FileIndexProcessor(BaseDBProcessor):
    """
    用途：文件索引数据库处理器，负责 file_index 表的相关操作
    """

    @staticmethod
    def batch_insert_data(data_list: List[FileIndexDBModel]) -> int:
        """
        用途：批量插入或更新文件索引
        入参说明：
            data_list (List[FileIndexDBModel]): 文件索引对象列表
        返回值说明：
            int: 成功插入的行数
        """
        if not data_list:
            return 0
        
        # 准备数据，确保元组顺序与 SQL 语句中的列顺序一致
        data: List[tuple] = [
            (
                f.file_path,
                f.file_md5,
                f.file_size,
                f.thumbnail_path,
                f.is_in_recycle_bin)
            for f in data_list
        ]
        
        # 使用常量类构建 SQL，防止硬编码错误
        query: str = f'''
            INSERT OR REPLACE INTO {DBConstants.FileIndex.TABLE_NAME} (
                {DBConstants.FileIndex.COL_FILE_PATH},
                {DBConstants.FileIndex.COL_FILE_MD5},
                {DBConstants.FileIndex.COL_FILE_SIZE},
                {DBConstants.FileIndex.COL_THUMBNAIL_PATH},
                {DBConstants.FileIndex.COL_IS_IN_RECYCLE_BIN},
                {DBConstants.FileIndex.COL_SCAN_TIME}
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
            Optional[FileIndexDBModel]: 找到的 FileIndex 对象，否则返回 None
        """
        query: str = f"SELECT * FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        result: Optional[dict] = BaseDBProcessor._execute(query, (file_path,), is_query=True, fetch_one=True)
        if result:
            return FileIndexDBModel(**result)
        return None

    @staticmethod
    def update_thumbnail_path(file_path: str, thumbnail_path: str) -> bool:
        """
        用途：更新指定文件的缩略图路径
        入参说明：
            file_path (str): 文件绝对路径
            thumbnail_path (str): 缩略图文件的相对路径或绝对路径
        返回值说明：
            bool: 是否更新成功
        """
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = ? WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        result: int = BaseDBProcessor._execute(query, (thumbnail_path, file_path))
        return bool(result and result > 0)

    @staticmethod
    def clear_all_thumbnails() -> int:
        """
        用途：清空所有文件的缩略图路径数据
        入参说明：无
        返回值说明：
            int: 受影响的行数
        """
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = NULL"
        result: int = BaseDBProcessor._execute(query)
        return result if result is not None else 0

    @staticmethod
    def delete_by_id(file_id: int) -> bool:
        """
        用途：根据 ID 从文件索引表中删除记录
        入参说明：
            file_id (int): 记录的唯一标识 ID
        返回值说明：
            bool: 是否删除成功（受影响行数 > 0）
        """
        query: str = f"DELETE FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_ID} = ?"
        result: int = BaseDBProcessor._execute(query, (file_id,))
        return bool(result and result > 0)

    @staticmethod
    def clear_all_table() -> bool:
        """
        用途：清空文件索引表
        入参说明：无
        返回值说明：
            bool: 是否清空成功
        """
        return BaseDBProcessor._clear_table(DBConstants.FileIndex.TABLE_NAME)

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
            PaginationResult[FileIndexDBModel]: 包含 total, list, page, limit 等分页信息的对象
        """
        allowed_cols: List[str] = [
            DBConstants.FileIndex.COL_ID,
            DBConstants.FileIndex.COL_FILE_PATH,
            DBConstants.FileIndex.COL_FILE_MD5,
            DBConstants.FileIndex.COL_FILE_SIZE,
            DBConstants.FileIndex.COL_SCAN_TIME,
            DBConstants.FileIndex.COL_IS_IN_RECYCLE_BIN
        ]
        
        return BaseDBProcessor._search_paged_list(
            table_name=DBConstants.FileIndex.TABLE_NAME,
            model_class=FileIndexDBModel,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            search_query=search_query,
            search_column=DBConstants.FileIndex.COL_FILE_PATH,
            allowed_sort_columns=allowed_cols,
            default_sort_column=DBConstants.FileIndex.COL_SCAN_TIME
        )

    @staticmethod
    def get_list_by_condition(offset: int, limit: int, only_no_thumbnail: bool = False) -> List[FileIndexDBModel]:
        """
        用途：获取文件列表数据，支持分页及缩略图状态过滤
        入参说明：
            offset (int): 查询起始偏移量
            limit (int): 查询数量限制（如果为 0，则返回从 offset 开始的所有数据）
            only_no_thumbnail (bool): 是否仅查询没有缩略图的文件
        返回值说明：
            List[FileIndexDBModel]: 文件索引模型列表
        """
        where_clause: str = ""
        if only_no_thumbnail:
            where_clause = f"WHERE ({DBConstants.FileIndex.COL_THUMBNAIL_PATH} IS NULL OR {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = '')"

        # 如果 limit 为 0，在 SQLite 中使用 -1 表示不限制数量
        actual_limit: int = limit if limit > 0 else -1

        query: str = f"""
            SELECT * FROM {DBConstants.FileIndex.TABLE_NAME}
            {where_clause}
            LIMIT ? OFFSET ?
        """
        rows: List[dict] = BaseDBProcessor._execute(query, (actual_limit, offset), is_query=True)
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
        where_clause: str = ""
        if only_no_thumbnail:
            where_clause = f"WHERE ({DBConstants.FileIndex.COL_THUMBNAIL_PATH} IS NULL OR {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = '')"

        query: str = f"SELECT COUNT(*) as total FROM {DBConstants.FileIndex.TABLE_NAME} {where_clause}"
        res: Optional[dict] = BaseDBProcessor._execute(query, is_query=True, fetch_one=True)
        return res['total'] if res else 0


