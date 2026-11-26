from dataclasses import dataclass
from typing import Generic, List, TypeVar

T = TypeVar('T')


@dataclass
class CursorPaginationResult(Generic[T]):
    """
    用途：表示只使用游标与每页数量的分页结果，不包含页码。
    入参说明：
        total (int): 符合条件的总记录数。
        list (List[T]): 当前批次的数据列表（泛型）。
        limit (int): 当前批次的最大记录数。
        sort_by (str): 排序字段名称。
        order (str): 排序方向（如 'ASC' 或 'DESC'）。
    """
    total: int
    list: List[T]
    limit: int
    sort_by: str
    order: str
