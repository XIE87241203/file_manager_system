from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UserResult:
    """
    用途：用户账户的 API 返回数据类（不含密码哈希，避免敏感信息泄露）。
    字段说明：
        id (int): 用户唯一标识。
        username (str): 登录名。
        is_admin (bool): 是否管理员。
        create_time (Optional[str]): 创建时间。
        last_login (Optional[str]): 最后一次登录时间（无登录记录时为 None）。
    """
    id: int = 0
    username: str = ''
    is_admin: bool = False
    create_time: Optional[str] = None
    last_login: Optional[str] = None


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


@dataclass
class LoginHistoryResult:
    """
    用途：单条登录历史的 API 返回数据类。
    字段说明：
        login_time (Optional[str]): 登录成功时间。
        ip (str): 登录来源 IP。
    """
    login_time: Optional[str] = None
    ip: str = ''


@dataclass
class LoginHistoryPageResult:
    """
    用途：登录历史分页查询的 API 返回数据类。
    字段说明：
        total (int): 该用户登录历史总条数。
        page (int): 当前页码（从 1 开始）。
        page_size (int): 每页条数。
        list (List[LoginHistoryResult]): 当前页登录历史列表（按时间倒序）。
    """
    total: int = 0
    page: int = 1
    page_size: int = 10
    list: List[LoginHistoryResult] = field(default_factory=list)