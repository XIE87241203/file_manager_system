from dataclasses import dataclass
from typing import Optional


@dataclass
class RepositoryResult:
    """
    用途：用于 API 返回的仓库基本信息（不含配置详情）。
    入参说明：
        id (int): 仓库 ID。
        name (str): 仓库名称。
        create_time (Optional[str]): 创建时间。
    """
    id: int = 0
    name: str = ""
    create_time: Optional[str] = None