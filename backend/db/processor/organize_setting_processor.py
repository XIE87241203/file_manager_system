from typing import Optional

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.organize_setting_db_model import OrganizeSettingDBModel


class OrganizeSettingProcessor(BaseDBProcessor):
    """
    用途：整理模块设置数据库处理器，负责 organize_settings 表的读写（保持单行记录）。
    """

    def get_setting(self) -> Optional[OrganizeSettingDBModel]:
        """
        用途说明：获取当前仓库的整理设置记录。
        入参说明：无（仓库路由由当前请求上下文决定）。
        返回值说明：Optional[OrganizeSettingDBModel] - 存在记录时返回模型对象，否则返回 None。
        """
        row: Optional[dict] = self._execute(
            f"SELECT * FROM {DBConstants.OrganizeSetting.TABLE_NAME} "
            f"ORDER BY {DBConstants.OrganizeSetting.COL_ID} DESC LIMIT 1",
            is_query=True,
            fetch_one=True
        )
        if row:
            return OrganizeSettingDBModel(**row)
        return None

    def save_setting(self, model: OrganizeSettingDBModel) -> bool:
        """
        用途说明：保存整理设置（存在记录则更新，否则插入，始终保持单行）。
        入参说明：model (OrganizeSettingDBModel) - 待保存的设置模型，列表字段须已序列化为 JSON 文本。
        返回值说明：bool - 保存成功返回 True。
        """
        existing: Optional[dict] = self._execute(
            f"SELECT {DBConstants.OrganizeSetting.COL_ID} FROM {DBConstants.OrganizeSetting.TABLE_NAME} LIMIT 1",
            is_query=True,
            fetch_one=True
        )
        if existing:
            self._execute(
                f"UPDATE {DBConstants.OrganizeSetting.TABLE_NAME} "
                f"SET {DBConstants.OrganizeSetting.COL_PENDING_DIRS} = ?, "
                f"{DBConstants.OrganizeSetting.COL_ORGANIZED_DIR} = ?, "
                f"{DBConstants.OrganizeSetting.COL_EXTENSIONS} = ?, "
                f"{DBConstants.OrganizeSetting.COL_UPDATE_TIME} = CURRENT_TIMESTAMP "
                f"WHERE {DBConstants.OrganizeSetting.COL_ID} = ?",
                (model.pending_dirs, model.organized_dir, model.extensions, existing['id'])
            )
        else:
            self._execute(
                f"INSERT INTO {DBConstants.OrganizeSetting.TABLE_NAME} "
                f"({DBConstants.OrganizeSetting.COL_PENDING_DIRS}, "
                f"{DBConstants.OrganizeSetting.COL_ORGANIZED_DIR}, "
                f"{DBConstants.OrganizeSetting.COL_EXTENSIONS}) "
                f"VALUES (?, ?, ?)",
                (model.pending_dirs, model.organized_dir, model.extensions)
            )
        return True