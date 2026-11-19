from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.organize_record_db_model import OrganizeRecordDBModel


class OrganizeRecordProcessor(BaseDBProcessor):
    """
    用途：整理历史数据库处理器，负责 organize_records 表的写入。
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