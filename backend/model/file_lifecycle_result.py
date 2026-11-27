from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class FileIndexChangeResult:
    """
    用途：记录单个索引适配器在文件生命周期操作中的影响行数。
    """

    index_name: str
    affected_rows: int


@dataclass
class FileLifecycleResult:
    """
    用途：汇总一次文件生命周期操作的文件数量及各索引影响行数。
    """

    affected_files: int = 0
    index_changes: List[FileIndexChangeResult] = field(default_factory=list)
