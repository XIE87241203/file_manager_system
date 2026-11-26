from dataclasses import dataclass


@dataclass
class AlbumAxisItemDBModel:
    """
    用途：表示从数据库聚合得到的相册轴分组项。
    入参说明：
        key (str): 年份、月份、日期或首字母分组键。
        first_path (str): 该分组按当前排序规则的第一条媒体路径。
        count (int): 该分组的媒体数量。
    返回值说明：无。
    """
    key: str = ""
    first_path: str = ""
    count: int = 0
