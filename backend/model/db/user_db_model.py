from dataclasses import dataclass
from typing import Optional


@dataclass
class UserDBModel:
    """
    用途：用户账户数据库模型，与主库 users 表列一一对应。
    说明：password_hash 存储 PBKDF2 加盐慢哈希，绝不存明文；is_admin 以 1/0 表示是否管理员。
    """
    username: str = ''
    password_hash: str = ''
    is_admin: int = 0
    create_time: Optional[str] = None
    update_time: Optional[str] = None
    id: Optional[int] = None