from dataclasses import dataclass, field
from typing import List, Optional

from backend.db.db_constants import DBConstants


@dataclass
class DuplicateFileDBModel:
    """
    用途：duplicate_files 表对应的数据库模型
    入参说明：
        id (Optional[int]): 数据库主键 ID
        group_id (Optional[int]): 所属重复分组的 ID
        file_id (int): 关联的文件索引 ID
        similarity_type (str): 相似类型，如 'md5', 'hash'
        similarity_rate (float): 相似率，1.0 表示完全相同
    """
    id: Optional[int] = None
    group_id: Optional[int] = None
    file_id: int = 0
    similarity_type: str = DBConstants.SimilarityType.MD5
    similarity_rate: float = 1.0


@dataclass
class DuplicateGroupDBModel:
    """
    用途：duplicate_groups 表对应的数据库模型
    入参说明：
        id (Optional[int]): 数据库主键 ID
        group_name (str): 分组名称
        files (List[DuplicateFileDBModel]): 该组内的重复文件详情列表
    """
    id: Optional[int] = None
    group_name: str = ""
    files: List[DuplicateFileDBModel] = field(default_factory=list)
