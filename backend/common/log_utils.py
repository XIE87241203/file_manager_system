import logging
import sys
import os
from datetime import datetime

class LogUtils:
    """
    用途：后端统一日志工具类，提供 info, debug, error 三种等级的日志输出，并同步写入按天生成的日志文件。
    """
    _logger = None

    @classmethod
    def init(cls, level=logging.INFO):
        """
        用途：初始化日志配置，设置控制台输出和文件输出。
        入参说明：
            - level: 日志级别，默认为 logging.INFO。
        返回值说明：无。
        """
        if cls._logger is None:
            cls._logger = logging.getLogger("file_manager_system")
            cls._logger.setLevel(level)
            
            # 1. 确保日志目录存在 (直接使用 os.getcwd() 避免循环导入 Utils)
            runtime_path = os.path.join(os.getcwd(), "data")
            log_dir = os.path.join(runtime_path, 'log')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # 2. 构造日志文件路径 (yyyyMMdd.log)
            log_filename = datetime.now().strftime('%Y%m%d') + ".log"
            log_path = os.path.join(log_dir, log_filename)
            
            # 3. 定义日志格式：yyyy/MM/dd-HH:mm:ss:SSS
            formatter = logging.Formatter(
                fmt='%(asctime)s:%(msecs)03d - %(levelname)s - %(message)s',
                datefmt='%Y/%m/%d-%H:%M:%S'
            )
            
            # 4. 创建控制台处理器
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            cls._logger.addHandler(console_handler)
            
            # 5. 创建文件处理器 (追加模式)
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            cls._logger.addHandler(file_handler)

    @classmethod
    def info(cls, message):
        """
        用途：打印并记录 INFO 级别日志。
        """
        if cls._logger:
            cls._logger.info(message)
        else:
            print(f"INFO: {message}")

    @classmethod
    def debug(cls, message):
        """
        用途：打印并记录 DEBUG 级别日志。
        """
        if cls._logger:
            cls._logger.debug(message)
        else:
            print(f"DEBUG: {message}")

    @classmethod
    def error(cls, message):
        """
        用途：打印并记录 ERROR 级别日志。
        """
        if cls._logger:
            cls._logger.error(message)
        else:
            print(f"ERROR: {message}")
