from dataclasses import dataclass
from typing import Optional

@dataclass
class VideoInfoCache:
    """
    用途：视频信息缓存数据类，对应 video_info_cache 表
    """
    id: Optional[int] = None
    path: str = ""
    video_name: str = ""
    md5: str = ""
    duration: Optional[float] = None
    video_hashes: Optional[str] = None
