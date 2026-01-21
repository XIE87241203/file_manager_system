from typing import List

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
    def get_all_results() -> List[BatchCheckDBModel]:
        """
        用途说明：获取所有已保存的检测结果。
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
    def clear_results() -> bool:
        """
        用途说明：清空检测结果表。
        返回值说明：bool: 是否清空成功。
        """
        return BaseDBProcessor._clear_table(DBConstants.BatchCheckResult.TABLE_NAME)
