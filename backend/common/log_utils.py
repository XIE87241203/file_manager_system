import logging
import os
import sys
from datetime import datetime
from typing import Optional

# 定义自定义等级：API 设为 25，位于 INFO(20) 和 WARNING(30) 之间
LOG_LEVEL_API: int = 25
logging.addLevelName(LOG_LEVEL_API, "API")

class LogUtils:
    """
    用途说明：后端统一日志工具类，提供 DEBUG, INFO, API, ERROR 四种等级。
    不再暴露 WARNING 等级，API 等级专门用于记录接口请求。
    """
    _logger: Optional[logging.Logger] = None

    API_START = "接口请求"

    @staticmethod
    def get_log_filename(date_str: str) -> str:
        """
        用途说明：根据日期字符串生成日志文件名。
        入参说明：date_str (str): %Y%m%d 格式的日期字符串。
        返回值说明：str: 生成的日志文件名（例如 "20231027.log"）。
        """
        return f"{date_str}.log"

    @classmethod
    def init(cls, level: int = logging.DEBUG) -> None:
        """
        用途说明：初始化日志配置。
        入参说明：level (int): 日志级别。
        """
        if cls._logger is None:
            cls._logger = logging.getLogger("file_manager_system")
            cls._logger.setLevel(level)
            
            runtime_path: str = os.path.join(os.getcwd(), "data")
            log_dir: str = os.path.join(runtime_path, 'log')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # 使用静态方法获取文件名
            date_str: str = datetime.now().strftime('%Y%m%d')
            log_filename: str = cls.get_log_filename(date_str)
            log_path: str = os.path.join(log_dir, log_filename)
            
            formatter: logging.Formatter = logging.Formatter(
                fmt='%(asctime)s:%(msecs)03d - %(levelname)s - %(message)s',
                datefmt='%Y/%m/%d-%H:%M:%S'
            )
            
            console_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            cls._logger.addHandler(console_handler)
            
            file_handler: logging.FileHandler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            cls._logger.addHandler(file_handler)

    @classmethod
    def set_level(cls, debug_api_enabled: bool) -> None:
        """
        用途说明：动态调整日志显示级别。如果关闭 API 日志，则级别调高至高于 API 的级别（如 ERROR）。
        入参说明：debug_api_enabled (bool): 是否启用 API 及以下级别的日志。
        """
        if cls._logger:
            # 如果不开启，则只显示 ERROR；如果开启，则显示 DEBUG 及其以上所有
            level = logging.DEBUG if debug_api_enabled else logging.ERROR
            cls._logger.setLevel(level)

    @classmethod
    def info(cls, message: str) -> None:
        """用途说明：打印 INFO 级别日志。"""
        if cls._logger: cls._logger.info(message)

    @classmethod
    def debug(cls, message: str) -> None:
        """用途说明：打印 DEBUG 级别日志。"""
        if cls._logger: cls._logger.debug(message)

    @classmethod
    def api(cls, message: str) -> None:
        """用途说明：打印 API 级别日志（自定义等级 25）。"""
        if cls._logger: cls._logger.log(LOG_LEVEL_API, f"{cls.API_START} - {message}")

    @classmethod
    def error(cls, message: str) -> None:
        """用途说明：打印 ERROR 级别日志。"""
        if cls._logger: cls._logger.error(message)
