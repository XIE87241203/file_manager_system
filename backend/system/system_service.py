import fnmatch
import os
from datetime import datetime
from typing import List, Optional

from backend.common.log_utils import LogUtils
from backend.common.utils import Utils


class SystemService:
    """
    用途说明：系统管理服务类，负责日志读取等系统级操作。
    """

    @staticmethod
    def get_latest_logs(line_count: int = 200, keyword: Optional[str] = None, level: Optional[str] = None, exclude_api: bool = False) -> List[str]:
        """
        用途说明：读取当天的日志文件，并根据关键词、等级、API过滤标识进行过滤，返回末尾指定行数的内容。
        入参说明：
            line_count (int): 需要返回的末尾行数。
            keyword (str, 可选): 搜索关键词，支持 * 通配符。
            level (str, 可选): 日志等级（INFO/DEBUG/WARN/ERROR/ALL）。
            exclude_api (bool): 是否过滤 API 请求相关的日志，默认为 False。
        返回值说明：List[str]: 过滤后的日志行列表。
        """
        log_dir: str = os.path.join(Utils.get_runtime_path(), 'log')
        log_filename: str = datetime.now().strftime('%Y%m%d') + ".log"
        log_path: str = os.path.join(log_dir, log_filename)

        if not os.path.exists(log_path):
            return [f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 日志文件不存在: {log_filename}"]

        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                all_lines: List[str] = f.readlines()
            
            filtered_lines: List[str] = all_lines
            
            # 1. 过滤 API 日志 (通常包含 /api/ 路径的 INFO 日志)
            if exclude_api:
                filtered_lines = [line for line in filtered_lines if LogUtils.API_START not in line]

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
            return [f"读取日志失败: {str(e)}"]

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
