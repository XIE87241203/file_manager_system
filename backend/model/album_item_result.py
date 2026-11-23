from dataclasses import dataclass
from typing import Optional


@dataclass
class AlbumItemResult:
    """
    用途：相册瀑布流单个媒体项的 API 返回数据类（图片 / 视频）
    """
    file_path: str = ""                          # 文件完整路径
    file_name: str = ""                          # 文件名（含后缀）
    file_type: str = ""                          # 媒体类型：image / video
    file_size: int = 0                           # 文件大小（字节）
    thumbnail_path: Optional[str] = None         # 缩略图物理路径，空表示尚未生成
    video_duration: Optional[float] = None       # 视频时长（秒），图片为空
    scan_time: Optional[str] = None              # 文件入库（扫描）时间