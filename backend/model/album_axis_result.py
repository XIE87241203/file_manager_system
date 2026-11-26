from dataclasses import dataclass, field
from typing import List

from backend.model.album_axis_item_result import AlbumAxisItemResult


@dataclass
class AlbumAxisResult:
    """
    用途：表示相册分级轴查询结果。
    入参说明：
        level (str): 轴层级，可选 year、month、day、initial。
        items (List[AlbumAxisItemResult]): 当前层级有数据的轴项列表。
    返回值说明：无。
    """
    level: str = ""
    items: List[AlbumAxisItemResult] = field(default_factory=list)
