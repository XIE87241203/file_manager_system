import sqlite3
from typing import List, Optional

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.batch_check_db_model import BatchCheckDBModel


class BatchCheckProcessor(BaseDBProcessor):
    """
    用途说明：批量检测结果处理器，负责 batch_check_results 表的增删改查。
    """

    @staticmethod
    def batch_insert_results(results: List[BatchCheckDBModel]) -> int:
        """
        用途说明：批量插入检测结果。
        入参说明：results (List[BatchCheckDBModel]): 待入库的检测结果模型列表。
        返回值说明：int: 成功插入的记录条数。
        """
        if not results:
            return 0
        
        query: str = f"""
            INSERT INTO {DBConstants.BatchCheckResult.TABLE_NAME} (
                {DBConstants.BatchCheckResult.COL_NAME},
                {DBConstants.BatchCheckResult.COL_SOURCE},
                {DBConstants.BatchCheckResult.COL_DETAIL}
            ) VALUES (?, ?, ?)
        """
        params: List[tuple] = [(r.name, r.source, r.detail) for r in results]
        return BaseDBProcessor._execute_batch(query, params)

    @staticmethod
    def get_all_results(sort_by: Optional[str] = None, order_asc: bool = False) -> List[BatchCheckDBModel]:
        """
        用途说明：获取所有已保存的检测结果，支持排序。
        入参说明：
            sort_by (Optional[str]): 排序字段，可选 'name' 或 'source'。
            order_asc (bool): 如果为 True 则升序，否则降序。
        返回值说明：List[BatchCheckDBModel]: 包含所有检测结果的数据模型列表。
        """
        query: str = f"""
            SELECT 
                {DBConstants.BatchCheckResult.COL_ID},
                {DBConstants.BatchCheckResult.COL_NAME},
                {DBConstants.BatchCheckResult.COL_SOURCE},
                {DBConstants.BatchCheckResult.COL_DETAIL}
            FROM {DBConstants.BatchCheckResult.TABLE_NAME}
        """
        
        allowed_sort_columns: dict = {
            'name': DBConstants.BatchCheckResult.COL_NAME,
            'source': DBConstants.BatchCheckResult.COL_SOURCE
        }

        # 构建排序子句
        order_clause: str = ""
        if sort_by and sort_by in allowed_sort_columns:
            column_to_sort = allowed_sort_columns[sort_by]
            order_direction = "ASC" if order_asc else "DESC"
            order_clause = f" ORDER BY {column_to_sort} {order_direction}"
        
        query += order_clause

        rows: List[dict] = BaseDBProcessor._execute(query, is_query=True)
        
        return [
            BatchCheckDBModel(
                id=row[DBConstants.BatchCheckResult.COL_ID],
                name=row[DBConstants.BatchCheckResult.COL_NAME],
                source=row[DBConstants.BatchCheckResult.COL_SOURCE],
                detail=row[DBConstants.BatchCheckResult.COL_DETAIL]
            ) for row in rows
        ]

    @staticmethod
    def delete_results_by_names(file_names: List[str], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：根据文件名批量删除检测结果。
        入参说明：
            file_names (List[str]): 文件名列表。
            conn (Optional[sqlite3.Connection]): 数据库连接对象。
        返回值说明：int: 成功删除的数量。
        """
        if not file_names:
            return 0
        query: str = f"DELETE FROM {DBConstants.BatchCheckResult.TABLE_NAME} WHERE {DBConstants.BatchCheckResult.COL_NAME} = ?"
        params: List[tuple] = [(name,) for name in file_names]
        return BaseDBProcessor._execute_batch(query, params, conn=conn)

    @staticmethod
    def clear_results() -> bool:
        """
        用途说明：清空检测结果表。
        返回值说明：bool: 是否清空成功。
        """
        return BaseDBProcessor._clear_table(DBConstants.BatchCheckResult.TABLE_NAME)
