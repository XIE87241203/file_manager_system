import os
from typing import Optional

from backend.common.i18n_utils import t
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
    def update_file_index_path(old_path: str, new_path: str) -> bool:
        """
        用途说明：文件移动/改名后，同步更新文件索引中的路径与文件名。
            1. 过滤：原路径不在索引中的请求直接跳过（例如整理的是从未扫描入索引的文件），不视为异常；
            2. 校验：更新前确认新路径下确实存在文件，防止索引指向不存在的文件；
            3. 冲突：新路径已存在其他索引记录（唯一约束）时跳过，保留原有记录不做覆盖。
        入参说明：
            old_path (str): 文件移动/改名前的完整路径。
            new_path (str): 文件移动/改名后的完整路径。
        返回值说明：bool - 是否实际更新了索引记录；被过滤、校验失败或更新失败均返回 False。
        """
        try:
            if not old_path or not new_path or os.path.normcase(old_path) == os.path.normcase(new_path):
                return False

            # 1. 过滤：原路径不在索引中则跳过
            old_info: Optional[FileIndexDBModel] = DBOperations.get_file_by_path(old_path)
            if old_info is None:
                LogUtils.debug(t('repo_update_index_skip_not_indexed', old_path=old_path))
                return False

            # 2. 校验：更新前确认新路径下存在文件
            if not os.path.isfile(new_path):
                LogUtils.error(t('repo_update_index_target_missing', new_path=new_path))
                return False

            # 3. 更新索引路径与文件名
            updated: int = DBOperations.update_file_path(old_path, new_path)
            if updated <= 0:
                LogUtils.error(t('repo_update_index_conflict', old_path=old_path, new_path=new_path))
                return False

            LogUtils.info(t('repo_update_index_log', old_path=old_path, new_path=new_path))
            return True
        except Exception as e:
            LogUtils.error(t('repo_update_index_error', old_path=old_path, new_path=new_path, error=str(e)))
            return False

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

            LogUtils.info(t('repo_clear_log_full', user='', clear_history=clear_history))
            return True
        except Exception as e:
            LogUtils.error(t('repo_clear_error', error=str(e)))
            return False

    @staticmethod
    def clear_history_repository() -> bool:
        """
        用途说明：仅清空历史文件索引库 (history_file_index)
        返回值说明：bool: 是否成功
        """
        try:
            if DBOperations.clear_history_index():
                LogUtils.info(t('repo_clear_history_success'))
                return True
            return False
        except Exception as e:
            LogUtils.error(t('repo_clear_history_failed', error=str(e)))
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
