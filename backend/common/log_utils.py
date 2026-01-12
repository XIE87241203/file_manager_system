import logging
import os
import sys
from datetime import datetime
from typing import Any, Optional


class LogUtils:
    LOG_API_ENABLE: bool = False

    """
    用途：后端统一日志工具类，提供 info, debug, error 三种等级的日志输出，并同步写入按天生成的日志文件。
    """
    _logger: Optional[logging.Logger] = None

    @classmethod
    def init(cls, level: int = logging.INFO) -> None:
        """
        用途：初始化日志配置，设置控制台输出和文件输出。
        入参说明：
            - level: int, 日志级别，默认为 logging.INFO。
        返回值说明：无。
        """
        if cls._logger is None:
            cls._logger = logging.getLogger("file_manager_system")
            cls._logger.setLevel(level)
            
            # 1. 确保日志目录存在 (直接使用 os.getcwd() 避免循环导入 Utils)
            runtime_path: str = os.path.join(os.getcwd(), "data")
            log_dir: str = os.path.join(runtime_path, 'log')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # 2. 构造日志文件路径 (yyyyMMdd.log)
            log_filename: str = datetime.now().strftime('%Y%m%d') + ".log"
            log_path: str = os.path.join(log_dir, log_filename)
            
            # 3. 定义日志格式：yyyy/MM/dd-HH:mm:ss:SSS
            formatter: logging.Formatter = logging.Formatter(
                fmt='%(asctime)s:%(msecs)03d - %(levelname)s - %(message)s',
                datefmt='%Y/%m/%d-%H:%M:%S'
            )
            
            # 4. 创建控制台处理器
            console_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            cls._logger.addHandler(console_handler)
            
            # 5. 创建文件处理器 (追加模式)
            file_handler: logging.FileHandler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            cls._logger.addHandler(file_handler)

    @classmethod
    def info(cls, message: str) -> None:
        """
        用途：打印并记录 INFO 级别日志。
        入参说明：
            - message: str, 日志信息内容。
        返回值说明：无。
        """
        if cls._logger:
            cls._logger.info(message)
        else:
            print(f"INFO: {message}")

    @classmethod
    def debug(cls, message: str) -> None:
        """
        用途：打印并记录 DEBUG 级别日志。
        入参说明：
            - message: str, 日志信息内容。
        返回值说明：无。
        """
        if cls._logger:
            cls._logger.debug(message)
        else:
            print(f"DEBUG: {message}")

    @classmethod
    def api_response(cls, url: str, status_code: int, data: Any) -> None:
        """
        用途：打印并记录 API 响应日志。
        入参说明：
            - url: str, 请求的 API 路径。
            - status_code: int, HTTP 状态码。
            - data: Any, 返回的数据内容。
        返回值说明：无。
        """
        if not LogUtils.LOG_API_ENABLE :
            return
        message: str = f"API Response [{status_code}] - URL: {url} - Data: {data}"
        cls.info(message)

    @classmethod
    def error(cls, message: str) -> None:
        """
        用途：打印并记录 ERROR 级别日志。
        入参说明：
            - message: str, 日志信息内容。
        返回值说明：无。
        """
        if cls._logger:
            cls._logger.error(message)
        else:
            print(f"ERROR: {message}")
