import os
import re
import struct
from datetime import datetime
from typing import Optional

from backend.common.file_type_enum import FileType
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils


class MediaTimeService:
    """
    用途：媒体拍摄时间读取服务。
        图片读取 EXIF 拍摄时间（DateTimeOriginal/DateTimeDigitized/DateTime）；
        视频读取 MP4/MOV 盒子中的创建时间（mvhd creation_time）。
        读取失败统一返回 None，由调用方回退到文件修改时间。
    """

    # EXIF 标签：拍摄时间、数字化时间、文件修改时间（按优先级排列）
    IMAGE_EXIF_TAGS: tuple = (36867, 36868, 306)
    # EXIF 子 IFD 标签（DateTimeOriginal 等通常位于该子目录中）
    EXIF_SUB_IFD_TAG: int = 0x8769
    # 视频中可能携带创建时间的容器后缀
    VIDEO_BOX_SUFFIXES: tuple = ('.mp4', '.mov', '.m4v', '.3gp', '.qt')
    # 1904-01-01 到 1970-01-01 的秒数差（QuickTime/MP4 纪元）
    MP4_EPOCH_OFFSET: int = 2082844800
    # 顶层盒子与子盒子的最大扫描数量，避免异常文件导致长时间循环
    MAX_BOX_COUNT: int = 512
    # EXIF 时间格式，如 2024:05:01 12:30:00
    EXIF_TIME_PATTERN: re.Pattern = re.compile(r'^(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})')

    @classmethod
    def get_exif_time(cls, file_path: str, file_type: str) -> Optional[str]:
        """
        用途说明：按文件类型读取拍摄时间；图片读 EXIF，视频读容器创建时间。
        入参说明：
            file_path (str): 文件完整路径。
            file_type (str): 文件类型（FileType.IMAGE.value / FileType.VIDEO.value）。
        返回值说明：Optional[str] - 格式为 'YYYY-MM-DD HH:MM:SS' 的本地时间；读取失败返回 None。
        """
        try:
            if not file_path or not os.path.isfile(file_path):
                return None
            if file_type == FileType.IMAGE.value:
                return cls._read_image_exif_time(file_path)
            if file_type == FileType.VIDEO.value:
                return cls._read_video_creation_time(file_path)
            return None
        except Exception as e:
            LogUtils.error(t('media_time_read_failed', path=file_path, error=str(e)))
            return None

    @classmethod
    def _read_image_exif_time(cls, file_path: str) -> Optional[str]:
        """
        用途说明：使用 Pillow 读取图片 EXIF 中的拍摄时间，优先拍摄时间，其次数字化时间与文件时间。
        入参说明：file_path (str) - 图片完整路径。
        返回值说明：Optional[str] - 解析成功返回标准化时间字符串，否则返回 None。
        """
        from PIL import Image

        with Image.open(file_path) as image:
            exif = image.getexif()
            if not exif:
                return None
            # DateTimeOriginal 等标签通常位于 Exif 子 IFD 中，先读子 IFD 再读主 IFD
            containers: list = []
            try:
                sub_ifd = exif.get_ifd(cls.EXIF_SUB_IFD_TAG)
                if sub_ifd:
                    containers.append(sub_ifd)
            except Exception:
                pass
            containers.append(exif)
            for container in containers:
                for tag in cls.IMAGE_EXIF_TAGS:
                    raw_value = container.get(tag)
                    normalized: Optional[str] = cls._normalize_raw_time(raw_value)
                    if normalized:
                        return normalized
        return None

    @classmethod
    def _normalize_raw_time(cls, raw_value) -> Optional[str]:
        """
        用途说明：把 EXIF 时间原始值（可能为字符串或字节）标准化为 'YYYY-MM-DD HH:MM:SS'。
        入参说明：raw_value - EXIF 时间原始值。
        返回值说明：Optional[str] - 合法时间返回标准字符串，否则返回 None。
        """
        if not raw_value:
            return None
        if isinstance(raw_value, bytes):
            raw_text: str = raw_value.decode('ascii', errors='ignore')
        else:
            raw_text = str(raw_value)
        match = cls.EXIF_TIME_PATTERN.match(raw_text.strip())
        if not match:
            return None
        year, month, day, hour, minute, second = (int(item) for item in match.groups())
        try:
            time_value: datetime = datetime(year, month, day, hour, minute, second)
        except ValueError:
            return None
        return time_value.strftime('%Y-%m-%d %H:%M:%S')

    @classmethod
    def _read_video_creation_time(cls, file_path: str) -> Optional[str]:
        """
        用途说明：解析 MP4/MOV 容器，从 moov -> mvhd 盒子读取创建时间（秒，自 1904-01-01 纪元）。
        入参说明：file_path (str) - 视频完整路径。
        返回值说明：Optional[str] - 解析成功返回本地时间字符串，否则返回 None。
        """
        suffix: str = os.path.splitext(file_path)[1].lower()
        if suffix not in cls.VIDEO_BOX_SUFFIXES:
            return None

        file_size: int = os.path.getsize(file_path)
        with open(file_path, 'rb') as file_handle:
            offset: int = 0
            box_count: int = 0
            while offset + 8 <= file_size and box_count < cls.MAX_BOX_COUNT:
                box_info = cls._read_box_header(file_handle, offset, file_size)
                if box_info is None:
                    break
                box_type, box_size, header_size = box_info
                if box_type == b'moov':
                    creation_seconds: Optional[int] = cls._find_mvhd_creation(
                        file_handle, offset + header_size, offset + box_size
                    )
                    if creation_seconds:
                        return cls._mp4_seconds_to_local_time(creation_seconds)
                    return None
                offset += box_size
                box_count += 1
        return None

    @classmethod
    def _read_box_header(cls, file_handle, offset: int, file_size: int) -> Optional[tuple]:
        """
        用途说明：读取指定偏移处的盒子头（类型、总大小、头部大小）。
        入参说明：
            file_handle - 已打开的文件对象。
            offset (int) - 盒子起始偏移。
            file_size (int) - 文件总大小（用于处理 size=0 的盒子）。
        返回值说明：Optional[tuple] - (类型, 总大小, 头部大小)；非法盒子返回 None。
        """
        file_handle.seek(offset)
        header: bytes = file_handle.read(8)
        if len(header) < 8:
            return None
        box_size: int = struct.unpack('>I', header[:4])[0]
        box_type: bytes = header[4:8]
        header_size: int = 8
        if box_size == 1:
            large_size: bytes = file_handle.read(8)
            if len(large_size) < 8:
                return None
            box_size = struct.unpack('>Q', large_size)[0]
            header_size = 16
        elif box_size == 0:
            box_size = file_size - offset
        if box_size < header_size or offset + box_size > file_size:
            return None
        return box_type, box_size, header_size

    @classmethod
    def _find_mvhd_creation(cls, file_handle, start: int, end: int) -> Optional[int]:
        """
        用途说明：在 moov 盒子范围内查找 mvhd 盒子并读取其创建时间。
        入参说明：
            file_handle - 已打开的文件对象。
            start (int) - 子盒子扫描起始偏移。
            end (int) - 子盒子扫描结束偏移。
        返回值说明：Optional[int] - 创建时间秒数（1904 纪元）；未找到返回 None。
        """
        offset: int = start
        box_count: int = 0
        while offset + 8 <= end and box_count < cls.MAX_BOX_COUNT:
            box_info = cls._read_box_header(file_handle, offset, end)
            if box_info is None:
                break
            box_type, box_size, header_size = box_info
            if box_type == b'mvhd':
                file_handle.seek(offset + header_size)
                payload: bytes = file_handle.read(min(box_size - header_size, 32))
                if len(payload) < 8:
                    return None
                version: int = payload[0]
                if version == 1 and len(payload) >= 12:
                    return struct.unpack('>Q', payload[4:12])[0]
                return struct.unpack('>I', payload[4:8])[0]
            offset += box_size
            box_count += 1
        return None

    @classmethod
    def _mp4_seconds_to_local_time(cls, creation_seconds: int) -> Optional[str]:
        """
        用途说明：将 MP4 创建时间（1904 纪元秒）转换为本地时间字符串，并做合理年份校验。
        入参说明：creation_seconds (int) - 1904 纪元秒数。
        返回值说明：Optional[str] - 合法时间返回 'YYYY-MM-DD HH:MM:SS'，异常值返回 None。
        """
        epoch_seconds: int = creation_seconds - cls.MP4_EPOCH_OFFSET
        if epoch_seconds <= 0:
            return None
        try:
            time_value: datetime = datetime.fromtimestamp(epoch_seconds)
        except (OverflowError, OSError, ValueError):
            return None
        if time_value.year < 1980 or time_value.year > 2100:
            return None
        return time_value.strftime('%Y-%m-%d %H:%M:%S')