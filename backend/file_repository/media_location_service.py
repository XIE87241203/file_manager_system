import os
import re
from typing import List, Optional, Tuple

from backend.common.file_type_enum import FileType
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils


class MediaLocationService:
    """
    用途：媒体拍摄地点读取服务。
        图片读取 EXIF GPS 信息；
        视频读取 MP4/MOV 元数据中的 ISO 6709 位置字符串（©xyz / Apple location 键）。
        读取失败统一返回 None，不阻塞文件索引。
    """

    # EXIF GPS 子 IFD 标签
    GPS_IFD_TAG: int = 0x8825
    # GPS 子 IFD 中的标签：纬度参考、纬度、经度参考、经度
    TAG_GPS_LAT_REF: int = 1
    TAG_GPS_LAT: int = 2
    TAG_GPS_LON_REF: int = 3
    TAG_GPS_LON: int = 4
    # 视频中可能携带拍摄地点的容器后缀
    VIDEO_SUFFIXES: tuple = ('.mp4', '.mov', '.m4v', '.3gp', '.qt')
    # 视频元数据中位置字符串的键名（©xyz 的原始字节形式与 Apple 扩展键）
    VIDEO_LOCATION_TOKENS: tuple = (b'\xa9xyz', b'com.apple.quicktime.location.ISO6709')
    # ISO 6709 位置串，如 +31.230416+121.473701/
    ISO6709_PATTERN: re.Pattern = re.compile(rb'([+-]\d{2,3}(?:\.\d+)?)([+-]\d{2,3}(?:\.\d+)?)')
    # 单次扫描的数据量：文件头 4MB、文件尾 2MB，兼顾速度与元数据命中率
    HEAD_SCAN_BYTES: int = 4 * 1024 * 1024
    TAIL_SCAN_BYTES: int = 2 * 1024 * 1024

    @classmethod
    def get_location(cls, file_path: str, file_type: str) -> Optional[str]:
        """
        用途说明：按文件类型读取拍摄地点；图片读 EXIF GPS，视频读容器 ISO 6709 元数据。
        入参说明：
            file_path (str): 文件完整路径。
            file_type (str): 文件类型（FileType.IMAGE.value / FileType.VIDEO.value）。
        返回值说明：Optional[str] - 格式为 '纬度, 经度'（南纬/西经为负）；读取失败返回 None。
        """
        try:
            if not file_path or not os.path.isfile(file_path):
                return None
            if file_type == FileType.IMAGE.value:
                return cls._read_image_gps(file_path)
            if file_type == FileType.VIDEO.value:
                return cls._read_video_location(file_path)
            return None
        except Exception as e:
            LogUtils.error(t('media_location_read_failed', path=file_path, error=str(e)))
            return None

    @classmethod
    def _read_image_gps(cls, file_path: str) -> Optional[str]:
        """
        用途说明：使用 Pillow 读取图片 EXIF 中的 GPS 子 IFD，并转换为十进制度坐标。
        入参说明：file_path (str) - 图片完整路径。
        返回值说明：Optional[str] - 成功返回 '纬度, 经度'，否则返回 None。
        """
        from PIL import Image

        with Image.open(file_path) as image:
            exif = image.getexif()
            if not exif:
                return None
            try:
                gps_info = exif.get_ifd(cls.GPS_IFD_TAG)
            except Exception:
                return None
            if not gps_info:
                return None

            lat_value = cls._dms_to_degrees(gps_info.get(cls.TAG_GPS_LAT))
            lon_value = cls._dms_to_degrees(gps_info.get(cls.TAG_GPS_LON))
            if lat_value is None or lon_value is None:
                return None

            # 南纬、西经取负值，统一为有符号十进制度
            lat_ref = cls._ref_to_text(gps_info.get(cls.TAG_GPS_LAT_REF))
            lon_ref = cls._ref_to_text(gps_info.get(cls.TAG_GPS_LON_REF))
            if lat_ref == 'S':
                lat_value = -lat_value
            if lon_ref == 'W':
                lon_value = -lon_value

            if abs(lat_value) > 90 or abs(lon_value) > 180:
                return None
            return cls._format_location(lat_value, lon_value)

    @classmethod
    def _dms_to_degrees(cls, dms_value) -> Optional[float]:
        """
        用途说明：将 EXIF GPS 的 (度, 分, 秒) 有理数序列转换为十进制度。
        入参说明：dms_value - EXIF GPS 标签值，通常为 3 个有理数组成的序列。
        返回值说明：Optional[float] - 转换成功返回十进制度，否则返回 None。
        """
        if not dms_value:
            return None
        try:
            parts = list(dms_value)
            if len(parts) < 3:
                return None
            degrees: float = cls._to_float(parts[0])
            minutes: float = cls._to_float(parts[1])
            seconds: float = cls._to_float(parts[2])
            return degrees + minutes / 60.0 + seconds / 3600.0
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    @classmethod
    def _to_float(cls, value) -> float:
        """
        用途说明：把 EXIF 有理数（IFDRational / 元组 / 数值）统一转换为浮点数。
        入参说明：value - 待转换值。
        返回值说明：float - 转换结果。
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            # 兼容 (分子, 分母) 形式的原始有理数
            numerator, denominator = value
            if not denominator:
                raise ValueError('zero denominator')
            return float(numerator) / float(denominator)

    @classmethod
    def _ref_to_text(cls, ref_value) -> str:
        """
        用途说明：将 EXIF GPS 方位参考值（N/S/E/W）统一为单个大写字符。
        入参说明：ref_value - EXIF 参考值（可能为字符串或字节）。
        返回值说明：str - 单字符方位；无法识别时返回空串。
        """
        if not ref_value:
            return ''
        if isinstance(ref_value, bytes):
            ref_text: str = ref_value.decode('ascii', errors='ignore')
        else:
            ref_text = str(ref_value)
        return ref_text.strip().upper()[:1]

    @classmethod
    def _read_video_location(cls, file_path: str) -> Optional[str]:
        """
        用途说明：在视频文件头部与尾部有限范围内查找 ISO 6709 位置元数据。
        入参说明：file_path (str) - 视频完整路径。
        返回值说明：Optional[str] - 成功返回 '纬度, 经度'，否则返回 None。
        """
        suffix: str = os.path.splitext(file_path)[1].lower()
        if suffix not in cls.VIDEO_SUFFIXES:
            return None

        file_size: int = os.path.getsize(file_path)
        if file_size <= 0:
            return None

        ranges: List[Tuple[int, int]] = [(0, min(file_size, cls.HEAD_SCAN_BYTES))]
        if file_size > cls.HEAD_SCAN_BYTES:
            tail_start: int = max(0, file_size - cls.TAIL_SCAN_BYTES)
            ranges.append((tail_start, file_size))

        with open(file_path, 'rb') as file_handle:
            for start, end in ranges:
                file_handle.seek(start)
                data: bytes = file_handle.read(end - start)
                location: Optional[str] = cls._extract_iso6709(data)
                if location:
                    return location
        return None

    @classmethod
    def _extract_iso6709(cls, data: bytes) -> Optional[str]:
        """
        用途说明：在给定字节块中定位位置元数据键，并解析相邻的 ISO 6709 坐标串。
        入参说明：data (bytes) - 视频片段数据。
        返回值说明：Optional[str] - 成功返回 '纬度, 经度'，否则返回 None。
        """
        for token in cls.VIDEO_LOCATION_TOKENS:
            search_start: int = 0
            while True:
                index: int = data.find(token, search_start)
                if index < 0:
                    break
                window: bytes = data[index:index + 256]
                match = cls.ISO6709_PATTERN.search(window)
                if match:
                    try:
                        lat_value: float = float(match.group(1))
                        lon_value: float = float(match.group(2))
                        if abs(lat_value) <= 90 and abs(lon_value) <= 180:
                            return cls._format_location(lat_value, lon_value)
                    except ValueError:
                        pass
                search_start = index + len(token)
        return None

    @classmethod
    def _format_location(cls, latitude: float, longitude: float) -> str:
        """
        用途说明：把经纬度格式化为统一的展示文本。
        入参说明：
            latitude (float) - 纬度（南纬为负）。
            longitude (float) - 经度（西经为负）。
        返回值说明：str - '纬度, 经度'，保留 6 位小数。
        """
        return f"{latitude:.6f}, {longitude:.6f}"