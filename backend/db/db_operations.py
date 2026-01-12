from typing import List, Optional

from backend.db.db_manager import DBManager
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
    用途：数据库操作类，负责封装所有跨 Processor 的业务逻辑，并提供事务支持。
    """

    # --- 文件索引相关操作 (File Index & History) ---
    @staticmethod
    def batch_insert_files_index(data_list: List[FileIndexDBModel]) -> bool:
        """
        用途：批量插入文件索引
        """
        return bool(processor_manager.file_index_processor.batch_insert_data(data_list))

    @staticmethod
    def batch_update_files_scan_time(file_paths: List[str], scan_time: str) -> bool:
        """
        用途：批量更新文件扫描时间
        """
        return bool(processor_manager.file_index_processor.batch_update_scan_time(file_paths, scan_time))

    @staticmethod
    def delete_files_by_not_scan_time(scan_time: str) -> int:
        """
        用途：删除扫描时间不等于指定时间戳的文件索引
        """
        return processor_manager.file_index_processor.delete_by_scan_time_not_equal(scan_time)

    @staticmethod
    def clear_all_file_index() -> bool:
        """
        用途：清空文件索引及关联的重复组数据（已优化：使用事务确保原子性）
        """
        try:
            with DBManager.transaction() as conn:
                # 注意：此处假设 Processor 的 clear 方法未来也会支持 conn 参数
                # 目前由于 _clear_table 是直接执行 SQL，我们先保持现状或进一步重构
                res1: bool = processor_manager.file_index_processor.clear_all_table()
                res2: bool = processor_manager.duplicate_group_processor.clear_all_table()
                return res1 and res2
        except Exception:
            return False

    @staticmethod
    def clear_history_index() -> bool:
        """
        用途：清空历史记录表
        """
        return processor_manager.history_file_index_processor.clear_all_table()

    @staticmethod
    def copy_file_index_to_history() -> int:
        """
        用途：将当前所有文件索引数据备份到历史索引表中
        """
        return processor_manager.history_file_index_processor.copy_file_index_to_history()

    @staticmethod
    def get_file_by_path(file_path: str) -> Optional[FileIndexDBModel]:
        """
        用途：通过路径获取文件详情
        """
        return processor_manager.file_index_processor.get_file_index_by_path(file_path)

    @staticmethod
    def delete_file_index_by_file_id(file_id: int) -> bool:
        """
        用途：删除指定文件索引，并同步维护重复文件分组（已优化：使用事务确保原子性）
        入参说明：
            file_id (int): 文件 ID
        返回值说明：
            bool: 操作是否全部成功
        """
        try:
            with DBManager.transaction() as conn:
                # 1. 从主索引表删除
                res1: bool = processor_manager.file_index_processor.delete_by_id(file_id, conn=conn)
                # 2. 从重复组记录中移除，并处理分组解散逻辑
                res2: bool = processor_manager.duplicate_group_processor.delete_file_by_id(file_id, conn=conn)
                return res1 and res2
        except Exception:
            return False

    @staticmethod
    def search_file_index_list(page: int, limit: int, sort_by: str, order: bool,
                               search_query: str) -> PaginationResult[FileIndexDBModel]:
        return processor_manager.file_index_processor.get_paged_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def search_history_file_index_list(page: int, limit: int, sort_by: str, order: bool,
                                       search_query: str) -> PaginationResult[HistoryFileIndexDBModule]:
        return processor_manager.history_file_index_processor.get_paged_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def get_file_index_list_by_condition(offset: int, limit: int,
                                         only_no_thumbnail: bool = False) -> List[FileIndexDBModel]:
        return processor_manager.file_index_processor.get_list_by_condition(offset, limit, only_no_thumbnail)

    @staticmethod
    def get_file_index_count(only_no_thumbnail: bool = False) -> int:
        return processor_manager.file_index_processor.get_count(only_no_thumbnail)

    @staticmethod
    def check_file_md5_exists(file_md5: str) -> bool:
        return processor_manager.file_index_processor.check_md5_exists(file_md5)

    @staticmethod
    def check_file_path_exists(file_path: str) -> bool:
        return processor_manager.file_index_processor.check_path_exists(file_path)

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
        file_index: Optional[FileIndexDBModel] = DBOperations.get_file_by_path(file_path)
        if not file_index:
            return None
        video_feature: Optional[VideoFeatureDBModel] = DBOperations.get_video_features_by_md5(file_index.file_md5)
        if not video_feature:
            return None
        return VideoFileInfoResult(file_index=file_index, video_feature=video_feature)

    # --- 查重结果相关操作 (Duplicate Results) ---

    @staticmethod
    def clear_duplicate_results() -> bool:
        return processor_manager.duplicate_group_processor.clear_all_table()

    @staticmethod
    def save_duplicate_results(results: List[DuplicateGroupDBModule]) -> bool:
        return processor_manager.duplicate_group_processor.batch_save_duplicate_groups(results)

    @staticmethod
    def get_all_duplicate_results(page: int, limit: int) -> PaginationResult[DuplicateGroupResult]:
        return processor_manager.duplicate_group_processor.get_duplicate_groups_paged(page, limit)

    @staticmethod
    def get_duplicate_group_count() -> int:
        """
        用途：获取重复分组总数
        """
        return processor_manager.duplicate_group_processor.get_group_count()

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
