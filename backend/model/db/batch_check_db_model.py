from dataclasses import dataclass

@dataclass
class BatchCheckDBModel:
    """
    用途说明：批量检测结果持久化模型。
    """
    id: int = 0
    name: str = ""          # 原始文件名
    source: str = ""        # 来源库 (index/history/pending/new)
    detail: str = ""        # 详细信息
