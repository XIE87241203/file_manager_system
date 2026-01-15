from typing import List

from backend.db.db_operations import DBOperations
from backend.model.db.ignore_file_db_model import IgnoreFileDBModel
from backend.model.pagination_result import PaginationResult


class IgnoreFileService:
    """
    用途：忽略文件库业务服务类，封装忽略文件的增删改查操作。
    """

    @staticmethod
    def add_ignore_files(file_names: List[str]) -> bool:
        """
        用途：批量添加忽略文件名。
        入参说明：file_names (List[str]): 文件名列表。
        返回值说明：bool: 是否成功。
        """
        return DBOperations.add_ignore_files(file_names)

    @staticmethod
    def batch_delete_ignore_files(file_ids: List[int]) -> int:
        """
        用途：批量删除忽略文件记录。
        入参说明：file_ids (List[int]): 记录 ID 列表。
        返回值说明：int: 成功删除的记录条数。
        """
        from backend.db.processor_manager import processor_manager
        return processor_manager.ignore_file_processor.batch_delete_ignore_files(file_ids)

    @staticmethod
    def search_ignore_file_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[IgnoreFileDBModel]:
        """
        用途：分页查询忽略文件。
        入参说明：
            page (int): 页码
            limit (int): 每页条数
            sort_by (str): 排序字段
            order (bool): 是否升序
            search_query (str): 搜索词
        返回值说明：PaginationResult[IgnoreFileDBModel]: 分页结果
        """
        return DBOperations.search_ignore_file_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def clear_ignore_repository() -> bool:
        """
        用途：清空忽略文件库。
        返回值说明：bool: 是否成功。
        """
        return DBOperations.clear_ignore_repository()
