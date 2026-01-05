import os
import hashlib
from backend.common.log_utils import LogUtils

class Utils:
    """
    用途：后端通用工具类
    """

    @staticmethod
    def get_runtime_path() -> str:
        """
        用途：获取程序运行时的 data 目录路径。改为基于项目根目录的绝对路径，确保 Docker 兼容性。
        入参说明：无
        返回值说明：str - 返回项目根目录下的 data 目录的绝对路径
        """
        # 获取当前文件所在目录的父目录的父目录（即项目根目录 /app）
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        data_path = os.path.join(base_path, "data")

        if not os.path.exists(data_path):
            # 使用 exist_ok=True 避免并发创建时的异常
            os.makedirs(data_path, exist_ok=True)

        return data_path

    @staticmethod
    def calculate_md5(file_path: str) -> str:
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
