from backend.common.log_utils import LogUtils
from backend.db.db_operations import DBOperations
from backend.file_repository.base_file_service import BaseFileService
from backend.file_repository.thumbnail.thumbnail_service import ThumbnailService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.pagination_result import PaginationResult


class FileService(BaseFileService):
    """
    用途：文件仓库业务服务类，封装文件列表查询、清理等核心操作。
    """

    @staticmethod
    def search_file_index_list(page: int, limit: int, sort_by: str, order: bool, search_query: str, is_in_recycle_bin: bool = False) -> PaginationResult[FileIndexDBModel]:
        return DBOperations.search_file_index_list(page, limit, sort_by, order, search_query, is_in_recycle_bin)


    @staticmethod
    def search_history_file_index_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[HistoryFileIndexDBModule]:
        return DBOperations.search_history_file_index_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def clear_repository(clear_history: bool) -> bool:
        """
        用途：清空文件索引数据库，并强制清理所有缩略图文件。
        入参说明：
            clear_history (bool): 是否同步清空历史索引表。
        返回值说明：
            bool: 是否全部清理成功
        """
        try:
            # 1. 物理删除所有缩略图文件及清空生成器队列
            ThumbnailService.clear_all_thumbnails()

            # 2. 清空当前文件索引表
            if not DBOperations.clear_all_file_index():
                return False
            
            # 3. 若需要，清空历史索引表
            if clear_history:
                if not DBOperations.clear_history_index():
                    return False
            
            LogUtils.info(f"文件仓库已清空 (包含历史记录: {clear_history})")
            return True
        except Exception as e:
            LogUtils.error(f"清理仓库过程发生异常: {e}")
            return False

    @staticmethod
    def clear_video_features() -> bool:
        """
        用途：清空视频特征指纹库。
        返回值说明：
            bool: 是否成功
        """
        return DBOperations.clear_video_features()
