from contextvars import ContextVar

# 默认仓库 ID（项目初始化时创建，承载历史数据）
DEFAULT_REPO_ID: int = 1

# 当前请求/任务上下文的仓库 ID，默认指向默认仓库
_current_repo_id: ContextVar[int] = ContextVar('current_repo_id', default=DEFAULT_REPO_ID)


def set_current_repo_id(repo_id: int) -> None:
    """
    用途说明：设置当前上下文的仓库 ID，供数据库路由与配置读取使用。
    入参说明：repo_id (int): 目标仓库 ID。
    返回值说明：无
    """
    _current_repo_id.set(repo_id)


def get_current_repo_id() -> int:
    """
    用途说明：获取当前上下文的仓库 ID。
    入参说明：无
    返回值说明：int - 当前仓库 ID，未显式设置时返回默认仓库 ID。
    """
    return _current_repo_id.get()