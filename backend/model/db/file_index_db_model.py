from dataclasses import dataclass
from typing import Optional

@dataclass
class FileIndexDBModel:
    """
    用途：文件索引数据类，对应 file_index 表
    """
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_md5: str = ""
    file_size: int = 0
    file_type: Optional[str] = None           # 新增：文件类型
    video_duration: Optional[float] = None   # 新增：视频时长
    video_codec: Optional[str] = None         # 新增：视频编码
    recycle_bin_time: Optional[str] = None
    thumbnail_path: Optional[str] = None
    scan_time: Optional[str] = None
    file_mtime: Optional[str] = None         # 文件最后修改时间（扫描时从磁盘读取，用于时间轴分组）
    file_exif_time: Optional[str] = None     # EXIF 拍摄时间/视频创建时间（相册优先使用，缺失时回退修改时间）
    file_location: Optional[str] = None      # 拍摄地点（EXIF GPS / 视频 ISO 6709 坐标文本）
    media_width: Optional[int] = None       # 图片或视频显示宽度（像素），0 表示已检查但无法获取
    media_height: Optional[int] = None      # 图片或视频显示高度（像素），0 表示已检查但无法获取
