from dataclasses import dataclass
from typing import Optional

@dataclass
class FileIndex:
    """
    用途：文件索引数据类，对应 file_index 表
    """
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_md5: str = ""
    thumbnail_path: Optional[str] = None
    scan_time: Optional[str] = None
