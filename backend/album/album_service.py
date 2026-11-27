import os
from typing import List, Optional

from backend.common.file_type_enum import FileType
from backend.common.filename_sort_utils import FilenameSortUtils
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.db.db_constants import DBConstants
from backend.file_repository.thumbnail.thumbnail_path_utils import ThumbnailPathUtils
from backend.model.album_item_result import AlbumItemResult
from backend.model.album_axis_item_result import AlbumAxisItemResult
from backend.model.album_axis_result import AlbumAxisResult
from backend.model.album_settings_result import AlbumSettingsResult
from backend.model.db.album_axis_item_db_model import AlbumAxisItemDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.cursor_pagination_result import CursorPaginationResult
from backend.model.thumbnail_usage_result import ThumbnailUsageResult
from backend.setting.setting_service import settingService


class AlbumService:
    """
    用途说明：相册模块业务服务类。
    职责：
        1. 查询图片/视频媒体列表（瀑布流分页 + 搜索）；
        2. 校验媒体文件并供下载/预览接口使用（缩略图生成统一由缩略图服务提供）；
        3. 读写相册设置（缩略图存储路径、全系统缩略图最大边长、新增文件自动生成缩略图与自动人脸识别开关）。
    """

    # 相册只展示图片与视频两类媒体
    MEDIA_TYPES: List[str] = [FileType.IMAGE.value, FileType.VIDEO.value]

    @staticmethod
    def get_album_list(limit: int, sort_by: str, order_asc: bool,
                       search_query: str, file_type: str = '', last_path: str = '',
                       anchor_path: str = '', before_path: str = '') -> CursorPaginationResult[AlbumItemResult]:
        """
        用途说明：按媒体路径游标查询相册媒体列表，并将数据库模型转换为 API 返回数据。
        入参说明：
            limit (int): 每批数量（限制在 1-500）。
            sort_by (str): 排序字段，可选 album_time、file_name、file_size。
            order_asc (bool): 是否升序。
            search_query (str): 文件名搜索关键词。
            file_type (str): 媒体类型筛选，空串为全部，可选 image（仅图片）/ video（仅视频）。
            last_path (str): 向下游标路径，空字符串表示首批数据。
            anchor_path (str): 定位锚点路径，从该媒体开始包含式取数。
            before_path (str): 向上锚点路径，取该媒体之前最近一批数据。
        返回值说明：CursorPaginationResult[AlbumItemResult] - 不包含页码的相册游标分页结果。
        """
        safe_limit: int = min(500, max(1, limit))
        # 按类型筛选：非法或空值回退为图片 + 视频全部类型
        target_types: List[str] = AlbumService.MEDIA_TYPES
        if file_type == FileType.IMAGE.value:
            target_types = [FileType.IMAGE.value]
        elif file_type == FileType.VIDEO.value:
            target_types = [FileType.VIDEO.value]

        raw_result: CursorPaginationResult[FileIndexDBModel] = DBOperations.search_album_file_list(
            safe_limit, sort_by, order_asc, search_query, target_types,
            last_path, anchor_path, before_path
        )

        items: List[AlbumItemResult] = []
        for item in raw_result.list:
            file_type: str = item.file_type or ""
            items.append(AlbumItemResult(
                file_path=item.file_path,
                file_name=item.file_name or os.path.basename(item.file_path),
                filename_initial=FilenameSortUtils.get_initial(item.file_name or item.file_path),
                file_type=file_type,
                file_size=item.file_size or 0,
                thumbnail_path=item.thumbnail_path or None,
                video_duration=item.video_duration if file_type == FileType.VIDEO.value else None,
                scan_time=item.scan_time,
                file_mtime=None if item.file_mtime == DBConstants.FileIndex.NO_INFO_VALUE else item.file_mtime,
                file_exif_time=(
                    None if item.file_exif_time == DBConstants.FileIndex.NO_INFO_VALUE else item.file_exif_time
                ),
                file_location=(
                    None if item.file_location == DBConstants.FileIndex.NO_INFO_VALUE else item.file_location
                ),
                media_width=item.media_width if item.media_width and item.media_width > 0 else None,
                media_height=item.media_height if item.media_height and item.media_height > 0 else None
            ))

        return CursorPaginationResult(
            total=raw_result.total,
            list=items,
            limit=raw_result.limit,
            sort_by=raw_result.sort_by,
            order=raw_result.order
        )

    @staticmethod
    def get_axis(level: str, sort_by: str, order_asc: bool,
                 search_query: str, file_type: str = '',
                 year: str = '', month: int = 0) -> AlbumAxisResult:
        """
        用途说明：获取相册年份、月份、日期或文件名首字母轴及每组首条媒体路径。
        入参说明：
            level (str): 轴层级，可选 year、month、day、initial。
            sort_by (str): 媒体排序字段，初始轴强制按文件名，时间轴强制按相册时间。
            order_asc (bool): 是否升序。
            search_query (str): 文件名搜索关键词。
            file_type (str): 媒体类型筛选，空串为全部。
            year (str): 月份轴或日期轴所属年份。
            month (int): 日期轴所属月份。
        返回值说明：AlbumAxisResult - 轴层级与有数据的分组项列表。
        """
        target_types: List[str] = AlbumService.MEDIA_TYPES
        if file_type == FileType.IMAGE.value:
            target_types = [FileType.IMAGE.value]
        elif file_type == FileType.VIDEO.value:
            target_types = [FileType.VIDEO.value]

        axis_sort_by: str = 'file_name' if level == 'initial' else DBConstants.FileIndex.ALBUM_TIME_FIELD
        axis_order_asc: bool = True if level == 'initial' else order_asc
        raw_items: List[AlbumAxisItemDBModel] = DBOperations.get_album_axis(
            level, axis_sort_by, axis_order_asc, search_query, target_types, year, month
        )
        items: List[AlbumAxisItemResult] = [
            AlbumAxisItemResult(key=item.key, first_path=item.first_path, count=item.count)
            for item in raw_items
        ]
        return AlbumAxisResult(level=level, items=items)

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
        用途说明：获取相册设置（缩略图存储路径、实际路径、全系统缩略图最大边长、新增文件自动生成缩略图与自动人脸识别开关）。
        入参说明：无
        返回值说明：AlbumSettingsResult - 相册设置数据。
        """
        thumbnail_size: int = settingService.get_album_thumbnail_size()
        auto_thumbnail_generation: bool = settingService.get_config().album.auto_thumbnail_generation
        if not isinstance(auto_thumbnail_generation, bool):
            auto_thumbnail_generation = False
        auto_face_recognition: bool = settingService.get_config().album.auto_face_recognition
        if not isinstance(auto_face_recognition, bool):
            auto_face_recognition = False
        return AlbumSettingsResult(
            thumbnail_dir=ThumbnailPathUtils.get_configured_dir(),
            thumbnail_dir_effective=ThumbnailPathUtils.get_thumbnail_dir(),
            thumbnail_size=thumbnail_size,
            auto_thumbnail_generation=auto_thumbnail_generation,
            auto_face_recognition=auto_face_recognition
        )

    @staticmethod
    def get_thumbnail_usage() -> ThumbnailUsageResult:
        """
        用途说明：统计当前配置的缩略图目录占用大小，仅遍历文件元数据，不读取文件内容。
        入参说明：无
        返回值说明：ThumbnailUsageResult - 缩略图目录中普通文件的总字节数；目录不存在时返回 0。
        """
        result: ThumbnailUsageResult = ThumbnailUsageResult()
        thumbnail_dir: str = ThumbnailPathUtils.get_thumbnail_dir()
        if not os.path.isdir(thumbnail_dir):
            return result

        pending_dirs: List[str] = [thumbnail_dir]
        while pending_dirs:
            current_dir: str = pending_dirs.pop()
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                pending_dirs.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                result.size_bytes += entry.stat().st_size
                        except OSError as e:
                            LogUtils.error(t('album_thumbnail_usage_error', error=str(e)))
            except OSError as e:
                LogUtils.error(t('album_thumbnail_usage_error', error=str(e)))

        return result

    @staticmethod
    def update_settings(thumbnail_dir: str, operator_name: str,
                        thumbnail_size: Optional[int] = None,
                        auto_thumbnail_generation: Optional[bool] = None,
                        auto_face_recognition: Optional[bool] = None) -> Optional[AlbumSettingsResult]:
        """
        用途说明：更新缩略图存储路径、全系统缩略图最大边长、新增文件自动生成缩略图与自动人脸识别开关，并确保目录可用。
        入参说明：
            thumbnail_dir (str): 用户输入的路径（相对 data 目录或绝对路径），空值使用默认 thumb。
            operator_name (str): 操作人用户名，用于日志。
            thumbnail_size (Optional[int]): 全系统缩略图最大边长（像素），None 表示不修改；仅接受正整数。
            auto_thumbnail_generation (Optional[bool]): 新增文件自动生成缩略图开关，None 表示不修改；仅接受布尔值。
            auto_face_recognition (Optional[bool]): 自动识别新增图片开关，None 表示不修改；仅接受布尔值。
        返回值说明：Optional[AlbumSettingsResult] - 更新后的设置，失败返回 None。
        """
        if thumbnail_size is not None and (
                isinstance(thumbnail_size, bool) or not isinstance(thumbnail_size, int) or thumbnail_size <= 0):
            LogUtils.error(t('album_thumbnail_size_invalid', value=thumbnail_size))
            return None
        if auto_thumbnail_generation is not None and not isinstance(auto_thumbnail_generation, bool):
            LogUtils.error(t('album_auto_thumbnail_generation_invalid', value=auto_thumbnail_generation))
            return None
        if auto_face_recognition is not None and not isinstance(auto_face_recognition, bool):
            LogUtils.error(t('album_auto_face_recognition_invalid', value=auto_face_recognition))
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

        # 通过统一设置服务持久化存储路径、全系统缩略图尺寸与自动生成开关
        album_settings: dict = {"thumbnail_dir": raw_value}
        if thumbnail_size is not None:
            album_settings["thumbnail_size"] = thumbnail_size
        if auto_thumbnail_generation is not None:
            album_settings["auto_thumbnail_generation"] = auto_thumbnail_generation
        if auto_face_recognition is not None:
            album_settings["auto_face_recognition"] = auto_face_recognition
        updated: bool = settingService.update_settings(
            {"album": album_settings}, operator_name
        )
        if not updated:
            LogUtils.error(t('album_settings_update_failed_log', user=operator_name))
            return None

        LogUtils.info(t('album_settings_updated_log', user=operator_name, path=candidate_dir))
        return AlbumService.get_settings()