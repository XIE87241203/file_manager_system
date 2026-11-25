import os
from typing import List, Optional

from backend.common.utils import Utils
from backend.setting.setting_service import settingService


class ThumbnailPathUtils:
    """
    用途说明：缩略图存储路径统一解析工具。
    设计说明：
        1. 相册与文件管理共用同一套缩略图文件（以文件 MD5 命名），因此目录解析集中在此处；
        2. 配置项 album.thumbnail_dir 为相对路径时以 data 目录为基准，绝对路径则直接使用；
        3. 兼容历史版本固定的 data/cache/thumbnail 目录，避免升级后旧缩略图无法访问。
    """

    DEFAULT_DIR_NAME: str = "thumb"
    LEGACY_DIR_NAME: str = os.path.join("cache", "thumbnail")

    @staticmethod
    def get_configured_dir() -> str:
        """
        用途说明：读取配置中的缩略图存储路径原始值。
        入参说明：无
        返回值说明：str - 配置值，空值或非法时返回默认目录名 thumb。
        """
        try:
            raw_value: str = settingService.get_config().album.thumbnail_dir
        except Exception:
            raw_value = ""
        return (raw_value or "").strip() or ThumbnailPathUtils.DEFAULT_DIR_NAME

    @staticmethod
    def get_thumbnail_dir() -> str:
        """
        用途说明：将配置值解析为缩略图目录的绝对路径。
        入参说明：无
        返回值说明：str - 缩略图目录绝对路径（不保证目录已存在）。
        """
        configured: str = ThumbnailPathUtils.get_configured_dir()
        if os.path.isabs(configured):
            return os.path.abspath(configured)
        return os.path.abspath(os.path.join(Utils.get_runtime_path(), configured))

    @staticmethod
    def ensure_thumbnail_dir() -> str:
        """
        用途说明：确保当前配置的缩略图目录存在并返回其绝对路径。
        入参说明：无
        返回值说明：str - 缩略图目录绝对路径。
        """
        thumbnail_dir: str = ThumbnailPathUtils.get_thumbnail_dir()
        os.makedirs(thumbnail_dir, exist_ok=True)
        return thumbnail_dir

    @staticmethod
    def get_legacy_dir() -> str:
        """
        用途说明：获取历史版本使用的缩略图目录（data/cache/thumbnail）。
        入参说明：无
        返回值说明：str - 历史缩略图目录绝对路径。
        """
        return os.path.abspath(os.path.join(Utils.get_runtime_path(), ThumbnailPathUtils.LEGACY_DIR_NAME))

    @staticmethod
    def get_known_dirs() -> List[str]:
        """
        用途说明：获取当前需要维护的缩略图目录列表（当前配置目录 + 历史目录，自动去重）。
        入参说明：无
        返回值说明：List[str] - 缩略图目录绝对路径列表。
        """
        dirs: List[str] = [ThumbnailPathUtils.get_thumbnail_dir()]
        legacy_dir: str = ThumbnailPathUtils.get_legacy_dir()
        if os.path.normcase(legacy_dir) not in {os.path.normcase(item) for item in dirs}:
            dirs.append(legacy_dir)
        return dirs

    @staticmethod
    def get_thumbnail_file(file_md5: str) -> str:
        """
        用途说明：根据文件 MD5 生成缩略图文件绝对路径（同内容文件共享同一缩略图）。
        入参说明：file_md5 (str) - 文件 MD5 哈希值。
        返回值说明：str - 缩略图文件绝对路径。
        """
        return os.path.join(ThumbnailPathUtils.ensure_thumbnail_dir(), f"{file_md5}.jpg")

    @staticmethod
    def get_existing_thumbnail(file_md5: str) -> Optional[str]:
        """
        用途说明：检查指定 MD5 的缩略图是否已存在于当前配置目录。
        入参说明：file_md5 (str) - 文件 MD5 哈希值。
        返回值说明：Optional[str] - 存在时返回缩略图绝对路径，否则返回 None。
        """
        if not file_md5:
            return None
        thumb_path: str = os.path.join(ThumbnailPathUtils.ensure_thumbnail_dir(), f"{file_md5}.jpg")
        return thumb_path if os.path.exists(thumb_path) else None

    @staticmethod
    def is_allowed_thumbnail_path(path: str) -> bool:
        """
        用途说明：校验请求的缩略图路径是否位于允许的缩略图目录内（防止路径穿越）。
        入参说明：path (str) - 请求的缩略图文件路径。
        返回值说明：bool - 位于当前目录或历史目录内返回 True，否则返回 False。
        """
        if not path:
            return False
        requested: str = os.path.normcase(os.path.abspath(path))
        for allowed_dir in ThumbnailPathUtils.get_known_dirs():
            normalized_dir: str = os.path.normcase(os.path.abspath(allowed_dir))
            if requested == normalized_dir or requested.startswith(normalized_dir + os.sep):
                return True
        return False