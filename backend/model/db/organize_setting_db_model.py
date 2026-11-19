from dataclasses import dataclass
from typing import Optional


@dataclass
class OrganizeSettingDBModel:
    """
    用途：整理模块设置数据库模型，与 organize_settings 表列一一对应。
    说明：pending_dirs 与 extensions 在数据库中以 JSON 数组文本形式存储，
    由服务层负责与列表结构之间的序列化/反序列化。
    """
    pending_dirs: str = '[]'
    organized_dir: str = ''
    extensions: str = '[]'
    rename_script_path: str = ''
    update_time: Optional[str] = None
    id: Optional[int] = None