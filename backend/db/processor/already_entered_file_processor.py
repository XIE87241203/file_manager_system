import sqlite3
from typing import Optional, List, Tuple, Dict

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.already_entered_file_db_model import AlreadyEnteredFileDBModel
from backend.model.pagination_result import PaginationResult


class AlreadyEnteredFileProcessor(BaseDBProcessor):
    """
    用途说明：曾录入文件名表数据库处理器，负责 already_entered_file 表的相关 CRUD 操作。
    """

    @staticmethod
    def add_already_entered_files(file_names: List[str], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量添加曾录入文件名。
        入参说明：
            file_names (List[str]): 待添加的文件名列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：返回成功插入的条数。
        """
        if not file_names:
            return 0
        
        query: str = f'''
            INSERT OR IGNORE INTO {DBConstants.AlreadyEnteredFile.TABLE_NAME} (
                {DBConstants.AlreadyEnteredFile.COL_FILE_NAME}
            )
            VALUES (?)
        '''
        data = [(name,) for name in file_names]
        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def batch_delete_already_entered_files(file_ids: List[int], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量删除指定的曾录入文件名记录。
        入参说明：
            file_ids (List[int]): 记录 ID 列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：成功删除的条数。
        """
        if not file_ids:
            return 0
        query: str = f"DELETE FROM {DBConstants.AlreadyEnteredFile.TABLE_NAME} WHERE {DBConstants.AlreadyEnteredFile.COL_ID} = ?"
        data = [(f_id,) for f_id in file_ids]
        return BaseDBProcessor._execute_batch(query, data, conn=conn)

    @staticmethod
    def get_paged_list(page: int, limit: int, sort_by: str, order: bool, search_query: str) -> PaginationResult[AlreadyEnteredFileDBModel]:
        """
        用途说明：分页搜索曾录入文件名列表。
        """
        allowed_cols: List[str] = [
            DBConstants.AlreadyEnteredFile.COL_ID,
            DBConstants.AlreadyEnteredFile.COL_FILE_NAME,
            DBConstants.AlreadyEnteredFile.COL_ADD_TIME
        ]
        
        return BaseDBProcessor._search_paged_list(
            table_name=DBConstants.AlreadyEnteredFile.TABLE_NAME,
            model_class=AlreadyEnteredFileDBModel,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order,
            search_query=search_query,
            search_column=DBConstants.AlreadyEnteredFile.COL_FILE_NAME,
            allowed_sort_columns=allowed_cols,
            default_sort_column=DBConstants.AlreadyEnteredFile.COL_ADD_TIME
        )

    @staticmethod
    def clear_all_table() -> bool:
        """
        用途说明：清空曾录入文件名表。
        """
        return BaseDBProcessor._clear_table(DBConstants.AlreadyEnteredFile.TABLE_NAME)

    @staticmethod
    def check_names_exist_by_patterns(name_patterns: List[Tuple[str, str]], conn: Optional[sqlite3.Connection] = None) -> Dict[str, str]:
        """
        用途说明：批量检查文件名是否存在于曾录入库。采用 CTE 批量模糊匹配优化。
        入参说明：name_patterns (List[Tuple[str, str]]): 包含 (原始文件名, 搜索模式) 的列表。
        返回值说明：Dict[str, str] - 返回匹配到的字典，Key 为原始文件名，Value 为库中匹配到的文件名。
        """
        if not name_patterns:
            return {}
        
        results: Dict[str, str] = {}
        chunk_size: int = 200
        for i in range(0, len(name_patterns), chunk_size):
            chunk = name_patterns[i:i + chunk_size]
            placeholders = ",".join(["(?, ?)"] * len(chunk))
            sql_params = []
            for name, pattern in chunk:
                sql_params.extend([name, pattern])
            
            query = f"""
                WITH SearchTerms(original_name, pattern) AS (VALUES {placeholders})
                SELECT st.original_name, ae.{DBConstants.AlreadyEnteredFile.COL_FILE_NAME} AS matched_name
                FROM SearchTerms st
                JOIN {DBConstants.AlreadyEnteredFile.TABLE_NAME} ae ON ae.{DBConstants.AlreadyEnteredFile.COL_FILE_NAME} LIKE st.pattern
            """
            rows = BaseDBProcessor._execute(query, tuple(sql_params), is_query=True, conn=conn)
            for row in rows:
                results[row['original_name']] = row['matched_name']
        return results
