from typing import List

from backend.db.db_operations import DBOperations
from backend.model.db.already_entered_file_db_model import AlreadyEnteredFileDBModel
from backend.model.pagination_result import PaginationResult


class AlreadyEnteredFileService:
    """
    用途说明：曾录入文件名库业务服务类，封装曾录入文件名的增删改查操作。
    """

    @staticmethod
    def add_already_entered_files(file_names: List[str]) -> bool:
        """
        用途说明：批量添加曾录入文件名。
        入参说明：file_names (List[str]): 文件名列表。
        返回值说明：bool: 是否成功。
        """
        return DBOperations.add_already_entered_files(file_names)

    @staticmethod
    def batch_delete_already_entered_files(file_ids: List[int]) -> int:
        """
        用途说明：批量删除曾录入文件名记录。
        入参说明：file_ids (List[int]): 记录 ID 列表。
        返回值说明：int: 成功删除的记录条数。
        """
        from backend.db.processor_manager import processor_manager
        return processor_manager.already_entered_file_processor.batch_delete_already_entered_files(file_ids)

    @staticmethod
    def search_already_entered_file_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[AlreadyEnteredFileDBModel]:
        """
        用途说明：分页查询曾录入文件名。
        入参说明：
            page (int): 页码
            limit (int): 每页条数
            sort_by (str): 排序字段
            order (bool): 是否升序
            search_query (str): 搜索词
        返回值说明：PaginationResult[AlreadyEnteredFileDBModel]: 分页结果
        """
        return DBOperations.search_already_entered_file_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def clear_already_entered_repository() -> bool:
        """
        用途说明：清空曾录入文件名库。
        返回值说明：bool: 是否成功。
        """
        return DBOperations.clear_already_entered_repository()
