import os
from typing import Tuple, Optional

import cv2

from backend.common.file_type_enum import FileType
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.model.db.file_index_db_model import FileIndexDBModel


class FileInfoService:
    """
    用途：文件信息组装服务，负责从物理文件提取并构建文件索引模型（FileIndexDBModel）。
    属于文件仓库领域逻辑，与通用工具解耦。
    """

    @staticmethod
    def get_video_params(file_path: str) -> Tuple[Optional[float], Optional[str]]:
        """
        用途说明：使用 OpenCV 获取视频的时长与编码格式。
        入参说明：file_path (str): 视频文件路径。
        返回值说明：Tuple[Optional[float], Optional[str]]: (视频时长秒, 编码格式)；获取失败对应项为 None。
        """
        duration: Optional[float] = None
        codec: Optional[str] = None
        cap: Optional[cv2.VideoCapture] = None
        try:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                fps: float = cap.get(cv2.CAP_PROP_FPS)
                frame_count: float = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if fps > 0 and frame_count > 0:
                    # 使用向下取整 (int)，与大多数系统文件管理器的显示习惯保持一致
                    duration = float(int(frame_count / fps))
                
                fourcc: int = int(cap.get(cv2.CAP_PROP_FOURCC))
                if fourcc != 0:
                    # 将整数转换为 4 字符编码字符串
                    codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).strip()
        except Exception as e:
            LogUtils.error(t('utils_extract_video_params_failed', path=file_path, error=str(e)))
        finally:
            if cap:
                cap.release()
        return duration, codec

    @staticmethod
    def get_file_info(file_path: str) -> Optional[FileIndexDBModel]:
        """
        用途说明：获取文件信息并组装成 FileIndexDBModel。包含 MD5、文件类型、视频时长与编码等。
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
            
            # 2. 识别文件类型及提取扩展属性
            file_type: str = FileType.OTHER.value
            video_duration: Optional[float] = None
            video_codec: Optional[str] = None
            
            if Utils.is_video_file(file_path):
                file_type = FileType.VIDEO.value
                video_duration, video_codec = FileInfoService.get_video_params(file_path)
            elif Utils.is_image_file(file_path):
                file_type = FileType.IMAGE.value

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
                thumbnail_path=thumbnail_path
            )
        except Exception as e:
            LogUtils.error(t('utils_get_file_info_failed', path=file_path, error=str(e)))
            return None