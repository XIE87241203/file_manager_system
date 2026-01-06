from typing import List, Tuple, Optional, Union, Any
import json
import sqlite3
from backend.db.db_manager import db_manager, DBManager
from backend.common.log_utils import LogUtils

from backend.db.model.file_index import FileIndex
from backend.db.model.history_file_index import HistoryFileIndex
from backend.db.model.video_features import VideoFeatures
from backend.db.model.video_info_cache import VideoInfoCache
from backend.file_repository.duplicate_check.checker.models.duplicate_models import DuplicateGroup, DuplicateFile


class DBOperations:
    """
    用途：数据库操作类，负责所有数据的增删改查业务逻辑
    """

    # --- 私有辅助方法 ---

    @staticmethod
    def __execute(query: str, params: tuple = (), is_query: bool = False, fetch_one: bool = False) -> Any:
        """
        用途：通用的执行 SQL 语句方法
        入参说明：
            query (str): SQL 语句
            params (tuple): 参数元组
            is_query (bool): 是否为查询操作
            fetch_one (bool): 是否仅获取单条记录
        返回值说明：
            Any: 查询结果（列表或字典）或受影响的行数
        """
        conn = None
        try:
            conn = db_manager.get_connection()
            conn.row_factory = sqlite3.Row  # 启用字段名访问
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if is_query:
                if fetch_one:
                    row = cursor.fetchone()
                    return dict(row) if row else None
                else:
                    rows = cursor.fetchall()
                    return [dict(r) for r in rows]
            else:
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            LogUtils.error(f"SQL 执行失败: {query}, 错误: {e}")
            return [] if is_query and not fetch_one else (None if fetch_one else 0)
        finally:
            if conn:
                conn.close()

    @staticmethod
    def __execute_batch(query: str, data: List[tuple]) -> int:
        """
        用途：批量执行 SQL 语句（用于高效插入）
        入参说明：
            query (str): SQL 语句
            data (List[tuple]): 待插入的数据元组列表
        返回值说明：
            int: 受影响的总行数
        """
        conn = None
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.executemany(query, data)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            LogUtils.error(f"批量执行失败: {query}, 错误: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    @staticmethod
    def __clear_table(table_name: str) -> bool:
        """
        用途：清空指定表并重置其自增主键序列
        入参说明：
            table_name (str): 表名
        返回值说明：
            bool: 是否成功
        """
        DBOperations.__execute(f'DELETE FROM {table_name}')
        DBOperations.__execute("DELETE FROM sqlite_sequence WHERE name=?", (table_name,))
        LogUtils.info(f"表 {table_name} 已清空")
        return True

    # --- 文件索引相关操作 (File Index & History) ---

    @staticmethod
    def batch_insert_files(file_list: List[FileIndex]) -> None:
        """
        用途：批量插入或更新文件索引
        入参说明：
            file_list (List[FileIndex]): 文件索引对象列表
        返回值说明：
            None
        """
        if not file_list:
            return
        data = [(f.file_path, f.file_name, f.file_md5, f.thumbnail_path) for f in file_list]
        query = f'''
            INSERT OR REPLACE INTO {DBManager.TABLE_FILE_INDEX} (file_path, file_name, file_md5, thumbnail_path, scan_time)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''
        count = DBOperations.__execute_batch(query, data)
        LogUtils.info(f"成功更新 {count} 条文件索引记录")

    @staticmethod
    def clear_file_index() -> bool:
        """
        用途：清空当前文件索引表
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        return DBOperations.__clear_table(DBManager.TABLE_FILE_INDEX)

    @staticmethod
    def clear_history_index() -> bool:
        """
        用途：清空历史文件索引表，并同步清空查重结果表
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        # 1. 清空历史索引表
        DBOperations.__clear_table(DBManager.TABLE_HISTORY_INDEX)
        # 2. 同步清空查重结果相关表
        DBOperations.clear_duplicate_results()
        LogUtils.info("历史文件索引及查重结果已同步清空")
        return True

    @staticmethod
    def copy_to_history() -> bool:
        """
        用途：将当前索引数据同步到历史表
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        query = f'''
            INSERT OR REPLACE INTO {DBManager.TABLE_HISTORY_INDEX} (file_path, file_name, file_md5, scan_time)
            SELECT file_path, file_name, file_md5, scan_time FROM {DBManager.TABLE_FILE_INDEX}
        '''
        return DBOperations.__execute(query) > 0

    @staticmethod
    def get_duplicate_md5s() -> List[Tuple[str, int]]:
        """
        用途：获取 MD5 重复的分组及其重复次数
        入参说明：无
        返回值说明：
            List[Tuple[str, int]]: (MD5值, 重复数) 列表
        """
        query = f"SELECT file_md5, COUNT(*) as count FROM {DBManager.TABLE_FILE_INDEX} GROUP BY file_md5 HAVING count > 1"
        rows = DBOperations.__execute(query, is_query=True)
        return [(r['file_md5'], r['count']) for r in rows]

    @staticmethod
    def get_file_by_path(file_path: str) -> Optional[FileIndex]:
        """
        用途：根据路径从索引表中获取单个文件信息
        入参说明：
            file_path (str): 文件路径
        返回值说明：
            Optional[FileIndex]: 文件索引对象，若不存在则返回 None
        """
        query = f"SELECT * FROM {DBManager.TABLE_FILE_INDEX} WHERE file_path = ?"
        row = DBOperations.__execute(query, (file_path,), is_query=True, fetch_one=True)
        return FileIndex(**row) if row else None

    @staticmethod
    def get_files_by_md5(md5: str) -> List[FileIndex]:
        """
        用途：根据 MD5 获取所有匹配的文件对象
        入参说明：
            md5 (str): 文件的 MD5 值
        返回值说明：
            List[FileIndex]: 文件索引对象列表
        """
        query = f"SELECT * FROM {DBManager.TABLE_FILE_INDEX} WHERE file_md5 = ?"
        rows = DBOperations.__execute(query, (md5,), is_query=True)
        return [FileIndex(**r) for r in rows]

    @staticmethod
    def delete_file_index_by_path(file_path: str) -> int:
        """
        用途：根据路径从索引表中删除文件记录
        入参说明：
            file_path (str): 文件路径
        返回值说明：
            int: 受影响的行数
        """
        query = f"DELETE FROM {DBManager.TABLE_FILE_INDEX} WHERE file_path = ?"
        return DBOperations.__execute(query, (file_path,))

    @staticmethod
    def get_file_list_with_pagination(
        table_name: str, 
        where_clause: str = "", 
        params: tuple = (), 
        sort_by: str = "scan_time", 
        order: str = "DESC", 
        limit: int = 100, 
        offset: int = 0,
        only_no_thumbnail: bool = False
    ) -> List[Union[FileIndex, HistoryFileIndex]]:
        """
        用途：通用分页查询文件列表
        入参说明：
            table_name (str): 表名
            where_clause (str): SQL 条件子句
            params (tuple): 条件参数
            sort_by (str): 排序字段
            order (str): 排序方向 (ASC/DESC)
            limit (int): 分页大小
            offset (int): 偏移量
            only_no_thumbnail (bool): 是否仅查询没有缩略图的文件
        返回值说明：
            List[Union[FileIndex, HistoryFileIndex]]: 数据对象列表
        """
        if only_no_thumbnail:
            no_thumb_condition = "(thumbnail_path IS NULL OR thumbnail_path = '')"
            if "WHERE" in where_clause.upper():
                where_clause += f" AND {no_thumb_condition}"
            else:
                where_clause = f" WHERE {no_thumb_condition}"

        query = f"SELECT * FROM {table_name} {where_clause} ORDER BY {sort_by} {order} LIMIT ? OFFSET ?"
        full_params = list(params) + [limit, offset]
        rows = DBOperations.__execute(query, tuple(full_params), is_query=True)
        
        model_cls = HistoryFileIndex if table_name == DBManager.TABLE_HISTORY_INDEX else FileIndex
        return [model_cls(**r) for r in rows]

    @staticmethod
    def get_file_count(table_name: str, where_clause: str = "", params: tuple = (), only_no_thumbnail: bool = False) -> int:
        """
        用途：获取表中满足条件的记录总数
        入参说明：
            table_name (str): 表名
            where_clause (str): 条件子句
            params (tuple): 参数
            only_no_thumbnail (bool): 是否仅查询没有缩略图的文件
        返回值说明：
            int: 总记录数
        """
        if only_no_thumbnail:
            no_thumb_condition = "(thumbnail_path IS NULL OR thumbnail_path = '')"
            if "WHERE" in where_clause.upper():
                where_clause += f" AND {no_thumb_condition}"
            else:
                where_clause = f" WHERE {no_thumb_condition}"

        query = f"SELECT COUNT(*) as count FROM {table_name} {where_clause}"
        res = DBOperations.__execute(query, params, is_query=True, fetch_one=True)
        return res['count'] if res else 0

    @staticmethod
    def get_paths_by_md5(md5: str) -> List[str]:
        """
        用途：根据 MD5 获取所有相关的物理路径
        入参说明：
            md5 (str): 文件的 MD5 值
        返回值说明：
            List[str]: 路径列表
        """
        query = f"SELECT file_path FROM {DBManager.TABLE_FILE_INDEX} WHERE file_md5 = ?"
        rows = DBOperations.__execute(query, (md5,), is_query=True)
        return [r['file_path'] for r in rows]

    # --- 视频特征相关操作 (Video Features) ---

    @staticmethod
    def add_video_features(features: VideoFeatures) -> bool:
        """
        用途：添加或更新视频特征信息
        入参说明：
            features (VideoFeatures): 视频特征对象
        返回值说明：
            bool: 是否成功
        """
        query = f"""
            INSERT INTO {DBManager.TABLE_VIDEO_FEATURES} (md5, video_hashes, duration)
            VALUES (?, ?, ?)
            ON CONFLICT(md5) DO UPDATE SET
            video_hashes = excluded.video_hashes,
            duration = excluded.duration
        """
        params = (features.md5, features.video_hashes, features.duration)
        return DBOperations.__execute(query, params) > 0

    @staticmethod
    def get_video_features_by_md5(md5: str) -> Optional[VideoFeatures]:
        """
        用途：根据 MD5 获取视频特征
        入参说明：
            md5 (str): 视频 MD5
        返回值说明：
            Optional[VideoFeatures]: 视频特征对象 or None
        """
        query = f"SELECT * FROM {DBManager.TABLE_VIDEO_FEATURES} WHERE md5 = ?"
        row = DBOperations.__execute(query, (md5,), is_query=True, fetch_one=True)
        return VideoFeatures(**row) if row else None

    @staticmethod
    def clear_video_features() -> bool:
        """
        用途：清空视频特征表
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        return DBOperations.__clear_table(DBManager.TABLE_VIDEO_FEATURES)

    # --- 视频信息缓存相关操作 (Video Info Cache) ---

    @staticmethod
    def add_video_info_cache(info: VideoInfoCache) -> bool:
        """
        用途：添加或更新视频信息缓存
        入参说明：
            info (VideoInfoCache): 视频信息缓存对象
        返回值说明：
            bool: 是否成功
        """
        query = f"""
            INSERT INTO {DBManager.TABLE_VIDEO_INFO_CACHE} (path, video_name, md5, duration, video_hashes, thumbnail_path)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
            video_name = excluded.video_name,
            md5 = excluded.md5,
            duration = excluded.duration,
            video_hashes = excluded.video_hashes,
            thumbnail_path = excluded.thumbnail_path
        """
        params = (info.path, info.video_name, info.md5, info.duration, info.video_hashes, info.thumbnail_path)
        return DBOperations.__execute(query, params) > 0

    @staticmethod
    def get_video_info_cache_by_md5(md5: str) -> List[VideoInfoCache]:
        """
        用途：根据 MD5 获取缓存的视频信息列表
        入参说明：
            md5 (str): 视频 MD5
        返回值说明：
            List[VideoInfoCache]: 缓存对象列表
        """
        query = f"SELECT * FROM {DBManager.TABLE_VIDEO_INFO_CACHE} WHERE md5 = ?"
        rows = DBOperations.__execute(query, (md5,), is_query=True)
        return [VideoInfoCache(**r) for r in rows]

    @staticmethod
    def get_all_video_info_caches() -> List[VideoInfoCache]:
        """
        用途：获取所有视频信息缓存
        入参说明：无
        返回值说明：
            List[VideoInfoCache]: 缓存对象列表
        """
        query = f"SELECT * FROM {DBManager.TABLE_VIDEO_INFO_CACHE}"
        rows = DBOperations.__execute(query, is_query=True)
        return [VideoInfoCache(**r) for r in rows]

    @staticmethod
    def clear_video_info_cache() -> bool:
        """
        用途：清空视频信息缓存表
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        return DBOperations.__clear_table(DBManager.TABLE_VIDEO_INFO_CACHE)

    # --- 查重结果相关操作 (Duplicate Results) ---

    @staticmethod
    def clear_duplicate_results() -> bool:
        """
        用途：清空所有查重结果
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        DBOperations.__clear_table(DBManager.TABLE_DUPLICATE_FILES)
        DBOperations.__clear_table(DBManager.TABLE_DUPLICATE_GROUPS)
        return True

    @staticmethod
    def save_duplicate_results(results: List[DuplicateGroup]) -> bool:
        """
        用途：保存查重结果分组及其关联文件
        入参说明：
            results (List[DuplicateGroup]): 查重结果分组列表
        返回值说明：
            bool: 是否成功
        """
        if not results:
            return True
        conn = None
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            for group in results:
                # 1. 插入分组
                cursor.execute(
                    f"INSERT INTO {DBManager.TABLE_DUPLICATE_GROUPS} (group_id, checker_type) VALUES (?, ?)",
                    (group.group_id, group.checker_type)
                )
                # 2. 批量插入该组下的文件
                file_data = [
                    (group.group_id, f.file_name, f.file_path, f.file_md5, f.thumbnail_path, json.dumps(f.extra_info)) 
                    for f in group.files
                ]
                cursor.executemany(
                    f"INSERT INTO {DBManager.TABLE_DUPLICATE_FILES} (group_id, file_name, file_path, file_md5, thumbnail_path, extra_info) VALUES (?, ?, ?, ?, ?, ?)",
                    file_data
                )
            conn.commit()
            return True
        except Exception as e:
            LogUtils.error(f"保存查重结果失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_all_duplicate_results() -> List[DuplicateGroup]:
        """
        用途：获取数据库中所有的查重结果
        入参说明：无
        返回值说明：
            List[DuplicateGroup]: 查重分组列表
        """
        groups_data = DBOperations.__execute(
            f"SELECT group_id, checker_type FROM {DBManager.TABLE_DUPLICATE_GROUPS}", is_query=True
        )
        results = []
        for g in groups_data:
            files_data = DBOperations.__execute(
                f"SELECT * FROM {DBManager.TABLE_DUPLICATE_FILES} WHERE group_id = ?", 
                (g['group_id'],), is_query=True
            )
            files = [
                DuplicateFile(
                    file_name=f['file_name'],
                    file_path=f['file_path'],
                    file_md5=f['file_md5'],
                    thumbnail_path=f['thumbnail_path'],
                    extra_info=json.loads(f['extra_info']) if f['extra_info'] else {}
                ) for f in files_data
            ]
            results.append(DuplicateGroup(group_id=g['group_id'], checker_type=g['checker_type'], files=files))
        return results

    @staticmethod
    def delete_duplicate_file_by_path(file_path: str) -> bool:
        """
        用途：根据路径删除查重结果中的文件记录，若组内剩余文件不足2个则自动解散分组
        入参说明：
            file_path (str): 待删除的文件路径
        返回值说明：
            bool: 是否执行成功
        """
        # 1. 查找所属分组 ID
        row = DBOperations.__execute(
            f"SELECT group_id FROM {DBManager.TABLE_DUPLICATE_FILES} WHERE file_path = ?", 
            (file_path,), is_query=True, fetch_one=True
        )
        if not row:
            return True
        
        group_id = row['group_id']
        
        # 2. 删除文件记录
        DBOperations.__execute(f"DELETE FROM {DBManager.TABLE_DUPLICATE_FILES} WHERE file_path = ?", (file_path,))
        
        # 3. 检查并清理孤立分组
        count = DBOperations.get_file_count(DBManager.TABLE_DUPLICATE_FILES, "WHERE group_id = ?", (group_id,))
        if count < 2:
            DBOperations.__execute(f"DELETE FROM {DBManager.TABLE_DUPLICATE_FILES} WHERE group_id = ?", (group_id,))
            DBOperations.__execute(f"DELETE FROM {DBManager.TABLE_DUPLICATE_GROUPS} WHERE group_id = ?", (group_id,))
            LogUtils.info(f"由于成员不足，已清理查重组: {group_id}")
            
        return True

    # --- 缩略图相关操作 ---

    @staticmethod
    def update_thumbnail_path(file_path: str, thumbnail_path: str) -> bool:
        """
        用途：更新指定文件的缩略图路径
        入参说明：
            file_path (str): 文件路径
            thumbnail_path (str): 缩略图路径
        返回值说明：
            bool: 是否成功
        """
        query = f"UPDATE {DBManager.TABLE_FILE_INDEX} SET thumbnail_path = ? WHERE file_path = ?"
        return DBOperations.__execute(query, (thumbnail_path, file_path)) > 0

    @staticmethod
    def get_files_without_thumbnail() -> List[FileIndex]:
        """
        用途：获取所有没有缩略图的文件记录
        入参说明：无
        返回值说明：
            List[FileIndex]: 文件对象列表
        """
        query = f"SELECT * FROM {DBManager.TABLE_FILE_INDEX} WHERE thumbnail_path IS NULL OR thumbnail_path = ''"
        rows = DBOperations.__execute(query, is_query=True)
        return [FileIndex(**r) for r in rows]

    @staticmethod
    def clear_all_thumbnail_records() -> bool:
        """
        用途：清空所有文件记录中的缩略图路径字段
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        query = f"UPDATE {DBManager.TABLE_FILE_INDEX} SET thumbnail_path = NULL"
        return DBOperations.__execute(query) >= 0

    @staticmethod
    def get_file_index_by_path(file_path: str) -> Optional[FileIndex]:
        """
        用途：根据路径从索引表中获取单个文件信息
        入参说明：
            file_path (str): 文件路径
        返回值说明：
            Optional[FileIndex]: 文件索引对象，若不存在则返回 None
        """
        query = f"SELECT * FROM {DBManager.TABLE_FILE_INDEX} WHERE file_path = ?"
        row = DBOperations.__execute(query, (file_path,), is_query=True, fetch_one=True)
        return FileIndex(**row) if row else None
