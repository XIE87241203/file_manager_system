import os

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
