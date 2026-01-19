from dataclasses import dataclass
from typing import List

@dataclass
class BatchCheckItemResult:
    """
    用途说明：批量检测单条记录结果的数据类。
    """
    name: str          # 原始文件名
    source: str        # 来源库 (index/history/pending/new)
    detail: str        # 详细信息 (如路径或匹配到的文件名)

@dataclass
class BatchCheckResult:
    """
    用途说明：批量检测全量结果的数据类。
    """
    results: List[BatchCheckItemResult]
