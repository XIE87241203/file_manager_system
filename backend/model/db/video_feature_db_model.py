from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoFeatureDBModel:
    """
    用途：视频特征数据类，对应 video_features 表
    """
    id: Optional[int] = None
    file_md5: str = ""
    video_hashes: Optional[str] = None
    duration: Optional[float] = None