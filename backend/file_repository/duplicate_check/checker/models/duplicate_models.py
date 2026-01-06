from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class DuplicateFile:
    """
    用途：表示查重结果中的单个文件信息。
    入参说明：
        file_name (str): 文件名。
        file_path (str): 文件绝对路径。
        file_md5 (Optional[str]): 文件的 MD5 值。
        thumbnail_path (Optional[str]): 缩略图路径。
        extra_info (Dict[str, Any]): 额外信息，用于存储特定类型检查器的附加数据（如视频时长）。
    """
    file_name: str
    file_path: str
    file_md5: Optional[str] = None
    thumbnail_path: Optional[str] = None
    extra_info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DuplicateGroup:
    """
    用途：表示一组相似或重复的文件。
    入参说明：
        group_id (str): 分组 ID。
        checker_type (str): 检查器类型（如 'md5', 'video_similarity'）。
        files (List[DuplicateFile]): 分组内的文件列表。
    """
    group_id: str
    checker_type: str
    files: List[DuplicateFile]
