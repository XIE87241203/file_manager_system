from typing import List, Dict, Tuple

from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.model.db.pending_entry_file_db_model import PendingEntryFileDBModel
from backend.model.pagination_result import PaginationResult


class PendingEntryFileService:
    """
    用途说明：待录入文件库业务服务类，封装待录入文件的增删改查操作。
    """

    @staticmethod
    def add_pending_entry_files(file_names: List[str]) -> bool:
        """
        用途说明：批量添加待录入文件名。
        入参说明：file_names (List[str]): 文件名列表。
        返回值说明：bool: 是否成功。
        """
        return DBOperations.add_pending_entry_files(file_names)

    @staticmethod
    def batch_delete_pending_entry_files(file_ids: List[int]) -> int:
        """
        用途说明：批量删除待录入文件记录。
        入参说明：file_ids (List[int]): 记录 ID 列表。
        返回值说明：int: 成功删除的记录条数。
        """
        from backend.db.processor_manager import processor_manager
        return processor_manager.pending_entry_file_processor.batch_delete_pending_entry_files(file_ids)

    @staticmethod
    def search_pending_entry_file_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[PendingEntryFileDBModel]:
        """
        用途说明：分页查询待录入文件。
        入参说明：
            page (int): 页码
            limit (int): 每页条数
            sort_by (str): 排序字段
            order (bool): 是否升序
            search_query (str): 搜索词
        返回值说明：PaginationResult[PendingEntryFileDBModel]: 分页结果
        """
        return DBOperations.search_pending_entry_file_list(page, limit, sort_by, order, search_query)

    @staticmethod
    def clear_pending_entry_repository() -> bool:
        """
        用途说明：清空待录入文件库。
        返回值说明：bool: 是否成功。
        """
        return DBOperations.clear_pending_entry_repository()

    @staticmethod
    def check_batch_files(file_names: List[str]) -> Dict[str, dict]:
        """
        用途说明：全库批量检测文件名是否存在。采用预处理模式匹配，提升批量搜索效率。
        入参说明：file_names (List[str]): 待检测的文件名列表。
        返回值说明：Dict[str, dict]: 包含检测结果的字典，格式如 {文件名: {source: 'index'|'history'|'pending'|'new', detail: '...'}}
        """
        results: Dict[str, dict] = {}
        from backend.db.processor_manager import processor_manager
        
        # 1. 批量预处理搜索模式
        name_patterns: List[Tuple[str, str]] = [(name, Utils.process_search_query(name)) for name in file_names]
        
        # 2. 调用处理器进行批量搜索
        # 检测文件索引库 (获取路径)
        index_matches: Dict[str, str] = processor_manager.file_index_processor.get_paths_by_patterns(name_patterns)
        
        # 检测曾录入库
        history_matches: set = processor_manager.already_entered_file_processor.check_names_exist_by_patterns(name_patterns)
        
        # 检测待录入库
        pending_matches: set = processor_manager.pending_entry_file_processor.check_names_exist_by_patterns(name_patterns)
        
        # 3. 汇总结果
        for name in file_names:
            if name in index_matches:
                results[name] = {"source": "index", "detail": index_matches[name]}
            elif name in history_matches:
                results[name] = {"source": "history", "detail": "存在于历史记录"}
            elif name in pending_matches:
                results[name] = {"source": "pending", "detail": "已在待录入队列"}
            else:
                results[name] = {"source": "new", "detail": ""}
                
        return results
