import os
from typing import List, Optional

from backend.common.file_type_enum import FileType
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import get_current_repo_id
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.thumbnail.thumbnail_path_utils import ThumbnailPathUtils
from backend.model.album_item_result import AlbumItemResult
from backend.model.album_settings_result import AlbumSettingsResult
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.pagination_result import PaginationResult
from backend.repository.repository_service import repositoryService
from backend.setting.setting_service import settingService


class AlbumService:
    """
    用途说明：相册模块业务服务类。
    职责：
        1. 查询图片/视频媒体列表（瀑布流分页 + 搜索）；
        2. 校验媒体文件并供下载/预览接口使用（缩略图生成统一由缩略图服务提供）；
        3. 读写相册设置（缩略图存储路径与当前仓库缩略图最大边长）。
    """

    # 相册只展示图片与视频两类媒体
    MEDIA_TYPES: List[str] = [FileType.IMAGE.value, FileType.VIDEO.value]

    @staticmethod
    def get_album_list(page: int, limit: int, sort_by: str, order_asc: bool,
                       search_query: str, file_type: str = '') -> PaginationResult[AlbumItemResult]:
        """
        用途说明：分页查询相册媒体列表，并将数据库模型转换为 API 返回数据。
        入参说明：
            page (int): 当前页码（最小 1）。
            limit (int): 每页数量（限制在 1-200）。
            sort_by (str): 排序字段。
            order_asc (bool): 是否升序。
            search_query (str): 文件名搜索关键词。
            file_type (str): 媒体类型筛选，空串为全部，可选 image（仅图片）/ video（仅视频）。
        返回值说明：PaginationResult[AlbumItemResult] - 相册媒体分页结果。
        """
        safe_page: int = max(1, page)
        safe_limit: int = min(200, max(1, limit))
        # 按类型筛选：非法或空值回退为图片 + 视频全部类型
        target_types: List[str] = AlbumService.MEDIA_TYPES
        if file_type == FileType.IMAGE.value:
            target_types = [FileType.IMAGE.value]
        elif file_type == FileType.VIDEO.value:
            target_types = [FileType.VIDEO.value]

        raw_result: PaginationResult[FileIndexDBModel] = DBOperations.search_album_file_list(
            safe_page, safe_limit, sort_by, order_asc, search_query, target_types
        )

        items: List[AlbumItemResult] = []
        for item in raw_result.list:
            file_type: str = item.file_type or ""
            items.append(AlbumItemResult(
                file_path=item.file_path,
                file_name=item.file_name or os.path.basename(item.file_path),
                file_type=file_type,
                file_size=item.file_size or 0,
                thumbnail_path=item.thumbnail_path or None,
                video_duration=item.video_duration if file_type == FileType.VIDEO.value else None,
                scan_time=item.scan_time,
                file_mtime=item.file_mtime,
                file_exif_time=item.file_exif_time,
                file_location=item.file_location
            ))

        return PaginationResult(
            total=raw_result.total,
            list=items,
            page=raw_result.page,
            limit=raw_result.limit,
            sort_by=raw_result.sort_by,
            order=raw_result.order
        )

    @staticmethod
    def get_media_file(file_path: str) -> Optional[FileIndexDBModel]:
        """
        用途说明：校验并获取可访问的媒体文件记录（仅限图片/视频、非回收站、文件真实存在）。
        入参说明：file_path (str): 媒体文件完整路径。
        返回值说明：Optional[FileIndexDBModel] - 校验通过的索引记录，失败返回 None。
        """
        if not file_path:
            return None
        file_info: Optional[FileIndexDBModel] = DBOperations.get_file_by_path(file_path)
        if file_info is None:
            return None
        if file_info.recycle_bin_time:
            return None
        if file_info.file_type not in AlbumService.MEDIA_TYPES:
            return None
        if not os.path.isfile(file_info.file_path):
            return None
        return file_info

    @staticmethod
    def get_settings() -> AlbumSettingsResult:
        """
        用途说明：获取相册设置（缩略图存储路径、实际路径与当前仓库缩略图最大边长）。
        入参说明：无
        返回值说明：AlbumSettingsResult - 相册设置数据。
        """
        thumbnail_size: int = repositoryService.get_current_config().thumbnail_size
        if isinstance(thumbnail_size, bool) or not isinstance(thumbnail_size, int) or thumbnail_size <= 0:
            thumbnail_size = 256
        return AlbumSettingsResult(
            thumbnail_dir=ThumbnailPathUtils.get_configured_dir(),
            thumbnail_dir_effective=ThumbnailPathUtils.get_thumbnail_dir(),
            thumbnail_size=thumbnail_size
        )

    @staticmethod
    def update_settings(thumbnail_dir: str, operator_name: str,
                        thumbnail_size: Optional[int] = None) -> Optional[AlbumSettingsResult]:
        """
        用途说明：更新缩略图存储路径与当前仓库缩略图最大边长，并确保目录可用。
        入参说明：
            thumbnail_dir (str): 用户输入的路径（相对 data 目录或绝对路径），空值使用默认 thumb。
            operator_name (str): 操作人用户名，用于日志。
            thumbnail_size (Optional[int]): 缩略图最大边长（像素），None 表示不修改；仅接受正整数。
        返回值说明：Optional[AlbumSettingsResult] - 更新后的设置，失败返回 None。
        """
        if thumbnail_size is not None and (
                isinstance(thumbnail_size, bool) or not isinstance(thumbnail_size, int) or thumbnail_size <= 0):
            LogUtils.error(t('album_thumbnail_size_invalid', value=thumbnail_size))
            return None

        raw_value: str = (thumbnail_dir or "").strip() or ThumbnailPathUtils.DEFAULT_DIR_NAME
        candidate_dir: str = (
            os.path.abspath(raw_value)
            if os.path.isabs(raw_value)
            else os.path.abspath(os.path.join(Utils.get_runtime_path(), raw_value))
        )

        try:
            os.makedirs(candidate_dir, exist_ok=True)
            if not os.path.isdir(candidate_dir):
                LogUtils.error(t('album_thumbnail_dir_invalid', path=raw_value))
                return None
        except Exception as e:
            LogUtils.error(t('album_thumbnail_dir_create_failed', path=raw_value, error=str(e)))
            return None

        # 通过统一设置服务持久化存储路径，保证 setting.json 结构与其他配置一致
        updated: bool = settingService.update_settings(
            {"album": {"thumbnail_dir": raw_value}}, operator_name
        )
        if not updated:
            LogUtils.error(t('album_settings_update_failed_log', user=operator_name))
            return None

        # 分辨率属于当前仓库配置，与缩略图生成器读取的 thumbnail_size 保持同一字段
        if thumbnail_size is not None:
            repo_updated: bool = repositoryService.update_config(
                get_current_repo_id(), {"thumbnail_size": thumbnail_size}
            )
            if not repo_updated:
                LogUtils.error(t('album_settings_update_failed_log', user=operator_name))
                return None

        LogUtils.info(t('album_settings_updated_log', user=operator_name, path=candidate_dir))
        return AlbumService.get_settings()