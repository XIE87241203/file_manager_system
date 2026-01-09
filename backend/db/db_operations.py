from typing import List, Optional

from backend.db.processor_manager import processor_manager
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModule
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.db.video_feature_db_model import VideoFeatureDBModel
from backend.model.duplicate_group_result import DuplicateGroupResult
from backend.model.pagination_result import PaginationResult
from backend.model.video_file_info_result import VideoFileInfoResult


class DBOperations:
    """
    用途：数据库操作类，负责所有数据的增删改查业务逻辑
    """

    # --- 文件索引相关操作 (File Index & History) ---
    @staticmethod
    def batch_insert_files_index(data_list: List[FileIndexDBModel]) -> bool:
        return processor_manager.file_index_processor.batch_insert_data(data_list)

    @staticmethod
    def clear_all_file_index() -> bool:
        return (processor_manager.file_index_processor.clear_all_table() and
                processor_manager.duplicate_group_processor.clear_all_table())

    @staticmethod
    def clear_history_index() -> bool:
        return processor_manager.history_file_index_processor.clear_all_table()

    @staticmethod
    def copy_file_index_to_history() -> int:
        """
        用途：将当前所有文件索引数据备份到历史索引表中
        入参说明：无
        返回值说明：
            int: 成功备份的记录数
        """
        return processor_manager.history_file_index_processor.copy_file_index_to_history()

    @staticmethod
    def get_file_by_path(file_path: str) -> Optional[FileIndexDBModel]:
        return processor_manager.file_index_processor.get_file_index_by_path(file_path)

    @staticmethod
    def delete_file_index_by_file_id(file_id: int) -> bool:
        return (processor_manager.file_index_processor.delete_by_id(file_id) and
                processor_manager.duplicate_group_processor.delete_file_by_id(file_id))

    @staticmethod
    def search_file_index_list(page: int, limit: int, sort_by: str, order: bool,
                               search_query: str) -> PaginationResult[FileIndexDBModel]:
        return processor_manager.file_index_processor.get_paged_list(page, limit, sort_by, order,
                                                              search_query)

    @staticmethod
    def search_history_file_index_list(page: int, limit: int, sort_by: str, order: bool,
                                       search_query: str) -> PaginationResult[
        HistoryFileIndexDBModule]:
        return processor_manager.history_file_index_processor.get_paged_list(page, limit, sort_by, order,
                                                                      search_query)

    @staticmethod
    def get_file_index_list_by_condition(offset: int, limit: int,
                                         only_no_thumbnail: bool = False) -> List[FileIndexDBModel]:
        return processor_manager.file_index_processor.get_list_by_condition(offset, limit,
                                                                     only_no_thumbnail)

    @staticmethod
    def get_file_index_count(only_no_thumbnail: bool = False) -> int:
        return processor_manager.file_index_processor.get_count(only_no_thumbnail)

    # --- 视频特征相关操作 (Video Features) ---

    @staticmethod
    def add_video_features(features: VideoFeatureDBModel) -> bool:
        return processor_manager.video_feature_processor.add_or_update_feature(features)

    @staticmethod
    def get_video_features_by_md5(md5: str) -> Optional[VideoFeatureDBModel]:
        return processor_manager.video_feature_processor.get_feature_by_md5(md5)

    @staticmethod
    def clear_video_features() -> bool:
        return processor_manager.video_feature_processor.clear_video_features()

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
        return processor_manager.duplicate_group_processor.clear_all_table()

    @staticmethod
    def save_duplicate_results(results: List[DuplicateGroupDBModule]) -> bool:
        return processor_manager.duplicate_group_processor.batch_save_duplicate_groups(results)

    @staticmethod
    def get_all_duplicate_results(page: int,
                                  limit: int) -> PaginationResult[DuplicateGroupResult]:
        return processor_manager.duplicate_group_processor.get_duplicate_groups_paged(page, limit)

    # --- 缩略图相关操作 ---

    @staticmethod
    def update_thumbnail_path(file_path: str, thumbnail_path: str) -> bool:
        return processor_manager.file_index_processor.update_thumbnail_path(file_path, thumbnail_path)

    @staticmethod
    def get_files_without_thumbnail() -> List[FileIndexDBModel]:
        return processor_manager.file_index_processor.get_list_by_condition(0, 0, True)

    @staticmethod
    def clear_all_thumbnail_records() -> bool:
        return processor_manager.file_index_processor.clear_all_thumbnails()
