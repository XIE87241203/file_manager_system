from dataclasses import dataclass
from typing import Optional

@dataclass
class HistoryFileIndex:
    """
    用途：历史文件索引数据类，对应 history_file_index 表
    """
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_md5: str = ""
    scan_time: Optional[str] = None
