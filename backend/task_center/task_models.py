from dataclasses import dataclass, field
from typing import List


@dataclass
class CurrentTaskInfo:
    """
    用途说明：统一当前任务入口的单个任务返回模型。
    字段说明：
        key (str): 任务类型标识，供前端选择名称图标和控制接口分发。
        repo_id (int): 任务所属仓库 ID。
        repo_name (str): 任务所属仓库展示名称。
        status (str): processing / paused。
        current (int): 当前已完成数量；无法统计时为 0。
        total (int): 任务总数量；无法统计时为 0。
        remaining (int): 剩余数量；无法统计时为 0。
        message (str): 对应业务页面使用的进度文案。
        can_pause (bool): 当前用户是否可暂停。
        can_resume (bool): 当前用户是否可恢复。
        can_stop (bool): 当前用户是否可停止。
    """
    key: str = ''
    repo_id: int = 0
    repo_name: str = ''
    status: str = 'processing'
    current: int = 0
    total: int = 0
    remaining: int = 0
    message: str = ''
    can_pause: bool = False
    can_resume: bool = False
    can_stop: bool = False


@dataclass
class CurrentTaskListResult:
    """
    用途说明：统一当前任务列表返回模型。
    字段说明：tasks 为当前用户可见仓库中的运行或暂停任务；count 为任务数量。
    """
    tasks: List[CurrentTaskInfo] = field(default_factory=list)
    count: int = 0
