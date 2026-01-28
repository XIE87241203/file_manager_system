from typing import Optional

from backend.common.log_utils import LogUtils
from backend.db.db_operations import DBOperations
from backend.file_repository.base_file_service import BaseFileService
from backend.file_repository.thumbnail.thumbnail_service import ThumbnailService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.file_repo_detail_db_model import FileRepoDetailDBModel
from backend.model.db.history_file_index_db_model import HistoryFileIndexDBModule
from backend.model.pagination_result import PaginationResult


class FileService(BaseFileService):
    """
    用途：文件仓库业务服务类，封装文件列表查询、清理等核心操作。
    """

    @staticmethod
    def search_file_index_list(page: int, limit: int, sort_by: str, order: bool, search_query: str, file_type: Optional[str] = None) -> PaginationResult[FileIndexDBModel]:
        """
        用途说明：搜索文件索引列表，支持分页、排序、关键词搜索及文件类型筛选。
        入参说明：
            page (int): 当前页码。
            limit (int): 每页记录数。
            sort_by (str): 排序字段。
            order (bool): 是否升序。
            search_query (str): 搜索关键词。
            is_in_recycle_bin (bool): 是否查询回收站文件。
            file_type (Optional[str]): 文件类型筛选（video/image/other）。
        返回值说明：PaginationResult[FileIndexDBModel] - 分页结果对象。
        """
        return DBOperations.search_file_index_list(page, limit, sort_by, order, search_query, False , file_type)


    @staticmethod
    def search_history_file_index_list(page: int, limit: int, sort_by: str, order: bool, search_query: str, file_type: Optional[str] = None) -> PaginationResult[HistoryFileIndexDBModule]:
        """
        用途说明：分页查询历史文件索引列表，支持文件类型筛选。
        入参说明：
            page (int): 当前页码。
            limit (int): 每页记录数。
            sort_by (str): 排序字段。
            order (bool): 是否升序。
            search_query (str): 搜索关键词。
            file_type (Optional[str]): 文件类型筛选 (video/image/other)
        返回值说明：PaginationResult[HistoryFileIndexDBModule] - 分页结果对象。
        """
        return DBOperations.search_history_file_index_list(page, limit, sort_by, order, search_query, file_type)

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
            
            # 4. 同步更新详情统计
            FileService.calculate_repo_detail()

            LogUtils.info(f"文件仓库已清空 (包含历史记录: {clear_history})")
            return True
        except Exception as e:
            LogUtils.error(f"清理仓库过程发生异常: {e}")
            return False

    @staticmethod
    def clear_history_repository() -> bool:
        """
        用途说明：仅清空历史文件索引库 (history_file_index)
        返回值说明：bool: 是否成功
        """
        try:
            if DBOperations.clear_history_index():
                LogUtils.info("历史文件索引库已清空")
                return True
            return False
        except Exception as e:
            LogUtils.error(f"清空历史仓库失败: {e}")
            return False

    @staticmethod
    def clear_video_features() -> bool:
        """
        用途：清空视频特征指纹库。
        返回值说明：
            bool: 是否成功
        """
        return DBOperations.clear_video_features()

    @staticmethod
    def get_repo_detail() -> Optional[FileRepoDetailDBModel]:
        """
        用途说明：获取文件仓库详情。
        返回值说明：Optional[FileRepoDetailDBModel] - 仓库详情对象。
        """
        return DBOperations.get_repo_detail()

    @staticmethod
    def calculate_repo_detail() -> Optional[FileRepoDetailDBModel]:
        """
        用途说明：计算并保存文件仓库详情。
        返回值说明：Optional[FileRepoDetailDBModel] - 计算后的仓库详情对象。
        """
        return DBOperations.calculate_and_save_repo_detail()
