from dataclasses import dataclass, field
from typing import Optional, List

from backend.db.db_constants import DBConstants
from backend.model.db.file_index_db_model import FileIndexDBModel


@dataclass
class DuplicateFileResult:
    """
    用途：用于 API 返回的重复文件详情，包含文件索引信息和相似度信息
    """
    file_info: FileIndexDBModel
    similarity_type: str = DBConstants.SimilarityType.MD5
    similarity_rate: float = 1.0


@dataclass
class DuplicateGroupResult:
    """
    用途：用于 API 返回的重复分组结果
    """
    id: Optional[int] = None
    group_name: str = ""
    create_time: Optional[str] = None
    # 包含该组内所有重复文件的详细信息及相似度
    files: List[DuplicateFileResult] = field(default_factory=list)
