from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DuplicateGroupDBModule:
    id: Optional[int] = None
    group_name: str  = ""
    file_ids: List[int] = field(default_factory=list) #file_id列表



