import fnmatch
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.timezone_utils import TimezoneUtils
from backend.common.utils import Utils


@dataclass
class LogDirectoryInfo:
    """
    用途说明：日志目录统计信息数据类
    """
    size_bytes: int = 0
    file_count: int = 0


@dataclass
class LogCleanupResultInfo:
    """
    用途说明：日志清理结果数据类
    """
    retention_days: Optional[int] = None
    deleted_count: int = 0
    freed_bytes: int = 0


class SystemService:
    """
    用途说明：系统管理服务类，负责日志读取、日志目录统计与过期日志清理等系统级操作。
    """

    # 日志文件命名格式：YYYYMMDD.log（日期按系统设置时区生成）
    LOG_FILE_PATTERN = re.compile(r'^(\d{8})\.log$')

    @staticmethod
    def get_log_dir() -> str:
        """
        用途说明：获取运行日志目录的绝对路径。
        入参说明：无
        返回值说明：str - 日志目录路径。
        """
        return os.path.join(Utils.get_runtime_path(), 'log')

    @staticmethod
    def get_latest_logs(line_count: int = 200, keyword: Optional[str] = None, level: Optional[str] = None, exclude_api: bool = False) -> List[str]:
        """
        用途说明：读取系统设置时区下当天的日志文件，并根据关键词、等级、API过滤标识进行过滤，返回末尾指定行数的内容。
        入参说明：
            line_count (int): 需要返回的末尾行数。
            keyword (str, 可选): 搜索关键词，支持 * 通配符。
            level (str, 可选): 日志等级（INFO/DEBUG/WARN/ERROR/ALL）。
            exclude_api (bool): 是否过滤 API 请求相关的日志，默认为 False。
        返回值说明：List[str]: 过滤后的日志行列表。
        """
        log_dir: str = os.path.join(Utils.get_runtime_path(), 'log')
        log_filename: str = TimezoneUtils.now_text('%Y%m%d') + ".log"
        log_path: str = os.path.join(log_dir, log_filename)

        if not os.path.exists(log_path):
            now_time: str = TimezoneUtils.now_text()
            return [t('sys_log_not_found', time=now_time, filename=log_filename)]

        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                all_lines: List[str] = f.readlines()
            
            filtered_lines: List[str] = all_lines
            
            # 1. 过滤 API 日志 (通常包含 /api/ 路径的 INFO 日志)
            if exclude_api:
                api_start_text = t('log_api_start')
                filtered_lines = [line for line in filtered_lines if api_start_text not in line]

            # 2. 按等级过滤
            if level and level.upper() != 'ALL':
                level_tag: str = f" - {level.upper()} - "
                filtered_lines = [line for line in filtered_lines if level_tag in line]
            
            # 3. 按关键词过滤（支持通配符）
            if keyword:
                # 如果没有通配符，则默认为包含匹配
                search_pattern: str = keyword if ('*' in keyword or '?' in keyword) else f"*{keyword}*"
                filtered_lines = [line for line in filtered_lines if fnmatch.fnmatch(line, search_pattern)]
            
            return filtered_lines[-line_count:] if len(filtered_lines) > line_count else filtered_lines
            
        except Exception as e:
            return [t('sys_log_read_failed', error=str(e))]

    @staticmethod
    def get_available_log_files() -> List[str]:
        """
        用途说明：获取当前系统中存在的所有日志文件列表。
        返回值说明：List[str]: 文件名列表。
        """
        log_dir: str = os.path.join(Utils.get_runtime_path(), 'log')
        if not os.path.exists(log_dir):
            return []
        files: List[str] = [f for f in os.listdir(log_dir) if f.endswith('.log')]
        files.sort(reverse=True)
        return files

    @classmethod
    def get_log_dir_size(cls) -> LogDirectoryInfo:
        """
        用途说明：统计当前日志目录的总大小与文件数量（仅遍历目录元数据，不读取文件内容）。
        入参说明：无
        返回值说明：LogDirectoryInfo - 包含 size_bytes（总字节数）与 file_count（文件数量）。
        """
        info = LogDirectoryInfo()
        log_dir: str = cls.get_log_dir()
        if not os.path.isdir(log_dir):
            return info

        try:
            with os.scandir(log_dir) as entries:
                for entry in entries:
                    try:
                        if not entry.is_file():
                            continue
                        info.file_count += 1
                        info.size_bytes += entry.stat().st_size
                    except OSError as e:
                        LogUtils.error(t('sys_log_dir_size_error', error=str(e)))
        except OSError as e:
            LogUtils.error(t('sys_log_dir_size_error', error=str(e)))

        return info

    @classmethod
    def cleanup_expired_logs(cls, retention_days: Optional[int]) -> LogCleanupResultInfo:
        """
        用途说明：按保留天数清理过期日志文件，仅处理 YYYYMMDD.log 命名格式的文件。
        入参说明：retention_days (Optional[int]) - 保留天数，None 表示永久保留不清理。
        返回值说明：LogCleanupResultInfo - 包含实际删除的文件数量与释放的字节数。
        """
        result = LogCleanupResultInfo(retention_days=retention_days)
        log_dir: str = cls.get_log_dir()
        if not os.path.isdir(log_dir):
            return result

        if retention_days is None:
            LogUtils.info(t('sys_log_cleanup_permanent'))
            return result

        # 按系统时区的自然日计算保留起点：保留从当天往前共 retention_days 天（含当天）
        today: date = TimezoneUtils.now().date()
        keep_from: date = today - timedelta(days=retention_days - 1)

        try:
            with os.scandir(log_dir) as entries:
                for entry in entries:
                    match = cls.LOG_FILE_PATTERN.match(entry.name)
                    if not match:
                        continue
                    try:
                        if not entry.is_file():
                            continue
                        file_date: date = datetime.strptime(match.group(1), '%Y%m%d').date()
                    except (OSError, ValueError):
                        continue
                    if file_date >= keep_from:
                        continue

                    try:
                        file_size: int = entry.stat().st_size
                        os.remove(entry.path)
                        result.deleted_count += 1
                        result.freed_bytes += file_size
                    except OSError as e:
                        LogUtils.error(t('sys_log_cleanup_file_error',
                                         filename=entry.name, error=str(e)))
        except OSError as e:
            LogUtils.error(t('sys_log_cleanup_error', error=str(e)))

        LogUtils.info(t('sys_log_cleanup_done',
                        days=retention_days,
                        deleted=result.deleted_count,
                        freed=result.freed_bytes))
        return result
