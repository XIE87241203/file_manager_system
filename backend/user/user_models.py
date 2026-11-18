from dataclasses import dataclass
from typing import Optional


@dataclass
class UserResult:
    """
    用途：用户账户的 API 返回数据类（不含密码哈希，避免敏感信息泄露）。
    字段说明：
        id (int): 用户唯一标识。
        username (str): 登录名。
        is_admin (bool): 是否管理员。
        create_time (Optional[str]): 创建时间。
    """
    id: int = 0
    username: str = ''
    is_admin: bool = False
    create_time: Optional[str] = None


@dataclass
class CurrentUserResult:
    """
    用途：当前登录用户信息的 API 返回数据类，供前端判断是否展示用户管理入口。
    字段说明：
        username (str): 当前登录名。
        is_admin (bool): 当前用户是否管理员。
    """
    username: str = ''
    is_admin: bool = False