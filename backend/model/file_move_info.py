from dataclasses import dataclass


@dataclass(frozen=True)
class FileMoveInfo:
    """
    用途：描述一次文件移动或改名的路径变更，供文件生命周期服务和索引适配器共同使用。
    """

    old_path: str
    new_path: str
