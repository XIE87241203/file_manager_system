from dataclasses import dataclass, field
from typing import Optional, List

from backend.model.db.file_index_db_model import FileIndexDBModel


@dataclass
class DuplicateGroupResult:
    id: Optional[int] = None
    group_name: str  = ""
    file_ids: List[FileIndexDBModel] = field(default_factory=list) #file_id列表
