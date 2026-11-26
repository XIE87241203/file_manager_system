import os
import sqlite3
from typing import Optional, List, Tuple, Dict, Set

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.db.search_query_helper import SearchQueryHelper
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.cursor_pagination_result import CursorPaginationResult
from backend.model.db.album_axis_item_db_model import AlbumAxisItemDBModel
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
                f.file_type,
                f.video_duration,
                f.video_codec,
                f.thumbnail_path,
                f.recycle_bin_time,
                f.scan_time,
                f.file_mtime,
                f.file_exif_time,
                f.file_location
            ))
        
        query: str = f'''
            INSERT OR REPLACE INTO {DBConstants.FileIndex.TABLE_NAME} (
                {DBConstants.FileIndex.COL_FILE_PATH},
                {DBConstants.FileIndex.COL_FILE_NAME},
                {DBConstants.FileIndex.COL_FILE_MD5},
                {DBConstants.FileIndex.COL_FILE_SIZE},
                {DBConstants.FileIndex.COL_FILE_TYPE},
                {DBConstants.FileIndex.COL_VIDEO_DURATION},
                {DBConstants.FileIndex.COL_VIDEO_CODEC},
                {DBConstants.FileIndex.COL_THUMBNAIL_PATH},
                {DBConstants.FileIndex.COL_RECYCLE_BIN_TIME},
                {DBConstants.FileIndex.COL_SCAN_TIME},
                {DBConstants.FileIndex.COL_FILE_MTIME},
                {DBConstants.FileIndex.COL_FILE_EXIF_TIME},
                {DBConstants.FileIndex.COL_FILE_LOCATION}
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def delete_by_path(file_path: str, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：根据文件路径从文件索引表中删除记录。
        入参说明：
            file_path (str): 文件路径。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回是否删除成功。
        """
        query: str = f"DELETE FROM {DBConstants.FileIndex.TABLE_NAME} WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?"
        result: int = BaseDBProcessor._execute(query, (file_path,), conn=conn)
        return bool(result and result > 0)

    @staticmethod
    def batch_update_scan_time(file_paths: List[str], scan_time: str, conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量更新文件的扫描时间。
        入参说明：
            file_paths (List[str]): 文件路径列表.
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
    def get_missing_album_metadata(after_id: int, limit: int = 200,
                                   conn: Optional[sqlite3.Connection] = None) -> List[FileIndexDBModel]:
        """
        用途说明：按主键游标分批获取当前仓库中缺少媒体信息的有效图片或视频索引。
        入参说明：
            after_id (int): 上一批最后一个文件索引主键，首批传 0。
            limit (int): 单批最大记录数，默认 200。
            conn (Optional[sqlite3.Connection]): 可选的外部事务连接。
        返回值说明：List[FileIndexDBModel] - 按主键升序排列的待补全索引记录。
        """
        file_index: type = DBConstants.FileIndex
        missing_clause: str = ' OR '.join(
            f"({column} IS NULL OR {column} = '')" for column in (
                file_index.COL_FILE_MTIME,
                file_index.COL_FILE_EXIF_TIME,
                file_index.COL_FILE_LOCATION
            )
        )
        query: str = (
            f"SELECT * FROM {file_index.TABLE_NAME} "
            f"WHERE {file_index.COL_ID} > ? "
            f"AND {file_index.COL_FILE_TYPE} IN (?, ?) "
            f"AND ({file_index.COL_RECYCLE_BIN_TIME} IS NULL OR {file_index.COL_RECYCLE_BIN_TIME} = '') "
            f"AND ({missing_clause}) ORDER BY {file_index.COL_ID} ASC LIMIT ?"
        )
        rows: List[dict] = BaseDBProcessor._execute(
            query, (after_id, 'image', 'video', limit), is_query=True, conn=conn
        )
        return [FileIndexDBModel(**row) for row in rows]

    @staticmethod
    def count_missing_album_metadata(conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：统计当前仓库中缺少媒体信息的有效图片或视频索引数量。
        入参说明：conn (Optional[sqlite3.Connection]): 可选的外部事务连接。
        返回值说明：int - 待补全记录数量。
        """
        file_index: type = DBConstants.FileIndex
        missing_clause: str = ' OR '.join(
            f"({column} IS NULL OR {column} = '')" for column in (
                file_index.COL_FILE_MTIME,
                file_index.COL_FILE_EXIF_TIME,
                file_index.COL_FILE_LOCATION
            )
        )
        query: str = (
            f"SELECT COUNT(*) AS total FROM {file_index.TABLE_NAME} "
            f"WHERE {file_index.COL_FILE_TYPE} IN (?, ?) "
            f"AND ({file_index.COL_RECYCLE_BIN_TIME} IS NULL OR {file_index.COL_RECYCLE_BIN_TIME} = '') "
            f"AND ({missing_clause})"
        )
        result: Optional[dict] = BaseDBProcessor._execute(
            query, ('image', 'video'), is_query=True, fetch_one=True, conn=conn
        )
        return int(result['total']) if result else 0

    @staticmethod
    def batch_update_album_metadata(data_list: List[FileIndexDBModel],
                                    conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量补全索引中的媒体修改时间、拍摄时间和拍摄地点，只覆盖原本为空的字段。
        入参说明：
            data_list (List[FileIndexDBModel]): 从物理文件读取的媒体信息列表，单批不超过 200 条。
            conn (Optional[sqlite3.Connection]): 可选的外部事务连接。
        返回值说明：int - 实际更新的索引记录数量；不修改主键、扫描时间和回收站状态。
        """
        if not data_list:
            return 0
        file_index: type = DBConstants.FileIndex
        query: str = (
            f"UPDATE {file_index.TABLE_NAME} SET "
            f"{file_index.COL_FILE_MTIME} = CASE "
            f"WHEN {file_index.COL_FILE_MTIME} IS NULL OR {file_index.COL_FILE_MTIME} = '' "
            f"THEN ? ELSE {file_index.COL_FILE_MTIME} END, "
            f"{file_index.COL_FILE_EXIF_TIME} = CASE "
            f"WHEN {file_index.COL_FILE_EXIF_TIME} IS NULL OR {file_index.COL_FILE_EXIF_TIME} = '' "
            f"THEN ? ELSE {file_index.COL_FILE_EXIF_TIME} END, "
            f"{file_index.COL_FILE_LOCATION} = CASE "
            f"WHEN {file_index.COL_FILE_LOCATION} IS NULL OR {file_index.COL_FILE_LOCATION} = '' "
            f"THEN ? ELSE {file_index.COL_FILE_LOCATION} END "
            f"WHERE {file_index.COL_FILE_PATH} = ?"
        )
        data: List[tuple] = [
            (item.file_mtime, item.file_exif_time, item.file_location, item.file_path)
            for item in data_list
        ]
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
    def update_thumbnail_path_by_md5(file_md5: str, thumbnail_path: str, conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：按文件 MD5 批量回填缩略图路径。缩略图按内容 MD5 命名，同内容文件共享同一缩略图，
                  因此生成一次缩略图后需同步回填所有同 MD5 文件（含副本），避免副本因路径为空而无法预览。
        入参说明：
            file_md5 (str): 文件 MD5 哈希值。
            thumbnail_path (str): 缩略图路径。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：int - 受影响的记录数。
        """
        query: str = f"UPDATE {DBConstants.FileIndex.TABLE_NAME} SET {DBConstants.FileIndex.COL_THUMBNAIL_PATH} = ? WHERE {DBConstants.FileIndex.COL_FILE_MD5} = ?"
        result: int = BaseDBProcessor._execute(query, (thumbnail_path, file_md5), conn=conn)
        return result or 0

    @staticmethod
    def update_file_path(old_path: str, new_path: str, conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：将文件索引中的原路径替换为新路径，并同步更新文件名（取新路径的文件名部分）。
                  使用 UPDATE OR IGNORE：若新路径已存在其他索引记录（file_path 唯一约束冲突），
                  本次更新会被忽略而不是覆盖原有记录。
        入参说明：
            old_path (str): 索引中记录的原文件路径。
            new_path (str): 文件移动/改名后的新文件路径。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：int - 实际更新的记录数；0 表示原路径不在索引或新路径冲突被忽略。
        """
        new_name: str = os.path.basename(new_path.replace('\\', '/'))
        query: str = (f"UPDATE OR IGNORE {DBConstants.FileIndex.TABLE_NAME} "
                      f"SET {DBConstants.FileIndex.COL_FILE_PATH} = ?, {DBConstants.FileIndex.COL_FILE_NAME} = ? "
                      f"WHERE {DBConstants.FileIndex.COL_FILE_PATH} = ?")
        result: int = BaseDBProcessor._execute(query, (new_path, new_name, old_path), conn=conn)
        return result or 0

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
    def clear_all_table(conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：清空文件索引表的所有内容，可参与调用方事务。
        入参说明：conn (Optional[sqlite3.Connection]) - 可选的外部事务连接。
        返回值说明：返回是否清空成功。
        """
        if conn is not None:
            BaseDBProcessor._execute(f"DELETE FROM {DBConstants.FileIndex.TABLE_NAME}", conn=conn)
            BaseDBProcessor._execute(
                "DELETE FROM sqlite_sequence WHERE name=?",
                (DBConstants.FileIndex.TABLE_NAME,),
                conn=conn
            )
            return True
        return BaseDBProcessor._clear_table(DBConstants.FileIndex.TABLE_NAME)

    @staticmethod
    def get_paged_list(page: int, limit: int, sort_by: str, order: bool, search_query: str, 
                       is_in_recycle_bin: bool = False, file_type: Optional[str] = None) -> PaginationResult[FileIndexDBModel]:
        """
        用途说明：分页搜索文件列表，并根据是否在回收站以及文件类型进行过滤。
        入参说明：
            page (int): 当前页码。
            limit (int): 每页条数。
            sort_by (str): 排序字段。
            order (bool): 是否为升序（True 为 ASC, False 为 DESC）。
            search_query (str): 搜索关键词。
            is_in_recycle_bin (bool): 是否过滤回收站内的数据。
            file_type (Optional[str]): 文件类型筛选 (如 'video', 'image', 'other')。
        返回值说明：返回封装了 FileIndexDBModel 列表的分页结果对象。
        """
        allowed_cols: List[str] = [
            DBConstants.FileIndex.COL_ID,
            DBConstants.FileIndex.COL_FILE_PATH,
            DBConstants.FileIndex.COL_FILE_NAME,
            DBConstants.FileIndex.COL_FILE_MD5,
            DBConstants.FileIndex.COL_FILE_SIZE,
            DBConstants.FileIndex.COL_FILE_TYPE,
            DBConstants.FileIndex.COL_VIDEO_DURATION,
            DBConstants.FileIndex.COL_VIDEO_CODEC,
            DBConstants.FileIndex.COL_SCAN_TIME,
            DBConstants.FileIndex.COL_RECYCLE_BIN_TIME
        ]
        
        # 兼容性逻辑：判定回收站时需同时检查 NULL 和空字符串
        col_recycle = DBConstants.FileIndex.COL_RECYCLE_BIN_TIME
        if is_in_recycle_bin:
            extra_where = f"AND ({col_recycle} IS NOT NULL AND {col_recycle} != '')"
        else:
            extra_where = f"AND ({col_recycle} IS NULL OR {col_recycle} = '')"

        # 处理文件类型筛选
        if file_type:
            extra_where += f" AND {DBConstants.FileIndex.COL_FILE_TYPE} = '{file_type}'"

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
    def get_album_paged_list(limit: int, sort_by: str, order: bool,
                             search_query: str, file_types: List[str],
                             last_path: str = '', anchor_path: str = '',
                             before_path: str = '') -> CursorPaginationResult[FileIndexDBModel]:
        """
        用途说明：按媒体路径游标或锚点查询相册数据，排除回收站文件并按文件名搜索；
                   支持相册时间、文件名首字母与文件大小三种全局排序，不使用页码。
        入参说明：
            limit (int): 本次获取条数。
            sort_by (str): 排序字段，可选 album_time、file_name、file_size。
            order (bool): 是否为升序（True 为 ASC，False 为 DESC）。
            search_query (str): 搜索关键词（按文件名模糊匹配）。
            file_types (List[str]): 需要包含的文件类型列表（如 ['image', 'video']）。
            last_path (str): 向下游标路径，空字符串表示首批数据。
            anchor_path (str): 定位锚点路径，从该媒体开始包含式取数。
            before_path (str): 向上锚点路径，取该媒体之前最近一批数据。
        返回值说明：CursorPaginationResult[FileIndexDBModel] - 不包含页码的游标分页结果对象。
        """
        table_name: str = DBConstants.FileIndex.TABLE_NAME
        col_id: str = DBConstants.FileIndex.COL_ID
        col_path: str = DBConstants.FileIndex.COL_FILE_PATH
        col_name: str = DBConstants.FileIndex.COL_FILE_NAME
        col_size: str = DBConstants.FileIndex.COL_FILE_SIZE
        allowed_cols: List[str] = [
            col_id,
            col_path,
            col_name,
            DBConstants.FileIndex.COL_FILE_MD5,
            col_size,
            DBConstants.FileIndex.COL_FILE_TYPE,
            DBConstants.FileIndex.COL_VIDEO_DURATION,
            DBConstants.FileIndex.COL_VIDEO_CODEC,
            DBConstants.FileIndex.COL_SCAN_TIME,
            DBConstants.FileIndex.COL_RECYCLE_BIN_TIME,
            DBConstants.FileIndex.COL_FILE_MTIME,
            DBConstants.FileIndex.COL_FILE_EXIF_TIME,
            DBConstants.FileIndex.ALBUM_TIME_FIELD
        ]

        # 兜底：未识别的排序字段统一按相册时间排序
        if sort_by not in allowed_cols:
            sort_by = DBConstants.FileIndex.ALBUM_TIME_FIELD
        if sort_by == DBConstants.FileIndex.ALBUM_TIME_FIELD:
            primary_expression: str = f"COALESCE({DBConstants.FileIndex.ALBUM_TIME_EXPRESSION}, '')"
        elif sort_by == col_name:
            primary_expression = "COALESCE(filename_initial(file_name), '#')"
        elif sort_by == col_size:
            primary_expression = f"COALESCE({col_size}, 0)"
        else:
            primary_expression = f"COALESCE({sort_by}, '')"

        order_str: str = 'ASC' if order else 'DESC'
        comparison: str = '>' if order else '<'
        order_by_sql: str = f"{primary_expression} {order_str}, {col_name} {order_str}, {col_id} {order_str}"

        # 排除回收站文件，并仅保留图片/视频类型
        col_recycle: str = DBConstants.FileIndex.COL_RECYCLE_BIN_TIME
        where_sql: str = f"{col_name} LIKE ? AND ({col_recycle} IS NULL OR {col_recycle} = '')"
        query_params: List[object] = [SearchQueryHelper.process_search_query(search_query)]
        valid_types: List[str] = [item for item in file_types if item]
        if valid_types:
            placeholders: str = ','.join(['?'] * len(valid_types))
            where_sql += f" AND {DBConstants.FileIndex.COL_FILE_TYPE} IN ({placeholders})"
            query_params.extend(valid_types)

        count_query: str = f"SELECT COUNT(*) as total FROM {table_name} WHERE {where_sql}"
        total_res: Optional[dict] = BaseDBProcessor._execute(
            count_query, tuple(query_params), is_query=True, fetch_one=True
        )
        total: int = int(total_res['total']) if total_res else 0

        # 按路径读取主排序值、次级排序值和唯一 ID，支持向下、定位和向上三种取数方式
        cursor_sql: str = ''
        cursor_path: str = last_path or anchor_path or before_path
        is_anchor_load: bool = bool(anchor_path and not last_path)
        is_previous_load: bool = bool(before_path and not last_path and not anchor_path)
        query_order_sql: str = order_by_sql
        if cursor_path:
            cursor_query: str = (
                f"SELECT {primary_expression} AS cursor_primary, "
                f"{col_name} AS cursor_name, {col_id} AS cursor_id "
                f"FROM {table_name} WHERE {col_path} = ?"
            )
            cursor_row: Optional[dict] = BaseDBProcessor._execute(
                cursor_query, (cursor_path,), is_query=True, fetch_one=True
            )
            if not cursor_row:
                return CursorPaginationResult(
                    total=total, list=[], limit=limit,
                    sort_by=sort_by, order=order_str
                )

            if is_anchor_load:
                # 包含锚点本身时，仅最后一个唯一 ID 使用包含比较，前两级仍保持严格顺序
                primary_comparison: str = '>' if order else '<'
                name_comparison: str = primary_comparison
                id_comparison: str = '>=' if order else '<='
            elif is_previous_load:
                primary_comparison = '<' if order else '>'
                name_comparison = primary_comparison
                id_comparison = primary_comparison
                reverse_order_str: str = 'DESC' if order else 'ASC'
                query_order_sql = (
                    f"{primary_expression} {reverse_order_str}, "
                    f"{col_name} {reverse_order_str}, {col_id} {reverse_order_str}"
                )
            else:
                primary_comparison = comparison
                name_comparison = comparison
                id_comparison = comparison

            cursor_sql = (
                f" AND (({primary_expression}) {primary_comparison} ? "
                f"OR (({primary_expression}) = ? AND {col_name} {name_comparison} ?) "
                f"OR (({primary_expression}) = ? AND {col_name} = ? AND {col_id} {id_comparison} ?))"
            )
            query_params.extend((
                cursor_row['cursor_primary'],
                cursor_row['cursor_primary'], cursor_row['cursor_name'],
                cursor_row['cursor_primary'], cursor_row['cursor_name'], cursor_row['cursor_id']
            ))

        list_query: str = (
            f"SELECT * FROM {table_name} WHERE {where_sql}{cursor_sql} "
            f"ORDER BY {query_order_sql} LIMIT ?"
        )
        query_params.append(limit)
        rows: List[dict] = BaseDBProcessor._execute(list_query, tuple(query_params), is_query=True)
        if is_previous_load:
            rows.reverse()
        data_list: List[FileIndexDBModel] = [FileIndexDBModel(**row) for row in rows]

        return CursorPaginationResult(
            total=total,
            list=data_list,
            limit=limit,
            sort_by=sort_by,
            order=order_str
        )

    @staticmethod
    def get_album_axis(level: str, sort_by: str, order: bool,
                       search_query: str, file_types: List[str],
                       year: str = '', month: int = 0) -> List[AlbumAxisItemDBModel]:
        """
        用途说明：聚合相册年份、月份、日期或文件名首字母轴，并返回每组首条媒体路径。
        入参说明：
            level (str): 轴层级，可选 year、month、day、initial。
            sort_by (str): 组内首条媒体的排序字段。
            order (bool): 组内首条媒体是否按升序排列。
            search_query (str): 文件名搜索关键词。
            file_types (List[str]): 需要包含的媒体类型。
            year (str): 月份轴或日期轴所属年份。
            month (int): 日期轴所属月份。
        返回值说明：List[AlbumAxisItemDBModel] - 轴分组、首条路径和媒体数量。
        """
        table_name: str = DBConstants.FileIndex.TABLE_NAME
        col_id: str = DBConstants.FileIndex.COL_ID
        col_path: str = DBConstants.FileIndex.COL_FILE_PATH
        col_name: str = DBConstants.FileIndex.COL_FILE_NAME
        col_recycle: str = DBConstants.FileIndex.COL_RECYCLE_BIN_TIME
        time_expression: str = DBConstants.FileIndex.ALBUM_TIME_EXPRESSION
        order_str: str = 'ASC' if order else 'DESC'

        where_sql: str = f"{col_name} LIKE ? AND ({col_recycle} IS NULL OR {col_recycle} = '')"
        query_params: List[object] = [SearchQueryHelper.process_search_query(search_query)]
        valid_types: List[str] = [item for item in file_types if item]
        if valid_types:
            placeholders: str = ','.join(['?'] * len(valid_types))
            where_sql += f" AND {DBConstants.FileIndex.COL_FILE_TYPE} IN ({placeholders})"
            query_params.extend(valid_types)

        valid_time_sql: str = (
            f"(length(COALESCE({time_expression}, '')) >= 10 "
            f"AND substr({time_expression}, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' "
            f"AND substr({time_expression}, 5, 1) = '-' "
            f"AND substr({time_expression}, 8, 1) = '-')"
        )

        if level == 'initial':
            group_expression: str = "COALESCE(filename_initial(file_name), '#')"
            row_order_sql: str = f"{col_name} {order_str}, {col_id} {order_str}"
            axis_condition: str = ''
        else:
            if level == 'year':
                group_expression = f"substr(COALESCE({time_expression}, ''), 1, 4)"
            elif level == 'month':
                group_expression = f"substr(COALESCE({time_expression}, ''), 1, 7)"
                where_sql += f" AND substr({time_expression}, 1, 4) = ?"
                query_params.append(year)
            else:
                group_expression = f"substr(COALESCE({time_expression}, ''), 1, 10)"
                where_sql += f" AND substr({time_expression}, 1, 4) = ?"
                where_sql += f" AND substr({time_expression}, 6, 2) = ?"
                query_params.extend((year, f"{month:02d}"))
            row_order_sql = (
                f"{time_expression} {order_str}, {col_name} {order_str}, {col_id} {order_str}"
            )
            axis_condition = f" AND {valid_time_sql}"

        axis_query: str = (
            "SELECT key, first_path, media_count FROM ("
            f"SELECT {group_expression} AS key, {col_path} AS first_path, "
            f"COUNT(*) OVER (PARTITION BY {group_expression}) AS media_count, "
            f"ROW_NUMBER() OVER (PARTITION BY {group_expression} ORDER BY {row_order_sql}) AS row_num "
            f"FROM {table_name} WHERE {where_sql}{axis_condition}"
            ") WHERE row_num = 1"
        )
        if level == 'initial':
            axis_query += " ORDER BY CASE WHEN key = '#' THEN 1 ELSE 0 END, key ASC"
        else:
            axis_query += f" ORDER BY key {order_str}"

        rows: List[dict] = BaseDBProcessor._execute(
            axis_query, tuple(query_params), is_query=True
        )
        items: List[AlbumAxisItemDBModel] = [
            AlbumAxisItemDBModel(
                key=str(row['key']),
                first_path=str(row['first_path'] or ''),
                count=int(row['media_count'] or 0)
            )
            for row in rows
        ]

        # 年份轴额外返回无有效时间的媒体，保证未知日期内容仍可通过轴定位
        if level == 'year':
            unknown_params: List[object] = list(query_params)
            unknown_query: str = (
                f"SELECT {col_path} AS first_path, COUNT(*) OVER () AS media_count "
                f"FROM {table_name} WHERE {where_sql} "
                f"AND NOT COALESCE(({valid_time_sql}), 0) "
                f"ORDER BY {time_expression} {order_str}, {col_name} {order_str}, {col_id} {order_str} "
                "LIMIT 1"
            )
            unknown_rows: List[dict] = BaseDBProcessor._execute(
                unknown_query, tuple(unknown_params), is_query=True
            )
            if unknown_rows:
                unknown_row: dict = unknown_rows[0]
                items.append(AlbumAxisItemDBModel(
                    key='unknown',
                    first_path=str(unknown_row['first_path'] or ''),
                    count=int(unknown_row['media_count'] or 0)
                ))

        return items

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
    def _build_scan_time_filter(checkpoint: Optional[str], newer: bool) -> Optional[Tuple[str, List[str]]]:
        """
        用途说明：构建按扫描时间筛选文件的 WHERE 条件（均排除回收站内的文件），供列表与计数查询共用。
        入参说明：
            checkpoint (Optional[str]): 查重时间点。为 None 时，newer=True 匹配全部文件，newer=False 匹配空集。
            newer (bool): True 筛选扫描时间晚于时间点的新文件；False 筛选不晚于时间点的旧文件。
        返回值说明：Optional[Tuple[str, List[str]]]: (WHERE 子句, 参数列表)；结果集必为空时返回 None。
        """
        col_recycle = DBConstants.FileIndex.COL_RECYCLE_BIN_TIME
        conditions: List[str] = [f"({col_recycle} IS NULL OR {col_recycle} = '')"]
        params: List[str] = []
        if checkpoint is None:
            if not newer:
                return None
        else:
            operator: str = '>' if newer else '<='
            conditions.append(f"{DBConstants.FileIndex.COL_SCAN_TIME} {operator} ?")
            params.append(checkpoint)
        return "WHERE " + " AND ".join(conditions), params

    @staticmethod
    def get_files_by_scan_time(checkpoint: Optional[str], newer: bool,
                               limit: Optional[int] = None, offset: int = 0) -> List[FileIndexDBModel]:
        """
        用途说明：按扫描时间与查重时间点的关系获取文件列表（均排除回收站内的文件）。
        入参说明：
            checkpoint (Optional[str]): 查重时间点。为 None 时，newer=True 返回全部文件，newer=False 返回空列表。
            newer (bool): True 获取扫描时间晚于时间点的新文件；False 获取不晚于时间点的旧文件。
            limit (Optional[int]): 单批返回上限；为 None 时返回全部（兼容旧调用），大库建议分批传入。
            offset (int): 分批查询的偏移量，仅在传入 limit 时生效。
        返回值说明：List[FileIndexDBModel]: 符合条件的文件索引列表（按主键 ID 升序，保证分批遍历稳定）。
        """
        filter_result: Optional[Tuple[str, List[str]]] = FileIndexProcessor._build_scan_time_filter(checkpoint, newer)
        if filter_result is None:
            return []
        where_clause, params = filter_result

        query: str = (
            f"SELECT * FROM {DBConstants.FileIndex.TABLE_NAME} {where_clause} "
            f"ORDER BY {DBConstants.FileIndex.COL_ID} ASC"
        )
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params = params + [str(limit), str(offset)]
        rows: List[dict] = BaseDBProcessor._execute(query, tuple(params), is_query=True)
        return [FileIndexDBModel(**row) for row in rows]

    @staticmethod
    def count_files_by_scan_time(checkpoint: Optional[str], newer: bool) -> int:
        """
        用途说明：统计按扫描时间筛选的文件数量（排除回收站文件），用于分批处理前确定总量。
        入参说明：
            checkpoint (Optional[str]): 查重时间点。为 None 时，newer=True 统计全部文件，newer=False 统计 0。
            newer (bool): True 统计新文件；False 统计旧文件。
        返回值说明：int: 符合条件的文件数量。
        """
        filter_result: Optional[Tuple[str, List[str]]] = FileIndexProcessor._build_scan_time_filter(checkpoint, newer)
        if filter_result is None:
            return 0
        where_clause, params = filter_result
        query: str = f"SELECT COUNT(*) as total FROM {DBConstants.FileIndex.TABLE_NAME} {where_clause}"
        res: Optional[dict] = BaseDBProcessor._execute(query, tuple(params), is_query=True, fetch_one=True)
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
    def get_recycle_bin_paths_under(dir_prefixes: List[str]) -> Set[str]:
        """
        用途说明：查询指定目录（含子目录）下所有已移入回收站的文件路径集合，
            供整理扫描时排除用户已删除（移入回收站）的文件，避免重扫后再次出现。
        入参说明：dir_prefixes (List[str]): 目录路径列表（来自整理设置的待整理目录）。
        返回值说明：Set[str] - 回收站标记非空且位于这些目录下的文件完整路径集合。
        """
        result: Set[str] = set()
        conditions: List[str] = []
        params: List[str] = []
        for prefix in dir_prefixes:
            # 统一去掉尾部分隔符后按“目录\”前缀匹配（目录名中的 % _ \ 按字面量转义）
            normalized: str = str(prefix or '').rstrip('\\/')
            if not normalized:
                continue
            escaped: str = normalized.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            conditions.append(f"{DBConstants.FileIndex.COL_FILE_PATH} LIKE ? ESCAPE '\\'")
            params.append(escaped + '\\\\' + '%')
        if not conditions:
            return result
        query: str = (
            f"SELECT {DBConstants.FileIndex.COL_FILE_PATH} FROM {DBConstants.FileIndex.TABLE_NAME} "
            f"WHERE {DBConstants.FileIndex.COL_RECYCLE_BIN_TIME} IS NOT NULL "
            f"AND ({' OR '.join(conditions)})"
        )
        rows: List[dict] = BaseDBProcessor._execute(query, tuple(params), is_query=True)
        for row in rows:
            result.add(row[DBConstants.FileIndex.COL_FILE_PATH])
        return result

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
