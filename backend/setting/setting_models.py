from dataclasses import dataclass, field
from typing import List

@dataclass
class UserData:
    """
    用途：用户基本信息配置数据类
    """
    username: str = "admin"
    password: str = "admin123"

@dataclass
class FileRepositorySettings:
    """
    用途：文件仓库相关配置数据类
    """
    directories: List[str] = field(default_factory=list)
    scan_suffixes: List[str] = field(default_factory=lambda: ["*"])
    search_replace_chars: List[str] = field(default_factory=list)
    ignore_filenames: List[str] = field(default_factory=list)
    ignore_filenames_case_insensitive: bool = True
    ignore_paths: List[str] = field(default_factory=list)
    ignore_paths_case_insensitive: bool = True
    thumbnail_size: int = 256
    quick_view_thumbnail: bool = False
    auto_refresh_enabled: bool = False  # 是否启用自动刷新
    auto_refresh_time: str = "04:00"  # 自动刷新时间 (HH:mm)

@dataclass
class DuplicateCheckSettings:
    """
    用途：文件查重算法相关参数配置数据类
    """
    image_threshold: int = 8
    video_frame_similar_distance: int = 5
    video_frame_similarity_rate: float = 0.7
    video_interval_seconds: int = 30
    video_max_duration_diff_ratio: float = 0.6
    video_backwards: bool = False  # 是否从视频结尾倒序生成特征

@dataclass
class FileNameEntrySettings:
    """
    用途：文件录入管理相关配置数据类
    """
    file_name_link_prefix: str = ""

@dataclass
class AppConfig:
    """
    用途：系统全局配置汇总数据类
    """
    user_data: UserData = field(default_factory=UserData)
    file_repository: FileRepositorySettings = field(default_factory=FileRepositorySettings)
    duplicate_check: DuplicateCheckSettings = field(default_factory=DuplicateCheckSettings)
    file_name_entry: FileNameEntrySettings = field(default_factory=FileNameEntrySettings)
