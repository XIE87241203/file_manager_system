from dataclasses import dataclass
from typing import Optional


@dataclass
class ThumbnailResult:
    """
    用途：缩略图按需生成结果数据类（统一缩略图生成接口的返回结构）。
    字段说明：
        file_path (str): 源文件完整路径。
        thumbnail_path (Optional[str]): 生成或复用到的缩略图物理路径；失败时为 None。
    """
    file_path: str = ''
    thumbnail_path: Optional[str] = None