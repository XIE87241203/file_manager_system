from dataclasses import dataclass
from typing import Optional


@dataclass
class ImageFeatureDBModel:
    """
    用途：图片特征数据类，对应 image_features 表（缓存图片感知哈希）
    """
    id: Optional[int] = None
    file_md5: str = ""
    image_hash: Optional[str] = None