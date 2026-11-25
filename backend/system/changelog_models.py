from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ChangelogEntryResult:
    """
    用途说明：单个版本的更新日志 API 返回数据类。
    字段说明：
        version (str): 版本号。
        date (str): 发布日期，格式为 YYYY-MM-DD。
        highlights (List[str]): 按重要程度排序的主要更新内容。
        rebuild_index_notice (Optional[str]): 该版本需要重建索引或补全索引信息的提示。
    """
    version: str = ''
    date: str = ''
    highlights: List[str] = field(default_factory=list)
    rebuild_index_notice: Optional[str] = None


@dataclass(frozen=True)
class ChangelogResult:
    """
    用途说明：首页更新日志弹窗的 API 返回数据类。
    字段说明：
        current_version (str): 当前程序版本号。
        seen_version (Optional[str]): 当前用户已读版本号，无记录时为 None。
        auto_show (bool): 是否应在首页自动弹出。
        entries (List[ChangelogEntryResult]): 按版本从新到旧排列的更新日志。
    """
    current_version: str = ''
    seen_version: Optional[str] = None
    auto_show: bool = False
    entries: List[ChangelogEntryResult] = field(default_factory=list)
