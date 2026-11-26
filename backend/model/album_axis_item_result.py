from dataclasses import dataclass


@dataclass
class AlbumAxisItemResult:
    """
    用途：表示相册轴单个分组项。
    入参说明：
        key (str): 分组键；年份为 YYYY，月份为 YYYY-MM，日期为 YYYY-MM-DD，首字母为单个字母或 #。
        first_path (str): 当前排序和筛选条件下该分组第一条媒体的完整路径。
        count (int): 该分组当前符合条件的媒体数量。
    返回值说明：无。
    """
    key: str = ""
    first_path: str = ""
    count: int = 0
