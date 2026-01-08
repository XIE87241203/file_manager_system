from typing import List, Tuple, Optional, Union, Any, Dict
import json
import sqlite3
from backend.db.db_manager import db_manager, DBManager
from backend.common.log_utils import LogUtils
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModule
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.db.video_feature_db_model import VideoFeatureDBModel
from backend.model.pagination_result import PaginationResult
from backend.model.video_file_info_result import VideoFileInfoResult


class DBOperations:
    """
    用途：数据库操作类，负责所有数据的增删改查业务逻辑
    """

    # --- 文件索引相关操作 (File Index & History) ---

    @staticmethod
    def clear_all_file_index() -> bool:
        return (db_manager.file_index_processor.clear_all_table() and
                db_manager.duplicate_group_processor.clear_all_table())

    @staticmethod
    def clear_history_index() -> bool:
        return db_manager.history_file_index_processor.clear_all_table()

    @staticmethod
    def get_file_by_path(file_path: str) -> Optional[FileIndexDBModel]:
        return db_manager.file_index_processor.get_file_index_by_path(file_path)

    @staticmethod
    def delete_file_index_by_file_id(file_id: int) -> bool:
        return (db_manager.file_index_processor.delete_by_id(file_id) and
                db_manager.duplicate_group_processor.delete_file_by_id(file_id))

    @staticmethod
    def search_file_index_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[FileIndexDBModel]:
        return db_manager.file_index_processor.get_paged_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def search_history_file_index_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[HistoryFileIndexDBModule]:
        return db_manager.history_file_index_processor.get_paged_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def get_file_index_list_by_condition(offset: int, limit: int, only_no_thumbnail: bool = False) -> List[FileIndexDBModel]:
        return db_manager.file_index_processor.get_list_by_condition(offset, limit, only_no_thumbnail)

    @staticmethod
    def get_file_index_count(only_no_thumbnail: bool = False) -> int:
        return db_manager.file_index_processor.get_count(only_no_thumbnail)

    # --- 视频特征相关操作 (Video Features) ---

    @staticmethod
    def add_video_features(features: VideoFeatureDBModel) -> bool:
        return db_manager.video_feature_processor.add_or_update_feature(features)

    @staticmethod
    def get_video_features_by_md5(md5: str) -> Optional[VideoFeatureDBModel]:
        return db_manager.video_feature_processor.get_feature_by_md5(md5)


    @staticmethod
    def clear_video_features() -> bool:
        return db_manager.video_feature_processor.clear_video_features()

    @staticmethod
    def get_video_file_info(file_path: str) -> Optional[VideoFileInfoResult]:
        file_index = DBOperations.get_file_by_path(file_path)
        if not file_index:
            return None
        video_feature = DBOperations.get_video_features_by_md5(file_index.file_md5)
        if not video_feature:
            return None
        return VideoFileInfoResult(file_index=file_index, video_feature=video_feature)



    # --- 查重结果相关操作 (Duplicate Results) ---

    @staticmethod
    def clear_duplicate_results() -> bool:
        """
        用途：清空所有查重结果
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        return db_manager.duplicate_group_processor.clear_all_table()

    @staticmethod
    def save_duplicate_results(results: List[DuplicateGroupDBModule]) -> bool:
        return db_manager.duplicate_group_processor.batch_save_duplicate_groups(results)
    # todo 修改至此
    @staticmethod
    def get_all_duplicate_results() -> List[DuplicateGroupDBModule]:
        """
        用途：获取数据库中所有的查重结果
        入参说明：无
        返回值说明：
            List[DuplicateGroupDBModule]: 查重分组列表
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
                DuplicateItem(
                    file_name=f['file_name'],
                    file_path=f['file_path'],
                    file_md5=f['file_md5'],
                    thumbnail_path=f['thumbnail_path'],
                    extra_info=json.loads(f['extra_info']) if f['extra_info'] else {}
                ) for f in files_data
            ]
            results.append(
                DuplicateGroupDBModule(group_id=g['group_id'], checker_type=g['checker_type'], file_ids=files))
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
        DBOperations.__execute(f"DELETE FROM {DBManager.TABLE_DUPLICATE_FILES} WHERE file_path = ?",
                               (file_path,))

        # 3. 检查并清理孤立分组
        count = DBOperations.get_file_count(DBManager.TABLE_DUPLICATE_FILES, "WHERE group_id = ?",
                                            (group_id,))
        if count < 2:
            DBOperations.__execute(
                f"DELETE FROM {DBManager.TABLE_DUPLICATE_FILES} WHERE group_id = ?", (group_id,))
            DBOperations.__execute(
                f"DELETE FROM {DBManager.TABLE_DUPLICATE_GROUPS} WHERE group_id = ?", (group_id,))
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
    def get_files_without_thumbnail() -> List[FileIndexDBModel]:
        """
        用途：获取所有没有缩略图的文件记录
        入参说明：无
        返回值说明：
            List[FileIndex]: 文件对象列表
        """
        query = f"SELECT * FROM {DBManager.TABLE_FILE_INDEX} WHERE thumbnail_path IS NULL OR thumbnail_path = ''"
        rows = DBOperations.__execute(query, is_query=True)
        return [FileIndexDBModel(**r) for r in rows]

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
    def get_file_index_by_path(file_path: str) -> Optional[FileIndexDBModel]:
        """
        用途：根据路径从索引表中获取单个文件信息
        入参说明：
            file_path (str): 文件路径
        返回值说明：
            Optional[FileIndex]: 文件索引对象，若不存在则返回 None
        """
        query = f"SELECT * FROM {DBManager.TABLE_FILE_INDEX} WHERE file_path = ?"
        row = DBOperations.__execute(query, (file_path,), is_query=True, fetch_one=True)
        return FileIndexDBModel(**row) if row else None
