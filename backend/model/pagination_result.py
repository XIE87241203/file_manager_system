from dataclasses import dataclass
from typing import List, TypeVar, Generic

T = TypeVar('T')

@dataclass
class PaginationResult(Generic[T]):
    """
    用途：表示分页查询的结果数据类，支持泛型。
    入参说明：
        total (int): 符合条件的总记录数。
        list (List[T]): 当前页的数据列表（泛型）。
        page (int): 当前页码。
        limit (int): 每页记录数限制。
        sort_by (str): 排序字段名称。
        order (str): 排序方向 (如 'ASC' 或 'DESC')。
    """
    total: int
    list: List[T]
    page: int
    limit: int
    sort_by: str
    order: str
