from dataclasses import dataclass
from typing import Optional


@dataclass
class HistoryFileIndexDBModule:
    """
    用途：历史文件索引数据类，对应 history_file_index 表
    """
    id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_md5: str = ""
    file_size: int = 0
    file_type: Optional[str] = None           # 新增：文件类型
    video_duration: Optional[float] = None   # 新增：视频时长
    video_codec: Optional[str] = None         # 新增：视频编码
    scan_time: Optional[str] = None
    delete_time: Optional[str] = None
