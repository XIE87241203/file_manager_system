from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class UserData:
    """
    用途：用户基本信息配置数据类
    """
    username: str = "admin"
    password: str = "admin123"  # 存储为 PBKDF2 加盐哈希（旧版明文在加载时自动迁移）
    language: str = "en"  # 新增：系统语言设置，支持 'zh' 或 'en'
    timezone_offset_minutes: int = 480  # 系统时区偏移（分钟），默认东八区（北京时间 UTC+08:00）
    login_max_attempts: int = 3  # 同一 IP 连续登录失败达到此次数后触发锁定，最小为 1
    login_lockout_minutes: int = 5  # 触发锁定后的禁止登录时长（分钟），最小为 1

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
    quick_view_thumbnail: bool = False
    auto_refresh_enabled: bool = False  # 是否启用自动刷新
    auto_refresh_time: str = "04:00"  # 自动刷新时间 (HH:mm)
    auto_duplicate_check_enabled: bool = False  # 自动刷新完成后是否执行自动新增查重

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
    video_max_frames: int = 60  # 单个视频最大抽帧数量（按采样方向截取前 N 帧，保持锚点对齐），-1 表示不限

@dataclass
class FileNameEntrySettings:
    """
    用途：文件录入管理相关配置数据类
    """
    file_name_link_prefix: str = ""

@dataclass
class AlbumSettings:
    """
    用途：相册模块相关配置数据类
    """
    # 缩略图存储路径：相对路径以 data 目录为基准（默认 data/thumb），也支持绝对路径
    thumbnail_dir: str = "thumb"
    # 缩略图最大边长（像素）：全系统统一配置，所有仓库共享同一尺寸与内容缓存
    thumbnail_size: int = 256
    # 开启后，建立索引发现新增图片/视频时会加入缩略图生成队列，不补处理已有文件
    auto_thumbnail_generation: bool = False
    # 开启后，新建索引发现的新增图片会自动去重加入人脸识别队列
    auto_face_recognition: bool = False


@dataclass
class LogManagementSettings:
    """
    用途：日志管理相关配置数据类
    """
    # 日志保留天数（按系统时区自然日计算）；None 表示永久保留，不自动清理
    retention_days: Optional[int] = 30


@dataclass
class AppConfig:
    """
    用途：系统全局配置汇总数据类
    """
    user_data: UserData = field(default_factory=UserData)
    file_repository: FileRepositorySettings = field(default_factory=FileRepositorySettings)
    duplicate_check: DuplicateCheckSettings = field(default_factory=DuplicateCheckSettings)
    file_name_entry: FileNameEntrySettings = field(default_factory=FileNameEntrySettings)
    album: AlbumSettings = field(default_factory=AlbumSettings)
    log_management: LogManagementSettings = field(default_factory=LogManagementSettings)
