from typing import List

from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.batch_check_db_model import BatchCheckDBModel


class BatchCheckProcessor(BaseDBProcessor):
    """
    用途说明：批量检测结果处理器，负责 batch_check_results 表的增删改查。
    """

    def __init__(self):
        """
        用途说明：初始化处理器，确保表结构存在。
        """
        self._create_table()

    def _create_table(self) -> None:
        """
        用途说明：创建批量检测结果存储表。
        """
        sql = """
        CREATE TABLE IF NOT EXISTS batch_check_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            detail TEXT
        )
        """
        self._execute(sql)

    def batch_insert_results(self, results: List[BatchCheckDBModel]) -> int:
        """
        用途说明：批量插入检测结果。
        入参说明：results (List[BatchCheckDBModel]): 结果列表。
        返回值说明：int: 插入成功的记录条数。
        """
        if not results:
            return 0
        sql = "INSERT INTO batch_check_results (name, source, detail) VALUES (?, ?, ?)"
        params = [(r.name, r.source, r.detail) for r in results]
        return self._execute_batch(sql, params)

    def get_all_results(self) -> List[BatchCheckDBModel]:
        """
        用途说明：获取所有已保存的检测结果。
        返回值说明：List[BatchCheckDBModel]: 结果模型列表。
        """
        sql = "SELECT id, name, source, detail FROM batch_check_results"
        rows = self._execute(sql, is_query=True)
        # rows 在这里已经是 dict 列表了（由 BaseDBProcessor._execute 处理过）
        return [BatchCheckDBModel(id=row['id'], name=row['name'], source=row['source'], detail=row['detail']) for row in rows]

    def clear_results(self) -> bool:
        """
        用途说明：清空检测结果表。
        返回值说明：bool: 是否成功。
        """
        return self._clear_table("batch_check_results")
