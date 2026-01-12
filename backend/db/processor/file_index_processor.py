import sqlite3
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
    def batch_insert_data(data_list: List[FileIndexDBModel], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途：批量插入或更新文件索引
        """
        if not data_list:
            return 0
        
        data: List[tuple] = []
        for f in data_list:
            data.append((
                f.file_path,
                f.file_md5,
                f.file_size,
                f.thumbnail_path,
                f.is_in_recycle_bin,
                f.scan_time
            ))
        
        query: str = f'''
            INSERT OR REPLACE INTO {DBConstants.FileIndex.TABLE_NAME} (
                {DBConstants.FileIndex.COL_FILE_PATH},
                {DBConstants.FileIndex.COL_FILE_MD5},
                {DBConstants.FileIndex.COL_FILE_SIZE},
                {DBConstants.FileIndex.COL_THUMBNAIL_PATH},
                {DBConstants.FileIndex.COL_IS_IN_RECYCLE_BIN},
                {DBConstants.FileIndex.COL_SCAN_TIME}
            )
            VALUES (?, ?, ?, ?, ?, ?)
        '''

        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def delete_by_id(file_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途：根据 ID 从文件索引表中删除记录
        """
        query: str = f"DELETE FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_ID} = ?"
        result: int = BaseDBProcessor._execute(query, (file_id,), conn=conn)
        return bool(result and result > 0)

    # ... 其他方法也应类似增加 conn 参数，此处仅展示关键修改 ...
    
    @staticmethod
    def batch_update_scan_time(file_paths: List[str], scan_time: str, conn: Optional[sqlite3.Connection] = None) -> int:
        if not file_paths:
            return 0
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_SCAN_TIME} = ? WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        data = [(scan_time, path) for path in file_paths]
        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def delete_by_scan_time_not_equal(scan_time: str, conn: Optional[sqlite3.Connection] = None) -> int:
        query: str = f"DELETE FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_SCAN_TIME} != ?"
        return BaseDBProcessor._execute(query, (scan_time,), conn=conn)

    @staticmethod
    def get_file_index_by_path(file_path: str, conn: Optional[sqlite3.Connection] = None) -> Optional[FileIndexDBModel]:
        query: str = f"SELECT * FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        result: Optional[dict] = BaseDBProcessor._execute(query, (file_path,), is_query=True, fetch_one=True, conn=conn)
        if result:
            return FileIndexDBModel(**result)
        return None

    @staticmethod
    def update_thumbnail_path(file_path: str, thumbnail_path: str, conn: Optional[sqlite3.Connection] = None) -> bool:
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = ? WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        result: int = BaseDBProcessor._execute(query, (thumbnail_path, file_path), conn=conn)
        return bool(result and result > 0)

    @staticmethod
    def clear_all_thumbnails(conn: Optional[sqlite3.Connection] = None) -> int:
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = NULL"
        result: int = BaseDBProcessor._execute(query, conn=conn)
        return result if result is not None else 0

    @staticmethod
    def clear_all_table() -> bool:
        return BaseDBProcessor._clear_table(DBConstants.FileIndex.TABLE_NAME)

    @staticmethod
    def get_paged_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[FileIndexDBModel]:
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
        where_clause: str = ""
        if only_no_thumbnail:
            where_clause = f"WHERE ({DBConstants.FileIndex.COL_THUMBNAIL_PATH} IS NULL OR {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = '')"

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
        where_clause: str = ""
        if only_no_thumbnail:
            where_clause = f"WHERE ({DBConstants.FileIndex.COL_THUMBNAIL_PATH} IS NULL OR {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = '')"

        query: str = f"SELECT COUNT(*) as total FROM {DBConstants.FileIndex.TABLE_NAME} {where_clause}"
        res: Optional[dict] = BaseDBProcessor._execute(query, is_query=True, fetch_one=True)
        return res['total'] if res else 0

    @staticmethod
    def check_md5_exists(file_md5: str) -> bool:
        query: str = f"SELECT 1 FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_MD5} = ? LIMIT 1"
        res: Optional[dict] = BaseDBProcessor._execute(query, (file_md5,), is_query=True, fetch_one=True)
        return res is not None

    @staticmethod
    def check_path_exists(file_path: str) -> bool:
        query: str = f"SELECT 1 FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ? LIMIT 1"
        res: Optional[dict] = BaseDBProcessor._execute(query, (file_path,), is_query=True, fetch_one=True)
        return res is not None
