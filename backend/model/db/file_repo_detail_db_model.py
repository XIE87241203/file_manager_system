from dataclasses import dataclass
from typing import Optional

@dataclass
class FileRepoDetailDBModel:
    """
    用途：文件仓库详情数据库模型
    """
    total_count: int = 0
    total_size: int = 0
    update_time: Optional[str] = None
    id: Optional[int] = None
