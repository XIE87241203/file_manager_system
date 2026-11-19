from dataclasses import dataclass
from typing import Optional


@dataclass
class OrganizeRecordDBModel:
    """
    用途：整理历史数据库模型，与 organize_records 表列一一对应。
    说明：每保存一个整理文件写入一条，记录原路径/原文件名/整理后路径/整理后文件名/整理时间。
    """
    original_path: str = ''
    original_name: str = ''
    organized_path: str = ''
    organized_name: str = ''
    organize_time: Optional[str] = None
    id: Optional[int] = None