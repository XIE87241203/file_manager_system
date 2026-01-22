import sqlite3
from typing import Optional, List, Tuple, Dict

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.pagination_result import PaginationResult


class FileIndexProcessor(BaseDBProcessor):
    """
    用途说明：文件索引数据库处理器，负责 file_index 表的相关 CRUD 操作。
    """

    @staticmethod
    def batch_insert_data(data_list: List[FileIndexDBModel], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量插入或更新文件索引。
        入参说明：
            data_list (List[FileIndexDBModel]): 待插入的文件对象列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回插入或更新成功的记录条数。
        """
        if not data_list:
            return 0
        
        data: List[tuple] = []
        for f in data_list:
            data.append((
                f.file_path,
                f.file_name,
                f.file_md5,
                f.file_size,
                f.thumbnail_path,
                f.recycle_bin_time,
                f.scan_time
            ))
        
        query: str = f'''
            INSERT OR REPLACE INTO {DBConstants.FileIndex.TABLE_NAME} (
                {DBConstants.FileIndex.COL_FILE_PATH},
                {DBConstants.FileIndex.COL_FILE_NAME},
                {DBConstants.FileIndex.COL_FILE_MD5},
                {DBConstants.FileIndex.COL_FILE_SIZE},
                {DBConstants.FileIndex.COL_THUMBNAIL_PATH},
                {DBConstants.FileIndex.COL_RECYCLE_BIN_TIME},
                {DBConstants.FileIndex.COL_SCAN_TIME}
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''

        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def delete_by_id(file_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：根据 ID 从文件索引表中删除记录。
        入参说明：
            file_id (int): 文件 ID。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回是否删除成功。
        """
        query: str = f"DELETE FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_ID} = ?"
        result: int = BaseDBProcessor._execute(query, (file_id,), conn=conn)
        return bool(result and result > 0)

    @staticmethod
    def batch_update_scan_time(file_paths: List[str], scan_time: str, conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量更新文件的扫描时间。
        入参说明：
            file_paths (List[str]): 文件路径列表。
            scan_time (str): 新新的扫描时间字符串。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回更新成功的记录数。
        """
        if not file_paths:
            return 0
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_SCAN_TIME} = ? WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        data = [(scan_time, path) for path in file_paths]
        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def delete_by_scan_time_not_equal(scan_time: str, conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：删除扫描时间不等于指定时间戳的所有记录。
        入参说明：
            scan_time (str): 目标扫描时间。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回删除的记录数。
        """
        query: str = f"DELETE FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_SCAN_TIME} != ?"
        return BaseDBProcessor._execute(query, (scan_time,), conn=conn)

    @staticmethod
    def get_file_index_by_path(file_path: str, conn: Optional[sqlite3.Connection] = None) -> Optional[FileIndexDBModel]:
        """
        用途说明：根据文件路径获取文件索引信息。
        入参说明：
            file_path (str): 文件路径。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回 FileIndexDBModel 对象 or None。
        """
        query: str = f"SELECT * FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        result: Optional[dict] = BaseDBProcessor._execute(query, (file_path,), is_query=True, fetch_one=True, conn=conn)
        if result:
            return FileIndexDBModel(**result)
        return None

    @staticmethod
    def get_ids_by_paths(file_paths: List[str], conn: Optional[sqlite3.Connection] = None) -> List[int]:
        """
        用途说明：根据路径列表批量获取对应的文件 ID。
        入参说明：
            file_paths (List[str]): 文件路径列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回对应的 ID 列表。
        """
        if not file_paths:
            return []
        placeholders: str = ','.join(['?'] * len(file_paths))
        query: str = f"SELECT {DBConstants.FileIndex.COL_ID} FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_PATH} IN ({placeholders})"
        rows: List[dict] = BaseDBProcessor._execute(query, tuple(file_paths), is_query=True, conn=conn)
        return [row[DBConstants.FileIndex.COL_ID] for row in rows]

    @staticmethod
    def update_thumbnail_path(file_path: str, thumbnail_path: str, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：更新指定文件的缩略图路径。
        入参说明：
            file_path (str): 文件路径。
            thumbnail_path (str): 缩略图路径。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回是否更新成功。
        """
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = ? WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        result: int = BaseDBProcessor._execute(query, (thumbnail_path, file_path), conn=conn)
        return bool(result and result > 0)

    @staticmethod
    def clear_all_thumbnails(conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：清空所有文件的缩略图记录。
        入参说明：
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回影响的行数。
        """
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = NULL"
        result: int = BaseDBProcessor._execute(query, conn=conn)
        return result if result is not None else 0

    @staticmethod
    def clear_all_table() -> bool:
        """
        用途说明：清空文件索引表的所有内容。
        返回值说明：返回是否清空成功。
        """
        return BaseDBProcessor._clear_table(DBConstants.FileIndex.TABLE_NAME)

    @staticmethod
    def get_paged_list(page: int, limit: int, sort_by: str, order: bool, search_query: str, is_in_recycle_bin: bool = False) -> PaginationResult[FileIndexDBModel]:
        """
        用途说明：分页搜索文件列表，并根据是否在回收站进行过滤。
        入参说明：
            page (int): 当前页码。
            limit (int): 每页条数。
            sort_by (str): 排序字段。
            order (bool): 是否为升序（True 为 ASC, False 为 DESC）。
            search_query (str): 搜索关键词。
            is_in_recycle_bin (bool): 是否过滤回收站内的数据。
        返回值说明：返回封装了 FileIndexDBModel 列表的分页结果对象。
        """
        allowed_cols: List[str] = [
            DBConstants.FileIndex.COL_ID,
            DBConstants.FileIndex.COL_FILE_PATH,
            DBConstants.FileIndex.COL_FILE_NAME,  # 允许按文件名排序
            DBConstants.FileIndex.COL_FILE_MD5,
            DBConstants.FileIndex.COL_FILE_SIZE,
            DBConstants.FileIndex.COL_SCAN_TIME,
            DBConstants.FileIndex.COL_RECYCLE_BIN_TIME
        ]
        
        # 兼容性逻辑：判定回收站时需同时检查 NULL 和空字符串
        col_recycle = DBConstants.FileIndex.COL_RECYCLE_BIN_TIME
        if is_in_recycle_bin:
            extra_where = f"AND ({col_recycle} IS NOT NULL AND {col_recycle} != '')"
        else:
            extra_where = f"AND ({col_recycle} IS NULL OR {col_recycle} = '')"

        return BaseDBProcessor._search_paged_list(
            table_name=DBConstants.FileIndex.TABLE_NAME,
            model_class=FileIndexDBModel,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            search_query=search_query,
            search_column=DBConstants.FileIndex.COL_FILE_NAME, # 默认改为按文件名搜索，更符合用户习惯
            allowed_sort_columns=allowed_cols,
            default_sort_column=DBConstants.FileIndex.COL_SCAN_TIME,
            extra_where=extra_where
        )

    @staticmethod
    def get_list_by_condition(offset: int, limit: int, only_no_thumbnail: bool = False) -> List[FileIndexDBModel]:
        """
        用途说明：根据指定 condition 获取文件列表（如仅获取无缩略图的文件）。
        入参说明：
            offset (int): 偏移量。
            limit (int): 限制条数。
            only_no_thumbnail (bool): 是否仅获取无缩略图的文件。
        返回值说明：返回 FileIndexDBModel 列表。
        """
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
        """
        用途说明：获取符合条件的文件总数。
        入参说明：
            only_no_thumbnail (bool): 是否仅统计无缩略图的文件。
        返回值说明：返回文件总数。
        """
        where_clause: str = ""
        if only_no_thumbnail:
            where_clause = f"WHERE ({DBConstants.FileIndex.COL_THUMBNAIL_PATH} IS NULL OR {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = '')"

        query: str = f"SELECT COUNT(*) as total FROM {DBConstants.FileIndex.TABLE_NAME} {where_clause}"
        res: Optional[dict] = BaseDBProcessor._execute(query, is_query=True, fetch_one=True)
        return res['total'] if res else 0

    @staticmethod
    def check_md5_exists(file_md5: str) -> bool:
        """
        用途说明：检查指定 MD5 是否已存在于数据库中。
        入参说明：file_md5 (str): 待检查的 MD5 字符串。
        返回值说明：存在返回 True，否则返回 False。
        """
        query: str = f"SELECT 1 FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_MD5} = ? LIMIT 1"
        res: Optional[dict] = BaseDBProcessor._execute(query, (file_md5,), is_query=True, fetch_one=True)
        return res is not None

    @staticmethod
    def check_path_exists(file_path: str) -> bool:
        """
        用途说明：检查指定文件路径是否已存在于数据库中。
        入参说明：file_path (str): 待检查的文件路径。
        返回值说明：存在返回 True，否则返回 False。
        """
        query: str = f"SELECT 1 FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ? LIMIT 1"
        res: Optional[dict] = BaseDBProcessor._execute(query, (file_path,), is_query=True, fetch_one=True)
        return res is not None

    @staticmethod
    def move_to_recycle_bin(file_paths: List[str], recycle_time: str, conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：将指定文件路径标记为已移入回收站。
        入参说明：
            file_paths (List[str]): 文件路径列表。
            recycle_time (str): 移入回收站的时间字符串。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回更新成功的记录条数。
        """
        if not file_paths:
            return 0
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_RECYCLE_BIN_TIME} = ? WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        data = [(recycle_time, path) for path in file_paths]
        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def restore_from_recycle_bin(file_paths: List[str], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：将指定文件从回收站移出（清除回收站时间标记）。
        入参说明：
            file_paths (List[str]): 文件路径列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回更新成功的记录条数。
        """
        if not file_paths:
            return 0
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_RECYCLE_BIN_TIME} = NULL WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        data = [(path,) for path in file_paths]
        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def get_paths_by_patterns(name_patterns: List[Tuple[str, str]], conn: Optional[sqlite3.Connection] = None) -> Dict[str, str]:
        """
        用途说明：根据预处理好的文件名匹配模式批量搜索已存在的文件路径。采用 CTE 批量模糊匹配优化。
        入参说明：
            name_patterns (List[Tuple[str, str]]): 包含 (原始文件名, 搜索模式) 的列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：Dict[str, str] - 返回 {原始文件名: 匹配到的文件路径}。
        """
        if not name_patterns:
            return {}
        
        results: Dict[str, str] = {}
        # 为防止超出 SQLite 变量限制，按 200 个一批进行处理
        chunk_size: int = 200
        for i in range(0, len(name_patterns), chunk_size):
            chunk = name_patterns[i:i + chunk_size]
            placeholders = ",".join(["(?, ?)"] * len(chunk))
            sql_params = []
            for name, pattern in chunk:
                sql_params.extend([name, pattern])
            
            # 使用 CTE (WITH) 构造临时搜索项表，并通过 LIKE JOIN 物理表实现批量搜索
            # 调整：由匹配文件路径改为匹配文件名 (COL_FILE_NAME)
            query = f"""
                WITH SearchTerms(original_name, pattern) AS (VALUES {placeholders})
                SELECT st.original_name, fi.{DBConstants.FileIndex.COL_FILE_PATH}
                FROM SearchTerms st
                JOIN {DBConstants.FileIndex.TABLE_NAME} fi ON fi.{DBConstants.FileIndex.COL_FILE_NAME} LIKE st.pattern
                GROUP BY st.original_name
            """
            rows = BaseDBProcessor._execute(query, tuple(sql_params), is_query=True, conn=conn)
            for row in rows:
                results[row['original_name']] = row[DBConstants.FileIndex.COL_FILE_PATH]
                
        return results

    @staticmethod
    def get_total_stats() -> Tuple[int, int]:
        """
        用途说明：统计 file_index 表中所有文件（非回收站）的总数和总大小。
        返回值说明：Tuple[int, int] - (总文件数, 总大小字节数)
        """
        col_recycle = DBConstants.FileIndex.COL_RECYCLE_BIN_TIME
        query = f'''
            SELECT COUNT(*), SUM({DBConstants.FileIndex.COL_FILE_SIZE}) 
            FROM {DBConstants.FileIndex.TABLE_NAME}
            WHERE ({col_recycle} IS NULL OR {col_recycle} = '')
        '''
        res = BaseDBProcessor._execute(query, is_query=True, fetch_one=True)
        if res:
            return res['COUNT(*)'] or 0, res[f'SUM({DBConstants.FileIndex.COL_FILE_SIZE})'] or 0
        return 0, 0
