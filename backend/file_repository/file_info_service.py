import os
from datetime import datetime
from typing import Tuple, Optional

import cv2

from backend.common.file_type_enum import FileType
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_constants import DBConstants
from backend.file_repository.media_location_service import MediaLocationService
from backend.file_repository.media_time_service import MediaTimeService
from backend.model.db.file_index_db_model import FileIndexDBModel


class FileInfoService:
    """
    用途：文件信息组装服务，负责从物理文件提取并构建文件索引模型（FileIndexDBModel）。
    属于文件仓库领域逻辑，与通用工具解耦。
    """

    @staticmethod
    def get_video_params(file_path: str) -> Tuple[Optional[float], Optional[str], int, int]:
        """
        用途说明：使用 OpenCV 获取视频的时长、编码格式与显示分辨率。
        入参说明：file_path (str): 视频文件路径。
        返回值说明：Tuple[Optional[float], Optional[str], int, int] - (视频时长秒, 编码格式, 显示宽度, 显示高度)；
            获取失败的时长或编码为 None，无法获取的分辨率记为 0。
        """
        duration: Optional[float] = None
        codec: Optional[str] = None
        media_width: int = 0
        media_height: int = 0
        cap: Optional[cv2.VideoCapture] = None
        try:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                fps: float = cap.get(cv2.CAP_PROP_FPS)
                frame_count: float = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if fps > 0 and frame_count > 0:
                    # 使用向下取整 (int)，与大多数系统文件管理器的显示习惯保持一致
                    duration = float(int(frame_count / fps))

                media_width = FileInfoService._normalize_dimension(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                media_height = FileInfoService._normalize_dimension(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                fourcc: int = int(cap.get(cv2.CAP_PROP_FOURCC))
                if fourcc != 0:
                    # 将整数转换为 4 字符编码字符串
                    codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).strip()
        except Exception as e:
            LogUtils.error(t('utils_extract_video_params_failed', path=file_path, error=str(e)))
        finally:
            if cap:
                cap.release()
        return duration, codec, media_width, media_height

    @staticmethod
    def get_image_dimensions(file_path: str) -> Tuple[int, int]:
        """
        用途说明：使用 Pillow 读取图片显示分辨率，并按 EXIF 方向交换横竖宽高。
        入参说明：file_path (str): 图片文件路径。
        返回值说明：Tuple[int, int] - (显示宽度, 显示高度)；读取失败时两项均为 0。
        """
        from PIL import Image

        try:
            with Image.open(file_path) as image:
                media_width: int = int(image.size[0])
                media_height: int = int(image.size[1])
                try:
                    orientation: int = int(image.getexif().get(274, 1))
                except (TypeError, ValueError, OverflowError):
                    orientation = 1
                if orientation in (5, 6, 7, 8):
                    media_width, media_height = media_height, media_width
            if media_width > 0 and media_height > 0:
                return media_width, media_height
        except Exception as e:
            LogUtils.error(t('utils_get_file_info_failed', path=file_path, error=str(e)))
        return 0, 0

    @staticmethod
    def _normalize_dimension(value: Optional[float]) -> int:
        """
        用途说明：把媒体宽高转换为正整数，无法获取或非法值统一记为 0，避免补全任务反复读取。
        入参说明：value (Optional[float]) - 图片或视频读取到的宽高原始值。
        返回值说明：int - 大于 0 的整数宽高；无效值返回 0。
        """
        try:
            dimension: int = int(value or 0)
        except (TypeError, ValueError, OverflowError):
            return 0
        return dimension if dimension > 0 else 0

    @staticmethod
    def _normalize_metadata_value(value: Optional[str]) -> str:
        """
        用途说明：把空媒体信息转换为统一的“无信息”标记，防止补全任务反复读取同一文件。
        入参说明：value (Optional[str]) - 文件修改时间、拍摄时间或拍摄地点。
        返回值说明：str - 有信息时返回原值，否则返回 DBConstants.FileIndex.NO_INFO_VALUE。
        """
        return value if value else DBConstants.FileIndex.NO_INFO_VALUE

    @staticmethod
    def get_album_metadata(file_path: str) -> Optional[FileIndexDBModel]:
        """
        用途说明：仅为手动补全任务读取媒体修改时间、拍摄时间、拍摄地点和分辨率，不计算 MD5 或生成缩略图。
        入参说明：file_path (str) - 当前索引中缺失媒体信息的图片或视频完整路径。
        返回值说明：Optional[FileIndexDBModel] - 包含媒体信息及分辨率的索引模型；文件不存在或非媒体时返回 None。
        """
        try:
            if not os.path.isfile(file_path):
                return None
            if Utils.is_video_file(file_path):
                file_type: str = FileType.VIDEO.value
            elif Utils.is_image_file(file_path):
                file_type = FileType.IMAGE.value
            else:
                return None

            file_mtime: Optional[str] = None
            try:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
            except OSError as stat_error:
                LogUtils.error(t('utils_get_file_info_failed', path=file_path, error=str(stat_error)))
                return None

            exif_time: Optional[str] = MediaTimeService.get_exif_time(file_path, file_type)
            file_location: Optional[str] = MediaLocationService.get_location(file_path, file_type)
            media_width: int = 0
            media_height: int = 0
            if file_type == FileType.VIDEO.value:
                _, _, media_width, media_height = FileInfoService.get_video_params(file_path)
            else:
                media_width, media_height = FileInfoService.get_image_dimensions(file_path)
            return FileIndexDBModel(
                file_path=file_path,
                file_type=file_type,
                file_mtime=FileInfoService._normalize_metadata_value(file_mtime),
                file_exif_time=FileInfoService._normalize_metadata_value(exif_time),
                file_location=FileInfoService._normalize_metadata_value(file_location),
                media_width=media_width,
                media_height=media_height
            )
        except Exception as e:
            LogUtils.error(t('utils_get_file_info_failed', path=file_path, error=str(e)))
            return None

    @staticmethod
    def get_file_info(file_path: str) -> Optional[FileIndexDBModel]:
        """
        用途说明：获取文件信息并组装成 FileIndexDBModel。包含 MD5、文件类型、视频时长与编码、媒体分辨率等。
        入参说明：file_path (str): 文件完整路径。
        返回值说明：Optional[FileIndexDBModel]: 组装好的数据库模型，失败返回 None。
        """
        try:
            if not os.path.exists(file_path):
                return None

            # 1. 计算 MD5 和基础信息
            _, f_md5 = Utils.calculate_fast_md5(file_path)
            if not f_md5:
                return None
            
            f_size: int = os.path.getsize(file_path)
            f_name: str = os.path.basename(file_path)
            # 文件最后修改时间：相册时间轴按此时间分组，取不到时留空由相册按扫描时间兜底
            f_mtime: Optional[str] = None
            try:
                f_mtime = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
            except OSError as stat_error:
                LogUtils.error(t('utils_get_file_info_failed', path=file_path, error=str(stat_error)))
            
            # 2. 识别文件类型及提取扩展属性
            file_type: str = FileType.OTHER.value
            video_duration: Optional[float] = None
            video_codec: Optional[str] = None
            media_width: int = 0
            media_height: int = 0
            
            if Utils.is_video_file(file_path):
                file_type = FileType.VIDEO.value
                video_duration, video_codec, media_width, media_height = FileInfoService.get_video_params(file_path)
            elif Utils.is_image_file(file_path):
                file_type = FileType.IMAGE.value
                media_width, media_height = FileInfoService.get_image_dimensions(file_path)

            # 2.1 读取 EXIF/拍摄时间：相册优先使用该时间，缺失时回退文件修改时间
            exif_time: Optional[str] = None
            # 2.2 读取拍摄地点：图片读 EXIF GPS，视频读容器 ISO 6709 元数据
            file_location: Optional[str] = None
            if file_type in (FileType.IMAGE.value, FileType.VIDEO.value):
                exif_time = MediaTimeService.get_exif_time(file_path, file_type)
                file_location = MediaLocationService.get_location(file_path, file_type)

            # 3. 复用同 MD5 文件已生成的缩略图（缩略图按内容 MD5 命名，同内容文件共享，避免副本无法预览）
            thumbnail_path: Optional[str] = None
            if file_type in (FileType.IMAGE.value, FileType.VIDEO.value):
                from backend.file_repository.thumbnail.thumbnail_generator import ThumbnailGenerator
                thumbnail_path = ThumbnailGenerator.get_existing_thumbnail_path(f_md5)

            return FileIndexDBModel(
                file_path=file_path,
                file_name=f_name,
                file_md5=f_md5,
                file_size=f_size,
                file_type=file_type,
                video_duration=video_duration,
                video_codec=video_codec,
                thumbnail_path=thumbnail_path,
                file_mtime=FileInfoService._normalize_metadata_value(f_mtime),
                file_exif_time=FileInfoService._normalize_metadata_value(exif_time),
                file_location=FileInfoService._normalize_metadata_value(file_location),
                media_width=media_width,
                media_height=media_height
            )
        except Exception as e:
            LogUtils.error(t('utils_get_file_info_failed', path=file_path, error=str(e)))
            return None