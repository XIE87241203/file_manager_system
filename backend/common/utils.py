import os
import hashlib
import fnmatch
import re
from typing import Tuple, List
from backend.common.log_utils import LogUtils
from backend.db.db_operations import DBOperations


class Utils:
    """
    用途：后端通用工具类
    """

    @staticmethod
    def get_runtime_path() -> str:
        """
        用途：获取程序运行时的 data 目录路径。
        入参说明：无
        返回值说明：str - 返回项目根目录下的 data 目录的绝对路径
        """
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        data_path = os.path.join(base_path, "data")

        if not os.path.exists(data_path):
            os.makedirs(data_path, exist_ok=True)

        return data_path

    @staticmethod
    def calculate_md5(file_path: str) -> Tuple[str, str]:
        """
        用途：计算指定文件的 MD5 哈希值，并返回路径与哈希的元组。
        入参说明：file_path (str) - 文件的绝对路径
        返回值说明：Tuple[str, str] - (文件绝对路径, MD5 十六进制字符串)；失败则 MD5 为空字符串
        """
        hash_md5 = hashlib.md5()
        try:
            if not os.path.exists(file_path):
                LogUtils.error(f"文件不存在，无法计算 MD5: {file_path}")
                return file_path, ""
                
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return file_path, hash_md5.hexdigest()
        except Exception as e:
            LogUtils.error(f"计算文件 MD5 失败: {file_path}, 错误: {e}")
            return file_path, ""

    @staticmethod
    def should_ignore(file_path: str, 
                      ignore_filenames: List[str], 
                      ignore_paths: List[str],
                      ignore_filenames_case_insensitive: bool = True,
                      ignore_paths_case_insensitive: bool = True) -> bool:
        """
        用途：根据忽略规则判断文件是否应被忽略
        入参说明：
            file_path (str): 文件完整路径
            ignore_filenames (List[str]): 忽略的文件名列表（支持通配符）
            ignore_paths (List[str]): 忽略的路径包含字符串列表（支持通配符）
            ignore_filenames_case_insensitive (bool): 文件名忽略是否忽略大小写
            ignore_paths_case_insensitive (bool): 路径忽略是否忽略大小写
        返回值说明：bool - True 表示应忽略，False 表示不忽略
        """
        filename = os.path.basename(file_path)
        
        # 1. 检查文件名忽略规则
        for pattern in ignore_filenames:
            if ignore_filenames_case_insensitive:
                if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                    return True
            else:
                if fnmatch.fnmatchcase(filename, pattern):
                    return True
        
        # 2. 检查路径忽略规则
        for pattern in ignore_paths:
            # 如果模式中不包含通配符，则默认为包含匹配，即前后加 *
            search_pattern = pattern if ('*' in pattern or '?' in pattern) else f"*{pattern}*"
            
            if ignore_paths_case_insensitive:
                if fnmatch.fnmatch(file_path.lower(), search_pattern.lower()):
                    return True
            else:
                if fnmatch.fnmatchcase(file_path, search_pattern):
                    return True
                
        return False

    @staticmethod
    def get_filename(file_path: str) -> str:
        """
        用途：从文件路径中获取文件名（包括后缀）。
        入参说明：file_path (str) - 文件的路径。
        返回值说明：str - 文件名（包括后缀）。
        """
        return os.path.basename(file_path)

    @staticmethod
    def delete_file(file_path: str) -> Tuple[bool, str]:
        """
        用途：删除物理文件并从数据库索引及重复结果中移除，同时删除对应的缩略图文件。
        入参说明：
            file_path (str) - 文件的绝对路径。
        返回值说明：Tuple[bool, str] - (是否成功, 详细说明)。
        """
        try:
            # 1. 获取并删除缩略图文件
            file_info = DBOperations.get_file_by_path(file_path)
            if file_info and file_info.thumbnail_path:
                Utils.delete_os_file(file_info.thumbnail_path)

            # 2. 删除原物理文件
            Utils.delete_os_file(file_path)

            # 3. 清理数据库记录
            if file_info:
                DBOperations.delete_file_index_by_file_id(file_info.id)

            return True, "文件及其索引、缩略图已成功删除"
        except Exception as e:
            LogUtils.error(f"删除文件操作失败: {file_path}, 错误: {e}")
            return False, f"删除失败: {str(e)}"

    @staticmethod
    def delete_os_file(file_path: str) -> bool:
        """
        用途：删除操作系统层面的物理文件。
        入参说明：file_path (str) - 文件的绝对路径。
        返回值说明：bool - 删除成功返回 True，文件不存在或删除失败返回 False。
        """
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                LogUtils.info(f"文件已删除: {file_path}")
                return True
            except Exception as e:
                LogUtils.error(f"删除文件失败: {file_path}, 错误: {e}")
        return False
