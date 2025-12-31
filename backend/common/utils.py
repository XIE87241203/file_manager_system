import os
import hashlib
from backend.common.log_utils import LogUtils

class Utils:
    """
    用途：后端通用工具类
    """
    
    @staticmethod
    def get_runtime_path():
        """
        用途：获取程序运行时的根路径
        入参说明：无
        返回值说明：返回当前工作目录的绝对路径
        """
        return os.getcwd()

    @staticmethod
    def calculate_md5(file_path):
        """
        用途：计算指定文件的 MD5 哈希值
        入参说明：file_path (str) - 文件的绝对路径
        返回值说明：str - 文件的 MD5 十六进制字符串；如果读取失败则返回空字符串
        """
        hash_md5 = hashlib.md5()
        try:
            if not os.path.exists(file_path):
                LogUtils.error(f"文件不存在，无法计算 MD5: {file_path}")
                return ""
                
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            LogUtils.error(f"计算文件 MD5 失败: {file_path}, 错误: {e}")
            return ""
