from typing import Iterator, List, Optional, Tuple

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.organize_record_db_model import OrganizeRecordDBModel


class OrganizeRecordProcessor(BaseDBProcessor):
    """
    用途：整理历史数据库处理器，负责 organize_records 表的写入与分页查询（支持文件名关键词搜索）。
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

    @staticmethod
    def _keyword_filter(keyword: str) -> Tuple[str, tuple]:
        """
        用途说明：构建文件名关键词搜索的 WHERE 子句与参数：同时匹配整理后文件名与整理前文件名（OR，模糊包含，
            SQLite LIKE 对英文字母默认不区分大小写）；关键词中的 LIKE 通配符（% _ \\）按字面量转义。
        入参说明：keyword (str): 搜索关键词，空串表示不筛选。
        返回值说明：Tuple[str, tuple] - (WHERE 子句片段（含前导空格，空关键词时为空串), 绑定参数元组)。
        """
        if not keyword:
            return '', ()
        escaped: str = keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        pattern: str = f'%{escaped}%'
        clause: str = (
            f" WHERE ({DBConstants.OrganizeRecord.COL_ORGANIZED_NAME} LIKE ? ESCAPE '\\' "
            f"OR {DBConstants.OrganizeRecord.COL_ORIGINAL_NAME} LIKE ? ESCAPE '\\')"
        )
        return clause, (pattern, pattern)

    def count_records(self, keyword: str = '') -> int:
        """
        用途说明：统计当前仓库的整理记录总数（可按文件名关键词筛选）。
        入参说明：keyword (str): 搜索关键词，同时模糊匹配整理后/整理前文件名，空串表示统计全部。
        返回值说明：int - 符合条件的整理记录条数。
        """
        where, params = self._keyword_filter(keyword)
        row: Optional[dict] = self._execute(
            f"SELECT COUNT(*) AS cnt FROM {DBConstants.OrganizeRecord.TABLE_NAME}{where}",
            params,
            is_query=True,
            fetch_one=True
        )
        return int(row['cnt']) if row else 0

    def get_records_page(self, page: int, page_size: int, keyword: str = '') -> List[OrganizeRecordDBModel]:
        """
        用途说明：分页查询整理记录，按整理时间倒序（时间越靠后越靠前），同时间按 id 倒序保证稳定；
            可按文件名关键词筛选（同时匹配整理后/整理前文件名）。
        入参说明：
            page (int): 页码，从 1 开始（由服务层保证合法）。
            page_size (int): 每页条数（由服务层保证合法）。
            keyword (str): 搜索关键词，空串表示不筛选。
        返回值说明：List[OrganizeRecordDBModel] - 当前页的整理记录模型列表。
        """
        where, params = self._keyword_filter(keyword)
        rows: List[dict] = self._execute(
            f"SELECT * FROM {DBConstants.OrganizeRecord.TABLE_NAME}{where} "
            f"ORDER BY {DBConstants.OrganizeRecord.COL_ORGANIZE_TIME} DESC, "
            f"{DBConstants.OrganizeRecord.COL_ID} DESC LIMIT ? OFFSET ?",
            params + (page_size, (page - 1) * page_size),
            is_query=True
        )
        return [OrganizeRecordDBModel(**row) for row in rows]

    def iter_record_chunks(self, chunk_size: int = 500, keyword: str = '') -> Iterator[List[OrganizeRecordDBModel]]:
        """
        用途说明：按批迭代整理记录（与分页查询同一倒序和筛选），供 CSV 导出等大数据量场景分批处理，避免一次性载入全表。
        入参说明：
            chunk_size (int): 单批条数，默认 500（符合分批处理 100-1000 条的规范）。
            keyword (str): 搜索关键词，空串表示迭代全部记录。
        返回值说明：Iterator[List[OrganizeRecordDBModel]] - 每批记录模型列表的迭代器，取完即止。
        """
        where, params = self._keyword_filter(keyword)
        offset: int = 0
        while True:
            rows: List[dict] = self._execute(
                f"SELECT * FROM {DBConstants.OrganizeRecord.TABLE_NAME}{where} "
                f"ORDER BY {DBConstants.OrganizeRecord.COL_ORGANIZE_TIME} DESC, "
                f"{DBConstants.OrganizeRecord.COL_ID} DESC LIMIT ? OFFSET ?",
                params + (chunk_size, offset),
                is_query=True
            )
            if not rows:
                return
            yield [OrganizeRecordDBModel(**row) for row in rows]
            if len(rows) < chunk_size:
                return
            offset += chunk_size