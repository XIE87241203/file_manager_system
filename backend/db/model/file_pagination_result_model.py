from dataclasses import dataclass
from typing import List
from backend.db.model.file_index_model import FileIndex

@dataclass
class FilePaginationResult:
    """
    用途：表示文件列表分页查询的结果数据类。
    入参说明：
        total (int): 符合条件的总记录数。
        list (List[FileIndex]): 当前页的文件数据列表。
        page (int): 当前页码。
        limit (int): 每页记录数限制。
        sort_by (str): 排序字段名称。
        order (str): 排序方向 (如 'ASC' 或 'DESC')。
    """
    total: int
    list: List[FileIndex]
    page: int
    limit: int
    sort_by: str
    order: str
