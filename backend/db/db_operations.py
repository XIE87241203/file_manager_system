from datetime import datetime
from typing import List, Optional, Tuple, Set

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.db.db_manager import db_manager
from backend.db.processor_manager import processor_manager
from backend.model.db.already_entered_file_db_model import AlreadyEnteredFileDBModel
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModel
from backend.model.db.face_embedding_db_model import FaceEmbeddingDBModel
from backend.model.db.face_queue_item_db_model import FaceQueueItemDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.file_repo_detail_db_model import FileRepoDetailDBModel
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.db.image_feature_db_model import ImageFeatureDBModel
from backend.model.db.pending_entry_file_db_model import PendingEntryFileDBModel
from backend.model.db.video_feature_db_model import VideoFeatureDBModel
from backend.model.duplicate_group_result import DuplicateGroupResult
from backend.model.face_index_result import FaceIndexSummaryResult
from backend.model.cursor_pagination_result import CursorPaginationResult
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
    def get_missing_album_metadata(after_id: int, limit: int = 200) -> List[FileIndexDBModel]:
        """
        用途说明：分批获取缺少媒体信息的有效图片或视频索引。
        入参说明：after_id (int): 上一批最后主键；limit (int): 单批最大数量，默认 200。
        返回值说明：List[FileIndexDBModel] - 按主键升序排列的待补全记录。
        """
        return processor_manager.file_index_processor.get_missing_album_metadata(after_id, limit)

    @staticmethod
    def count_missing_album_metadata() -> int:
        """
        用途说明：统计当前仓库缺少媒体信息的有效媒体索引数量。
        入参说明：无。
        返回值说明：int - 待补全记录数量。
        """
        return processor_manager.file_index_processor.count_missing_album_metadata()

    @staticmethod
    def batch_update_album_metadata(data_list: List[FileIndexDBModel]) -> int:
        """
        用途说明：批量补全媒体索引的三个相册字段，仅覆盖空字段。
        入参说明：data_list (List[FileIndexDBModel]): 从文件读取的媒体信息列表。
        返回值说明：int - 实际更新的索引记录数量。
        """
        return processor_manager.file_index_processor.batch_update_album_metadata(data_list)

    @staticmethod
    def delete_files_by_not_scan_time(scan_time: str) -> int:
        """
        用途说明：删除扫描时间不等于指定时间戳的文件索引，并同步清理已失效的人脸数据。
        入参说明：scan_time (str): 当前有效的扫描时间戳。
        返回值说明：int: 删除的记录数量。
        """
        try:
            with db_manager.transaction() as conn:
                deleted_count: int = processor_manager.file_index_processor.delete_by_scan_time_not_equal(
                    scan_time, conn=conn
                )
                if not processor_manager.face_data_processor.cleanup_orphan_data(conn=conn):
                    raise RuntimeError(t('face_data_orphan_cleanup_failed'))
                return deleted_count
        except Exception as e:
            LogUtils.error(t('repo_delete_stale_files_error', error=str(e)))
            raise e

    @staticmethod
    def clear_all_file_index() -> bool:
        """
        用途说明：清空文件索引、重复组数据与人脸数据（使用事务确保原子性）。
        入参说明：无
        返回值说明：bool: 是否清空成功。
        """
        try:
            with db_manager.transaction() as conn:
                face_cleared: bool = processor_manager.face_data_processor.clear_all_data(conn=conn)
                if not face_cleared:
                    raise RuntimeError(t('face_data_operation_failed'))
                index_cleared: bool = processor_manager.file_index_processor.clear_all_table(conn=conn)
                return index_cleared
        except Exception as e:
            LogUtils.error(t('repo_clear_error', error=str(e)))
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
    def delete_file_index_by_path(file_path: str) -> bool:
        """
        用途说明：删除指定文件索引，并同步维护重复文件分组与人脸数据（使用事务确保原子性）。
        入参说明：file_path (str): 文件完整路径。
        返回值说明：bool: 是否删除成功。
        """
        try:
            with db_manager.transaction() as conn:
                # 1. 删除文件索引
                res1: bool = processor_manager.file_index_processor.delete_by_path(file_path, conn=conn)
                # 2. 从重复组中批量移除（虽然是单个，也调用批量接口）
                res2: bool = processor_manager.duplicate_group_processor.delete_files_by_paths([file_path], conn=conn)
                # 3. 清理该文件的人脸特征与处理状态
                res3: bool = processor_manager.face_data_processor.delete_by_path(file_path, conn=conn)
                if not res3:
                    raise RuntimeError(t('face_data_operation_failed'))
                return res1 and res2 and res3
        except Exception as e:
            LogUtils.error(t('repo_delete_crash', error=str(e)))
            return False

    @staticmethod
    def search_file_index_list(page: int, limit: int, sort_by: str, order: bool,
                               search_query: str, is_in_recycle_bin: bool = False,
                               file_type: Optional[str] = None) -> PaginationResult[FileIndexDBModel]:
        """
        用途说明：分页查询文件索引列表。
        """
        return processor_manager.file_index_processor.get_paged_list(page, limit, sort_by, order, search_query, is_in_recycle_bin, file_type)

    @staticmethod
    def search_album_file_list(limit: int, sort_by: str, order: bool,
                               search_query: str, file_types: List[str],
                               last_path: str = '') -> CursorPaginationResult[FileIndexDBModel]:
        """
        用途说明：按媒体路径游标查询相册媒体文件（图片/视频）列表，排除回收站文件。
        入参说明：
            limit (int): 每批条数。
            sort_by (str): 排序字段。
            order (bool): 是否为升序。
            search_query (str): 文件名搜索关键词。
            file_types (List[str]): 文件类型列表（如 ['image', 'video']）。
            last_path (str): 媒体路径游标，空字符串表示首批数据。
        返回值说明：CursorPaginationResult[FileIndexDBModel] - 不包含页码的游标分页结果。
        """
        return processor_manager.file_index_processor.get_album_paged_list(
            limit, sort_by, order, search_query, file_types, last_path
        )

    @staticmethod
    def search_history_file_index_list(page: int, limit: int, sort_by: str, order: bool,
                                       search_query: str, file_type: Optional[str] = None) -> PaginationResult[HistoryFileIndexDBModule]:
        """
        用途说明：分页查询历史文件索引列表。
        """
        return processor_manager.history_file_index_processor.get_paged_list(page, limit, sort_by, order, search_query, file_type)

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
    def get_files_by_scan_time(checkpoint: Optional[str], newer: bool,
                               limit: Optional[int] = None, offset: int = 0) -> List[FileIndexDBModel]:
        """
        用途说明：按扫描时间与查重时间点的关系获取文件列表（排除回收站文件）。
        入参说明：
            checkpoint (Optional[str]): 查重时间点，为 None 时 newer=True 返回全部、newer=False 返回空。
            newer (bool): True 取新索引文件，False 取旧索引文件。
            limit (Optional[int]): 单批返回上限；为 None 时返回全部，大库建议分批传入。
            offset (int): 分批查询偏移量，仅在传入 limit 时生效。
        返回值说明：List[FileIndexDBModel]: 文件索引模型列表（按主键 ID 升序）。
        """
        return processor_manager.file_index_processor.get_files_by_scan_time(checkpoint, newer, limit, offset)

    @staticmethod
    def count_files_by_scan_time(checkpoint: Optional[str], newer: bool) -> int:
        """
        用途说明：统计按扫描时间筛选的文件数量（排除回收站文件）。
        入参说明：
            checkpoint (Optional[str]): 查重时间点。
            newer (bool): True 统计新索引文件，False 统计旧索引文件。
        返回值说明：int: 符合条件的文件数量。
        """
        return processor_manager.file_index_processor.count_files_by_scan_time(checkpoint, newer)

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
        用途说明：批量将文件移入回收站，并同步维护重复分组与人脸队列（使用事务）。
        入参说明：file_paths (List[str]) - 需要移入回收站的文件完整路径列表。
        返回值说明：bool - 是否至少移动成功一条记录。
        """
        recycle_time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with db_manager.transaction() as conn:
                # 1. 移动到回收站
                res1: int = processor_manager.file_index_processor.move_to_recycle_bin(file_paths, recycle_time, conn=conn)
                # 2. 批量从查重结果中移除
                processor_manager.duplicate_group_processor.delete_files_by_paths(file_paths, conn=conn)
                # 3. 移除待识别队列项，避免继续识别已移入回收站的图片
                if not processor_manager.face_data_processor.delete_queue_by_paths(file_paths, conn=conn):
                    raise RuntimeError(t('face_queue_delete_failed'))
                return res1 > 0
        except Exception as e:
            LogUtils.error(t('repo_clear_error', error=str(e)))
            return False

    @staticmethod
    def batch_restore_from_recycle_bin(file_paths: List[str]) -> bool:
        """
        用途说明：批量将文件从回收站恢复。
        """
        return processor_manager.file_index_processor.restore_from_recycle_bin(file_paths) > 0

    @staticmethod
    def get_recycle_bin_paths_under(dir_prefixes: List[str]) -> Set[str]:
        """
        用途说明：查询指定目录（含子目录）下已移入回收站的文件路径集合（供整理扫描排除已删除文件）。
        入参说明：dir_prefixes (List[str]): 目录路径列表。
        返回值说明：Set[str] - 位于这些目录下且回收站标记非空的文件完整路径集合。
        """
        return processor_manager.file_index_processor.get_recycle_bin_paths_under(dir_prefixes)

    # --- 图片人脸索引相关操作 (Face Index) ---
    @staticmethod
    def enqueue_pending_face_images(pipeline_version: str) -> bool:
        """
        用途说明：将当前仓库全部未按指定流水线处理的图片去重加入人脸识别队列。
        入参说明：pipeline_version (str) - 当前人脸识别流水线版本。
        返回值说明：bool - 是否完成入队。
        """
        return processor_manager.face_data_processor.enqueue_pending_images(pipeline_version)

    @staticmethod
    def enqueue_face_images(images: List[FileIndexDBModel]) -> bool:
        """
        用途说明：将新建索引发现的图片去重加入人脸识别队列。
        入参说明：images (List[FileIndexDBModel]) - 新写入的图片索引记录，单批通常不超过 100 条。
        返回值说明：bool - 是否完成入队。
        """
        return processor_manager.face_data_processor.enqueue_images(images)

    @staticmethod
    def get_queued_face_images(after_queue_id: int = 0,
                               limit: int = 200) -> List[FaceQueueItemDBModel]:
        """
        用途说明：按队列 ID 游标分批读取待识别图片。
        入参说明：after_queue_id (int) - 上一批最后一个队列 ID；limit (int) - 单批最大数量。
        返回值说明：List[FaceQueueItemDBModel] - 有序的队列项列表。
        """
        return processor_manager.face_data_processor.get_queued_images(after_queue_id, limit)

    @staticmethod
    def get_face_queue_count() -> int:
        """
        用途说明：获取当前仓库待识别队列数量。
        入参说明：无
        返回值说明：int - 队列中的图片数量。
        """
        return processor_manager.face_data_processor.get_queue_count()

    @staticmethod
    def delete_face_queue_item(queue_id: int, file_md5: str) -> bool:
        """
        用途说明：按队列 ID 和 MD5 移除单个待识别项。
        入参说明：queue_id (int) - 队列主键；file_md5 (str) - 入队时的 MD5。
        返回值说明：bool - 是否移除成功。
        """
        return processor_manager.face_data_processor.delete_queue_item(queue_id, file_md5)

    @staticmethod
    def clear_face_queue() -> bool:
        """
        用途说明：清空当前仓库待识别队列，保留已保存的人脸特征和处理状态。
        入参说明：无
        返回值说明：bool - 是否清空成功。
        """
        return processor_manager.face_data_processor.clear_queue()

    @staticmethod
    def get_pending_face_images(pipeline_version: str, after_file_path: str = '',
                                limit: int = 200) -> List[FileIndexDBModel]:
        """
        用途说明：分批获取尚未按指定流水线处理的相册图片。
        入参说明：
            pipeline_version (str): 人脸模型与处理流水线版本。
            after_file_path (str): 上一批最后一个文件路径。
            limit (int): 单批最大记录数。
        返回值说明：List[FileIndexDBModel] - 按文件路径升序排列的图片列表。
        """
        return processor_manager.face_data_processor.get_pending_images(
            pipeline_version, after_file_path, limit
        )

    @staticmethod
    def get_face_index_summary(pipeline_version: str) -> FaceIndexSummaryResult:
        """
        用途说明：获取当前仓库的图片总数、待处理数量和人脸数量。
        入参说明：pipeline_version (str): 人脸模型与处理流水线版本。
        返回值说明：FaceIndexSummaryResult - 人脸索引统计结果。
        """
        return processor_manager.face_data_processor.get_index_summary(pipeline_version)

    @staticmethod
    def save_face_file_result(file_info: FileIndexDBModel, faces: List[FaceEmbeddingDBModel],
                              pipeline_version: str, queue_id: Optional[int] = None,
                              queued_md5: Optional[str] = None) -> bool:
        """
        用途说明：原子保存一张图片中的全部人脸、处理状态，并移除匹配的队列项。
        入参说明：
            file_info (FileIndexDBModel): 图片索引记录。
            faces (List[FaceEmbeddingDBModel]): 图片中的全部人脸，一人一条。
            pipeline_version (str): 人脸模型与处理流水线版本。
            queue_id (Optional[int]): 本次消费的队列主键。
            queued_md5 (Optional[str]): 入队时的 MD5。
        返回值说明：bool - 是否保存成功。
        """
        return processor_manager.face_data_processor.save_file_result(
            file_info, faces, pipeline_version, queue_id, queued_md5
        )

    @staticmethod
    def cleanup_orphan_face_data() -> bool:
        """
        用途说明：清理文件索引中已不存在的人脸数据。
        入参说明：无
        返回值说明：bool - 是否清理成功。
        """
        return processor_manager.face_data_processor.cleanup_orphan_data()

    @staticmethod
    def clear_face_data() -> bool:
        """
        用途说明：清空当前仓库的全部人脸特征、图片处理状态和待识别队列。
        入参说明：无
        返回值说明：bool - 是否清理成功。
        """
        return processor_manager.face_data_processor.clear_all_data()

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

    # --- 图片特征相关操作 (Image Features) ---

    @staticmethod
    def add_image_feature(features: ImageFeatureDBModel) -> bool:
        """
        用途说明：添加或更新图片感知哈希特征。
        入参说明：features (ImageFeatureDBModel): 图片特征模型。
        返回值说明：bool: 是否成功。
        """
        return processor_manager.image_feature_processor.add_or_update_feature(features)

    @staticmethod
    def get_image_feature_by_md5(md5: str) -> Optional[ImageFeatureDBModel]:
        """
        用途说明：根据 MD5 获取图片感知哈希特征。
        入参说明：md5 (str): 文件 MD5 值。
        返回值说明：Optional[ImageFeatureDBModel]: 图片特征模型，不存在则返回 None。
        """
        return processor_manager.image_feature_processor.get_feature_by_md5(md5)

    @staticmethod
    def get_image_features_by_md5s(md5s: List[str]) -> List[ImageFeatureDBModel]:
        """
        用途说明：根据 MD5 列表批量获取图片感知哈希特征（单次连接查询）。
        入参说明：md5s (List[str]): 文件 MD5 值列表，单批建议 <= 500。
        返回值说明：List[ImageFeatureDBModel]: 命中的图片特征模型列表。
        """
        return processor_manager.image_feature_processor.get_features_by_md5s(md5s)

    @staticmethod
    def add_image_features_batch(features: List[ImageFeatureDBModel]) -> bool:
        """
        用途说明：批量添加或更新图片感知哈希特征（单事务提交）。
        入参说明：features (List[ImageFeatureDBModel]): 图片特征模型列表，单批建议 <= 500。
        返回值说明：bool: 是否成功。
        """
        return processor_manager.image_feature_processor.add_or_update_features_batch(features)

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
    def save_incremental_results(results: List[DuplicateGroupDBModel], new_file_paths: List[str]) -> bool:
        """
        用途说明：保存新增查重结果，仅保留涉及新文件的分组并取代受影响的旧分组。
        入参说明：
            results (List[DuplicateGroupDBModel]): 查重器产出的全部分组。
            new_file_paths (List[str]): 本次新增查重的新文件路径列表。
        返回值说明：bool: 是否成功保存。
        """
        return processor_manager.duplicate_group_processor.save_incremental_results(results, new_file_paths)

    @staticmethod
    def self_heal_duplicate_results() -> None:
        """
        用途说明：清理失效的查重结果（删除已不存在文件的关联并解散残缺分组）。
        入参说明：无
        返回值说明：无
        """
        processor_manager.duplicate_group_processor.cleanup_invalid_results()

    @staticmethod
    def get_last_check_time() -> Optional[str]:
        """
        用途说明：获取最近一次查重完成的时间点。
        返回值说明：Optional[str]: 时间字符串，若从未查重则返回 None。
        """
        return processor_manager.duplicate_group_processor.get_last_check_time()

    @staticmethod
    def set_last_check_time(check_time: str, duration_seconds: float = 0.0) -> bool:
        """
        用途说明：记录最近一次查重完成的时间点与耗时。
        入参说明：
            check_time (str): 查重完成时间字符串。
            duration_seconds (float): 本次查重耗时（秒）。
        返回值说明：bool: 是否成功。
        """
        return processor_manager.duplicate_group_processor.set_last_check_time(check_time, duration_seconds)

    @staticmethod
    def get_last_check_duration() -> Optional[float]:
        """
        用途说明：获取最近一次查重的耗时（秒）。
        返回值说明：Optional[float]: 耗时秒数，若从未查重则返回 None。
        """
        return processor_manager.duplicate_group_processor.get_last_check_duration()

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
    def update_thumbnail_path_by_md5(file_md5: str, thumbnail_path: str) -> int:
        """
        用途说明：按文件 MD5 批量回填缩略图路径，使同内容文件（含副本）共享同一缩略图。
        入参说明：
            file_md5 (str): 文件 MD5 哈希值。
            thumbnail_path (str): 缩略图文件路径。
        返回值说明：int - 受影响的记录数。
        """
        return processor_manager.file_index_processor.update_thumbnail_path_by_md5(file_md5, thumbnail_path)

    @staticmethod
    def update_file_path(old_path: str, new_path: str) -> int:
        """
        用途说明：文件移动/改名后更新文件索引，并清理旧路径的人脸数据与队列项，下次识别时重新建立关联。
        入参说明：
            old_path (str): 索引中记录的原文件路径。
            new_path (str): 文件移动/改名后的新文件路径。
        返回值说明：int - 实际更新的记录数；0 表示原路径不在索引或新路径唯一约束冲突被忽略。
        """
        try:
            with db_manager.transaction() as conn:
                updated_count: int = processor_manager.file_index_processor.update_file_path(
                    old_path, new_path, conn=conn
                )
                if updated_count > 0:
                    if not processor_manager.face_data_processor.delete_by_path(old_path, conn=conn):
                        raise RuntimeError(t('face_data_operation_failed'))
                return updated_count
        except Exception as e:
            LogUtils.error(t('repo_update_index_error', old_path=old_path, error=str(e)))
            return 0

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
            LogUtils.error(t('repo_clear_error', error=str(e)))
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
        用途说明：从 file_index 表中统计所有文件的总数 and 总大小，并保存到 file_repo_detail 表中。
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
