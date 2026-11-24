from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional

# 默认时区偏移（分钟）：东八区（北京时间）
DEFAULT_TIMEZONE_OFFSET_MINUTES: int = 480
# 允许的时区偏移范围（分钟）：UTC-12:00 至 UTC+14:00
MIN_TIMEZONE_OFFSET_MINUTES: int = -720
MAX_TIMEZONE_OFFSET_MINUTES: int = 840
# 系统时间统一格式
DEFAULT_TIME_FORMAT: str = '%Y-%m-%d %H:%M:%S'


class TimezoneUtils:
    """
    用途说明：系统时区工具类，依据系统设置中的时区偏移统一生成/转换系统时间（日志、查重时间等）。
    说明：数据库与业务内部仍沿用原有存储时区，本工具类仅负责按配置的时区输出展示时间。
    """

    @staticmethod
    def get_offset_minutes() -> int:
        """
        用途说明：读取系统设置中的时区偏移（分钟），非法或读取失败时回退默认东八区。
        入参说明：无
        返回值说明：int - 时区偏移分钟数，例如 480 表示 UTC+08:00。
        """
        try:
            # 延迟导入，避免与设置服务模块形成循环依赖
            from backend.setting.setting_service import settingService
            value = settingService.get_config().user_data.timezone_offset_minutes
        except Exception:
            return DEFAULT_TIMEZONE_OFFSET_MINUTES

        if isinstance(value, bool) or not isinstance(value, int):
            return DEFAULT_TIMEZONE_OFFSET_MINUTES
        if value < MIN_TIMEZONE_OFFSET_MINUTES or value > MAX_TIMEZONE_OFFSET_MINUTES:
            return DEFAULT_TIMEZONE_OFFSET_MINUTES
        return value

    @classmethod
    def get_tzinfo(cls) -> tzinfo:
        """
        用途说明：根据配置的时区偏移生成固定偏移时区对象。
        入参说明：无
        返回值说明：tzinfo - 固定偏移时区对象。
        """
        return timezone(timedelta(minutes=cls.get_offset_minutes()))

    @classmethod
    def from_timestamp(cls, timestamp: float) -> datetime:
        """
        用途说明：将 Unix 时间戳转换为配置时区下的带时区 datetime。
        入参说明：timestamp (float) - Unix 时间戳（秒）。
        返回值说明：datetime - 配置时区下的时间对象。
        """
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(cls.get_tzinfo())

    @classmethod
    def now(cls) -> datetime:
        """
        用途说明：获取配置时区下的当前时间。
        入参说明：无
        返回值说明：datetime - 配置时区下的当前时间（带时区）。
        """
        return cls.from_timestamp(datetime.now(timezone.utc).timestamp())

    @classmethod
    def now_text(cls, fmt: str = DEFAULT_TIME_FORMAT) -> str:
        """
        用途说明：获取配置时区下格式化后的当前时间字符串。
        入参说明：fmt (str) - 时间格式，默认 YYYY-MM-DD HH:MM:SS。
        返回值说明：str - 格式化后的时间字符串。
        """
        return cls.now().strftime(fmt)

    @classmethod
    def local_to_target(cls, raw: Optional[str], fmt: str = DEFAULT_TIME_FORMAT) -> Optional[str]:
        """
        用途说明：将服务器本地时区的时间字符串转换为配置时区的时间字符串（用于既有本地时间数据的展示）。
        入参说明：
            raw (Optional[str]) - 服务器本地时区时间字符串。
            fmt (str) - 解析与输出格式，默认 YYYY-MM-DD HH:MM:SS。
        返回值说明：Optional[str] - 配置时区下的时间字符串；空值原样返回，无法解析时原样返回。
        """
        if not raw:
            return raw
        try:
            local_dt: datetime = datetime.strptime(raw, fmt)
            return local_dt.astimezone(cls.get_tzinfo()).strftime(fmt)
        except (TypeError, ValueError):
            return raw

    @classmethod
    def utc_to_target(cls, raw: Optional[str], fmt: str = DEFAULT_TIME_FORMAT) -> str:
        """
        用途说明：将数据库 UTC 时间字符串转换为配置时区的时间字符串（用于数据库 CURRENT_TIMESTAMP 数据）。
        入参说明：
            raw (Optional[str]) - 数据库 UTC 时间字符串。
            fmt (str) - 解析与输出格式，默认 YYYY-MM-DD HH:MM:SS。
        返回值说明：str - 配置时区下的时间字符串；空值返回空串，无法解析时原样返回。
        """
        if not raw:
            return ''
        try:
            utc_dt: datetime = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return utc_dt.astimezone(cls.get_tzinfo()).strftime(fmt)
        except (TypeError, ValueError):
            return raw