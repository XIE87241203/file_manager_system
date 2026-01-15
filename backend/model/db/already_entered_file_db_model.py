from dataclasses import dataclass
from typing import Optional


@dataclass
class AlreadyEnteredFileDBModel:
    """
    用途说明：曾录入文件名表数据库模型，对应 already_entered_file 表。
    """
    file_name: str  # 文件名
    id: Optional[int] = None  # 自增 ID
    add_time: Optional[str] = None  # 添加时间
