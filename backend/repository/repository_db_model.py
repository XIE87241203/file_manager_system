from dataclasses import dataclass
from typing import Optional


@dataclass
class RepositoryDBModel:
    """
    用途：repositories 主表对应的数据库模型，存储仓库元数据与独立配置。
    入参说明：
        id (Optional[int]): 仓库主键 ID。
        name (str): 仓库名称（唯一）。
        config (str): 仓库独立配置（FileRepositorySettings 序列化后的 JSON 字符串）。
        db_file (str): 仓库业务库文件相对路径（相对 data 目录）。
        create_time (Optional[str]): 创建时间。
    """
    id: Optional[int] = None
    name: str = ""
    config: str = ""
    db_file: str = ""
    create_time: Optional[str] = None