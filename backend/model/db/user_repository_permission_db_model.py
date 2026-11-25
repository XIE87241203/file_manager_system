from dataclasses import dataclass


@dataclass
class UserRepositoryPermissionDBModel:
    """
    用途：系统使用者与仓库授权关系的数据库模型，与主库权限表列一一对应。
    说明：permission 仅允许 admin（仓库管理员）或 member（仓库成员）。
    """
    user_id: int = 0
    repo_id: int = 0
    permission: str = ''
