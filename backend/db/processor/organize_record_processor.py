from typing import Iterator, List, Optional

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.organize_record_db_model import OrganizeRecordDBModel


class OrganizeRecordProcessor(BaseDBProcessor):
    """
    用途：整理历史数据库处理器，负责 organize_records 表的写入与分页查询。
    """

    def insert_record(self, model: OrganizeRecordDBModel) -> bool:
        """
        用途说明：写入一条整理历史记录（整理时间由数据库默认值生成）。
        入参说明：model (OrganizeRecordDBModel) - 待写入的整理记录模型。
        返回值说明：bool - 写入成功返回 True。
        """
        self._execute(
            f"INSERT INTO {DBConstants.OrganizeRecord.TABLE_NAME} "
            f"({DBConstants.OrganizeRecord.COL_ORIGINAL_PATH}, "
            f"{DBConstants.OrganizeRecord.COL_ORIGINAL_NAME}, "
            f"{DBConstants.OrganizeRecord.COL_ORGANIZED_PATH}, "
            f"{DBConstants.OrganizeRecord.COL_ORGANIZED_NAME}) "
            f"VALUES (?, ?, ?, ?)",
            (model.original_path, model.original_name, model.organized_path, model.organized_name)
        )
        return True

    def count_records(self) -> int:
        """
        用途说明：统计当前仓库的整理记录总数。
        入参说明：无（仓库路由由当前请求上下文决定）。
        返回值说明：int - 整理记录总条数。
        """
        row: Optional[dict] = self._execute(
            f"SELECT COUNT(*) AS cnt FROM {DBConstants.OrganizeRecord.TABLE_NAME}",
            is_query=True,
            fetch_one=True
        )
        return int(row['cnt']) if row else 0

    def get_records_page(self, page: int, page_size: int) -> List[OrganizeRecordDBModel]:
        """
        用途说明：分页查询整理记录，按整理时间倒序（时间越靠后越靠前），同时间按 id 倒序保证稳定。
        入参说明：
            page (int): 页码，从 1 开始（由服务层保证合法）。
            page_size (int): 每页条数（由服务层保证合法）。
        返回值说明：List[OrganizeRecordDBModel] - 当前页的整理记录模型列表。
        """
        rows: List[dict] = self._execute(
            f"SELECT * FROM {DBConstants.OrganizeRecord.TABLE_NAME} "
            f"ORDER BY {DBConstants.OrganizeRecord.COL_ORGANIZE_TIME} DESC, "
            f"{DBConstants.OrganizeRecord.COL_ID} DESC LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
            is_query=True
        )
        return [OrganizeRecordDBModel(**row) for row in rows]

    def iter_record_chunks(self, chunk_size: int = 500) -> Iterator[List[OrganizeRecordDBModel]]:
        """
        用途说明：按批迭代全部整理记录（与分页查询同一倒序），供 CSV 导出等大数据量场景分批处理，避免一次性载入全表。
        入参说明：chunk_size (int): 单批条数，默认 500（符合分批处理 100-1000 条的规范）。
        返回值说明：Iterator[List[OrganizeRecordDBModel]] - 每批记录模型列表的迭代器，取完即止。
        """
        offset: int = 0
        while True:
            rows: List[dict] = self._execute(
                f"SELECT * FROM {DBConstants.OrganizeRecord.TABLE_NAME} "
                f"ORDER BY {DBConstants.OrganizeRecord.COL_ORGANIZE_TIME} DESC, "
                f"{DBConstants.OrganizeRecord.COL_ID} DESC LIMIT ? OFFSET ?",
                (chunk_size, offset),
                is_query=True
            )
            if not rows:
                return
            yield [OrganizeRecordDBModel(**row) for row in rows]
            if len(rows) < chunk_size:
                return
            offset += chunk_size