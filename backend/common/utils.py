import fnmatch
import hashlib
import os
from typing import Tuple, List, Optional

import cv2

from backend.common.file_type_enum import FileType
from backend.common.log_utils import LogUtils


class Utils:
    """
    用途：后端通用工具类
    """

    @staticmethod
    def get_runtime_path() -> str:
        """
        用途说明：获取程序运行时的 data 目录路径。
        入参说明：无
        返回值说明：str - 返回项目根目录下的 data 目录的绝对路径
        """
        base_path: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        data_path: str = os.path.join(base_path, "data")

        if not os.path.exists(data_path):
            os.makedirs(data_path, exist_ok=True)

        return data_path

    @staticmethod
    def calculate_md5(file_path: str) -> Tuple[str, str]:
        """
        用途说明：计算指定文件的完整 MD5 哈希值。适用于需要保证绝对唯一性的场景。
        入参说明：file_path (str) - 文件的绝对路径
        返回值说明：Tuple[str, str] - (文件绝对路径, MD5 十六进制字符串)；失败则 MD5 为空字符串
        """
        hash_md5 = hashlib.md5()
        try:
            if not os.path.exists(file_path):
                LogUtils.error(f"文件不存在，无法计算 MD5: {file_path}")
                return file_path, ""
                
            # 优化：使用 64KB 的缓冲区提高大文件读取速度
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hash_md5.update(chunk)
            return file_path, hash_md5.hexdigest()
        except Exception as e:
            LogUtils.error(f"计算文件 MD5 失败: {file_path}, 错误: {e}")
            return file_path, ""

    @staticmethod
    def calculate_fast_md5(file_path: str, sample_size: int = 8192) -> Tuple[str, str]:
        """
        用途说明：通过文件采样（头、中、尾）和文件大小快速计算 MD5，极大地优化大文件的计算速度。
        入参说明：
            file_path (str): 文件的绝对路径
            sample_size (int): 每个采样块的大小（字节），默认 8KB
        返回值说明：Tuple[str, str] - (文件绝对路径, 采样 MD5 十六进制字符串)
        """
        LogUtils.debug(f"正在计算MD5: {file_path}")
        try:
            if not os.path.exists(file_path):
                LogUtils.error(f"文件不存在，无法计算快速 MD5: {file_path}")
                return file_path, ""

            file_size: int = os.path.getsize(file_path)
            hash_md5 = hashlib.md5()
            
            # 将文件大小混合进哈希，增加区分度
            hash_md5.update(str(file_size).encode('utf-8'))

            if file_size <= sample_size * 3:
                # 文件较小，直接全量读取
                with open(file_path, "rb") as f:
                    hash_md5.update(f.read())
            else:
                # 大文件进行切片采样（头、中、尾）
                with open(file_path, "rb") as f:
                    # 1. 头部采样
                    hash_md5.update(f.read(sample_size))
                    
                    # 2. 中部采样
                    f.seek(file_size // 2 - sample_size // 2)
                    hash_md5.update(f.read(sample_size))
                    
                    # 3. 尾部采样
                    f.seek(-sample_size, os.SEEK_END)
                    hash_md5.update(f.read(sample_size))
                    
            return file_path, hash_md5.hexdigest()
        except Exception as e:
            LogUtils.error(f"计算文件快速 MD5 失败: {file_path}, 错误: {e}")
            return file_path, ""

    @staticmethod
    def should_ignore(file_path: str, 
                      ignore_filenames: List[str], 
                      ignore_paths: List[str],
                      ignore_filenames_case_insensitive: bool = True,
                      ignore_paths_case_insensitive: bool = True) -> bool:
        """
        用途说明：根据忽略规则判断文件是否应被忽略
        入参说明：
            file_path (str): 文件完整路径
            ignore_filenames (List[str]): 忽略的文件名列表（支持通配符）
            ignore_paths (List[str]): 忽略的路径包含字符串列表（支持通配符）
            ignore_filenames_case_insensitive (bool): 文件名忽略是否忽略大小写
            ignore_paths_case_insensitive (bool): 路径忽略是否忽略大小写
        返回值说明：bool - True 表示应忽略，False 表示不忽略
        """
        filename: str = os.path.basename(file_path)
        
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
            search_pattern: str = pattern if ('*' in pattern or '?' in pattern) else f"*{pattern}*"
            
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
        用途说明：从文件路径中获取文件名（包括后缀）。
        入参说明：file_path (str) - 文件的路径。
        返回值说明：str - 文件名（包括后缀）。
        """
        return os.path.basename(file_path)

    @staticmethod
    def delete_os_file(file_path: str) -> bool:
        """
        用途说明：删除操作系统层面的物理文件。
        入参说明：file_path (str) - 文件的绝对路径。
        返回值说明：bool - 删除成功返回 True，文件不存在返回 False。若删除失败则抛出异常。
        """
        if not os.path.exists(file_path):
            return False
            
        try:
            os.remove(file_path)
            LogUtils.info(f"文件已删除: {file_path}")
            return True
        except Exception as e:
            LogUtils.error(f"删除文件失败: {file_path}, 错误: {e}")
            raise e

    @staticmethod
    def process_search_query(search_query: str) -> str:
        """
        用途说明：对搜索关键词进行预处理，根据配置替换特殊字符并转义为 SQL LIKE 格式。
        入参说明：search_query (str): 原始搜索词。
        返回值说明：str: 处理后可直接用于 LIKE 子句的字符串（如 %keyword%）。
        """
        from backend.setting.setting_service import settingService
        
        search_replace_chars: List[str] = settingService.get_config().file_repository.search_replace_chars
        processed_query: str = search_query
        
        if processed_query:
            for char in search_replace_chars:
                if char:
                    processed_query = processed_query.replace(char, '%')
            return f"%{processed_query}%"
        else:
            return "%"

    @staticmethod
    def is_video_file(file_path: str) -> bool:
        """
        用途说明：根据文件后缀判断是否为视频文件。
        入参说明：file_path (str): 文件完整路径。
        返回值说明：bool: 是视频返回 True，否则返回 False。
        """
        video_extensions: set = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.mpeg', '.mpg', '.m4v', '.3gp'}
        _, ext = os.path.splitext(file_path)
        return ext.lower() in video_extensions

    @staticmethod
    def is_image_file(file_path: str) -> bool:
        """
        用途说明：根据文件后缀判断是否为图片文件。
        入参说明：file_path (str): 文件完整路径。
        返回值说明：bool: 是图片返回 True，否则返回 False。
        """
        image_extensions: set = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        _, ext = os.path.splitext(file_path)
        return ext.lower() in image_extensions

    @staticmethod
    def get_video_params(file_path: str) -> Tuple[Optional[float], Optional[str]]:
        """
        用途说明：使用 OpenCV 获取视频的时长与编码格式。
        入参说明：file_path (str): 视频文件路径。
        返回值说明：Tuple[Optional[float], Optional[str]]: (视频时长秒, 编码格式)；获取失败对应项为 None。
        """
        duration: Optional[float] = None
        codec: Optional[str] = None
        cap: Optional[cv2.VideoCapture] = None
        try:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                fps: float = cap.get(cv2.CAP_PROP_FPS)
                frame_count: float = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if fps > 0 and frame_count > 0:
                    # 使用向下取整 (int)，与大多数系统文件管理器的显示习惯保持一致
                    duration = float(int(frame_count / fps))
                
                fourcc: int = int(cap.get(cv2.CAP_PROP_FOURCC))
                if fourcc != 0:
                    # 将整数转换为 4 字符编码字符串
                    codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)]).strip()
        except Exception as e:
            LogUtils.error(f"提取视频参数失败: {file_path}, 错误: {e}")
        finally:
            if cap:
                cap.release()
        return duration, codec

    @staticmethod
    def get_file_info(file_path: str) -> Optional['FileIndexDBModel']:
        """
        用途说明：获取文件信息并组装成 FileIndexDBModel。包含 MD5、文件类型、视频时长与编码等。
        入参说明：file_path (str): 文件完整路径。
        返回值说明：Optional[FileIndexDBModel]: 组装好的数据库模型，失败返回 None。
        """
        from backend.model.db.file_index_db_model import FileIndexDBModel
        try:
            if not os.path.exists(file_path):
                return None

            # 1. 计算 MD5 和基础信息
            _, f_md5 = Utils.calculate_fast_md5(file_path)
            if not f_md5:
                return None
            
            f_size: int = os.path.getsize(file_path)
            f_name: str = os.path.basename(file_path)
            
            # 2. 识别文件类型及提取扩展属性
            file_type: str = FileType.OTHER.value
            video_duration: Optional[float] = None
            video_codec: Optional[str] = None
            
            if Utils.is_video_file(file_path):
                file_type = FileType.VIDEO.value
                video_duration, video_codec = Utils.get_video_params(file_path)
            elif Utils.is_image_file(file_path):
                file_type = FileType.IMAGE.value

            return FileIndexDBModel(
                file_path=file_path,
                file_name=f_name,
                file_md5=f_md5,
                file_size=f_size,
                file_type=file_type,
                video_duration=video_duration,
                video_codec=video_codec
            )
        except Exception as e:
            LogUtils.error(f"获取文件信息失败: {file_path}, 错误: {e}")
            return None
