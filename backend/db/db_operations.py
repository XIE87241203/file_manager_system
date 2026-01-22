from datetime import datetime
from typing import List, Optional, Tuple, Set

from backend.common.log_utils import LogUtils
from backend.db.db_manager import db_manager
from backend.db.processor_manager import processor_manager
from backend.model.db.already_entered_file_db_model import AlreadyEnteredFileDBModel
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.file_repo_detail_db_model import FileRepoDetailDBModel
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.db.pending_entry_file_db_model import PendingEntryFileDBModel
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
        用途说明：批量插入文件索引数据。
        入参说明：data_list (List[FileIndexDBModel]): 待入库的文件索引模型列表。
        返回值说明：bool: 是否插入成功。
        """
        return bool(processor_manager.file_index_processor.batch_insert_data(data_list))

    @staticmethod
    def batch_update_files_scan_time(file_paths: List[str], scan_time: str) -> bool:
        """
        用途说明：批量更新文件的扫描时间戳。
        入参说明：
            file_paths (List[str]): 需要更新的文件路径列表。
            scan_time (str): 新的扫描时间字符串。
        返回值说明：bool: 是否更新成功。
        """
        return bool(processor_manager.file_index_processor.batch_update_scan_time(file_paths, scan_time))

    @staticmethod
    def delete_files_by_not_scan_time(scan_time: str) -> int:
        """
        用途说明：删除扫描时间不等于指定时间戳的文件索引（用于清理已失效的文件）。
        入参说明：scan_time (str): 当前有效的扫描时间戳。
        返回值说明：int: 删除的记录数量。
        """
        return processor_manager.file_index_processor.delete_by_scan_time_not_equal(scan_time)

    @staticmethod
    def clear_all_file_index() -> bool:
        """
        用途说明：清空文件索引及关联的重复组数据（使用事务确保原子性）。
        入参说明：无
        返回值说明：bool: 是否清空成功。
        """
        try:
            with db_manager.transaction() as conn:
                res1: bool = processor_manager.file_index_processor.clear_all_table()
                res2: bool = processor_manager.duplicate_group_processor.clear_all_table()
                return res1 and res2
        except Exception:
            return False

    @staticmethod
    def clear_history_index() -> bool:
        """
        用途说明：清空历史记录表。
        入参说明：无
        返回值说明：bool: 是否清空成功。
        """
        return processor_manager.history_file_index_processor.clear_all_table()

    @staticmethod
    def copy_file_index_to_history() -> int:
        """
        用途说明：将当前所有文件索引数据备份到历史索引表中。
        入参说明：无
        返回值说明：int: 成功备份的记录条数。
        """
        return processor_manager.history_file_index_processor.copy_file_index_to_history()

    @staticmethod
    def get_file_by_path(file_path: str) -> Optional[FileIndexDBModel]:
        """
        用途说明：通过文件路径获取文件索引详情。
        入参说明：file_path (str): 文件完整路径。
        返回值说明：Optional[FileIndexDBModel]: 文件详情模型，不存在则返回 None。
        """
        return processor_manager.file_index_processor.get_file_index_by_path(file_path)

    @staticmethod
    def delete_file_index_by_file_id(file_id: int) -> bool:
        """
        用途说明：删除指定文件索引，并同步维护重复文件分组（使用事务确保原子性）。
        入参说明：file_id (int): 文件 ID。
        返回值说明：bool: 是否删除成功。
        """
        try:
            with db_manager.transaction() as conn:
                res1: bool = processor_manager.file_index_processor.delete_by_id(file_id, conn=conn)
                res2: bool = processor_manager.duplicate_group_processor.delete_file_by_id(file_id, conn=conn)
                return res1 and res2
        except Exception:
            return False

    @staticmethod
    def search_file_index_list(page: int, limit: int, sort_by: str, order: bool,
                               search_query: str, is_in_recycle_bin: bool = False) -> PaginationResult[FileIndexDBModel]:
        """
        用途说明：分页查询文件索引列表。
        """
        return processor_manager.file_index_processor.get_paged_list(page, limit, sort_by, order, search_query, is_in_recycle_bin)

    @staticmethod
    def search_history_file_index_list(page: int, limit: int, sort_by: str, order: bool,
                                       search_query: str) -> PaginationResult[HistoryFileIndexDBModule]:
        """
        用途说明：分页查询历史文件索引列表。
        """
        return processor_manager.history_file_index_processor.get_paged_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def get_file_index_list_by_condition(offset: int, limit: int,
                                         only_no_thumbnail: bool = False) -> List[FileIndexDBModel]:
        """
        用途说明：按条件获取文件索引列表。
        """
        return processor_manager.file_index_processor.get_list_by_condition(offset, limit, only_no_thumbnail)

    @staticmethod
    def get_file_index_count(only_no_thumbnail: bool = False) -> int:
        """
        用途说明：获取符合条件的文件总数。
        """
        return processor_manager.file_index_processor.get_count(only_no_thumbnail)

    @staticmethod
    def check_file_md5_exists(file_md5: str) -> bool:
        """
        用途说明：检查 MD5 是否已存在。
        """
        return processor_manager.file_index_processor.check_md5_exists(file_md5)

    @staticmethod
    def check_file_path_exists(file_path: str) -> bool:
        """
        用途说明：检查文件路径是否已存在。
        """
        return processor_manager.file_index_processor.check_path_exists(file_path)

    @staticmethod
    def batch_move_to_recycle_bin(file_paths: List[str]) -> bool:
        """
        用途说明：批量将文件移入回收站，并同步维护重复分组（使用事务）。
        """
        recycle_time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with db_manager.transaction() as conn:
                file_ids: List[int] = processor_manager.file_index_processor.get_ids_by_paths(file_paths, conn=conn)
                res1: int = processor_manager.file_index_processor.move_to_recycle_bin(file_paths, recycle_time, conn=conn)
                for f_id in file_ids:
                    processor_manager.duplicate_group_processor.delete_file_by_id(f_id, conn=conn)
                return res1 > 0
        except Exception:
            return False

    @staticmethod
    def batch_restore_from_recycle_bin(file_paths: List[str]) -> bool:
        """
        用途说明：批量将文件从回收站恢复。
        """
        return processor_manager.file_index_processor.restore_from_recycle_bin(file_paths) > 0

    # --- 视频特征相关操作 (Video Features) ---

    @staticmethod
    def add_video_features(features: VideoFeatureDBModel) -> bool:
        """
        用途说明：添加或更新视频特征。
        """
        return processor_manager.video_feature_processor.add_or_update_feature(features)

    @staticmethod
    def get_video_features_by_md5(md5: str) -> Optional[VideoFeatureDBModel]:
        """
        用途说明：根据 MD5 获取视频特征。
        """
        return processor_manager.video_feature_processor.get_feature_by_md5(md5)

    @staticmethod
    def clear_video_features() -> bool:
        """
        用途说明：清空视频特征库。
        """
        return processor_manager.video_feature_processor.clear_video_features()

    @staticmethod
    def get_video_file_info(file_path: str) -> Optional[VideoFileInfoResult]:
        """
        用途说明：获取完整的视频文件详情（包含索引与特征）。
        """
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
        """
        用途说明：清空查重结果表。
        """
        return processor_manager.duplicate_group_processor.clear_all_table()

    @staticmethod
    def save_duplicate_results(results: List[DuplicateGroupDBModel]) -> bool:
        """
        用途说明：批量保存查重结果.
        """
        return processor_manager.duplicate_group_processor.batch_save_duplicate_groups(results)

    @staticmethod
    def get_all_duplicate_results(page: int, limit: int, similarity_type: Optional[str] = None) -> PaginationResult[DuplicateGroupResult]:
        """
        用途说明：分页获取重复文件分组，支持相似度类型筛选。
        """
        return processor_manager.duplicate_group_processor.get_duplicate_groups_paged(page, limit, similarity_type)

    @staticmethod
    def get_duplicate_group_count() -> int:
        """
        用途说明：获取重复组总数。
        """
        return processor_manager.duplicate_group_processor.get_group_count()

    @staticmethod
    def get_latest_duplicate_check_time() -> Optional[str]:
        """
        用途说明：获取最近一次查重的时间（取第一条查重组的创建时间）。
        返回值说明：Optional[str]: 格式化后的时间字符串，若无数据则返回 None。
        """
        # 直接通过 processor 获取
        res = processor_manager.duplicate_group_processor.get_duplicate_groups_paged(page=1, limit=1)
        if res and res.list:
            return res.list[0].create_time
        return None

    # --- 缩略图相关操作 ---

    @staticmethod
    def update_thumbnail_path(file_path: str, thumbnail_path: str) -> bool:
        """
        用途说明：更新指定文件的缩略图路径。
        入参说明：
            file_path (str): 文件完整路径。
            thumbnail_path (str): 缩略图文件路径。
        返回值说明：bool: 是否更新成功。
        """
        return processor_manager.file_index_processor.update_thumbnail_path(file_path, thumbnail_path)

    @staticmethod
    def get_files_without_thumbnail() -> List[FileIndexDBModel]:
        """
        用途说明：获取所有缺失缩略图的文件。
        入参说明：无
        返回值说明：List[FileIndexDBModel]: 无缩略图的文件索引模型列表。
        """
        return processor_manager.file_index_processor.get_list_by_condition(0, 0, True)

    @staticmethod
    def clear_all_thumbnail_records() -> bool:
        """
        用途说明：清空数据库中所有文件的缩略图路径记录。
        入参说明：无
        返回值说明：bool: 是否成功执行清空操作。
        """
        return bool(processor_manager.file_index_processor.clear_all_thumbnails() >= 0)

    # --- 曾录入文件名库相关操作 (原忽略文件库) ---

    @staticmethod
    def add_already_entered_files(file_names: List[str]) -> bool:
        """
        用途说明：批量添加曾录入文件名。
        """
        return bool(processor_manager.already_entered_file_processor.add_already_entered_files(file_names))

    @staticmethod
    def search_already_entered_file_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[AlreadyEnteredFileDBModel]:
        """
        用途说明：分页查询曾录入文件名。
        """
        return processor_manager.already_entered_file_processor.get_paged_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def clear_already_entered_repository() -> bool:
        """
        用途说明：清空曾录入文件名库。
        """
        return processor_manager.already_entered_file_processor.clear_all_table()

    # --- 待录入文件库相关操作 ---

    @staticmethod
    def add_pending_entry_files(file_names: List[str]) -> int:
        """
        用途说明：批量添加待录入文件名。仅针对真正插入成功的条目清理批量检测结果表。
        入参说明：file_names (List[str]): 待录入的文件名列表。
        返回值说明：int: 成功录入的数量。
        """
        try:
            with db_manager.transaction() as conn:
                # 1. 记录插入前库中已存在的名单 (去重，提高查询效率)
                unique_names: List[str] = list(set(file_names))
                pre_existing_names: Set[str] = set(processor_manager.pending_entry_file_processor.get_existing_names(unique_names, conn=conn))
                
                # 2. 执行插入 (INSERT OR IGNORE)
                count: int = processor_manager.pending_entry_file_processor.add_pending_entry_files(file_names, conn=conn)
                
                # 3. 如果有新增录入成功，找出这部分名单
                if count > 0:
                    # 插入后再次查询这组名单在库中的情况
                    post_existing_names: Set[str] = set(processor_manager.pending_entry_file_processor.get_existing_names(unique_names, conn=conn))
                    
                    # 真正“变身成功”的名单 = 插入后存在的 - 插入前就存在的
                    newly_added_names: List[str] = list(post_existing_names - pre_existing_names)
                    
                    # 4. 仅清理这部分真正新增的检测结果
                    if newly_added_names:
                        processor_manager.batch_check_processor.delete_results_by_names(newly_added_names, conn=conn)
                
                return count
        except Exception as e:
            LogUtils.error(f"批量录入待录入文件并差异清理检测结果失败: {e}")
            return 0

    @staticmethod
    def search_pending_entry_file_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[PendingEntryFileDBModel]:
        """
        用途说明：分页查询待录入文件名。
        """
        return processor_manager.pending_entry_file_processor.get_paged_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def clear_pending_entry_repository() -> bool:
        """
        用途说明：清空待录入文件名库。
        """
        return processor_manager.pending_entry_file_processor.clear_all_table()

    # --- 文件仓库详情统计相关操作 ---

    @staticmethod
    def calculate_and_save_repo_detail() -> Optional[FileRepoDetailDBModel]:
        """
        用途说明：从 file_index 表中统计所有文件的总数和总大小，并保存到 file_repo_detail 表中。
        返回值说明：最新的 FileRepoDetailDBModel 对象，计算失败则返回 None。
        """
        stats: Tuple[int, int] = processor_manager.file_index_processor.get_total_stats()
        total_count, total_size = stats
        update_time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if processor_manager.file_repo_detail_processor.update_detail(total_count, total_size, update_time):
            return processor_manager.file_repo_detail_processor.get_detail()
        return None

    @staticmethod
    def get_repo_detail() -> Optional[FileRepoDetailDBModel]:
        """
        用途说明：从数据库中获取缓存的文件仓库详情。
        返回值说明：Optional[FileRepoDetailDBModel]: 统计详情模型，不存在则返回 None。
        """
        return processor_manager.file_repo_detail_processor.get_detail()
