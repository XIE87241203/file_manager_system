from dataclasses import dataclass
from typing import Optional


@dataclass
class IgnoreFileDBModel:
    """
    用途：忽略文件表数据库模型，对应 ignore_file 表。
    """
    file_name: str  # 文件名
    id: Optional[int] = None  # 自增 ID
    add_time: Optional[str] = None  # 添加时间
