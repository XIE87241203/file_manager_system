from abc import ABC, abstractmethod
from typing import List
from backend.db.file_index_processor import FileIndexDBModel
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModule


class BaseDuplicateChecker(ABC):
    """
    用途：文件查重检查器基类，定义录入文件和获取结果的标准接口。
    """

    @abstractmethod
    def add_file(self, file_info: FileIndexDBModel) -> None:
        """
        用途：录入一个文件信息进行查重分析。
        入参说明：
            file_info (FileIndex): 文件索引对象。
        返回值说明：
            None
        """
        pass

    @abstractmethod
    def get_results(self) -> List[DuplicateGroupDBModule]:
        """
        用途：获取查重分析后的结果。
        入参说明：无
        返回值说明：
            List[DuplicateGroupDBModule]: 查重结果组列表。
        """
        pass

    @abstractmethod
    def is_supported(self, file_extension: str) -> bool:
        """
        用途：查询该检查器是否支持处理指定后缀名的文件。
        入参说明：
            file_extension (str): 文件后缀名（带点，如 '.mp4'）。
        返回值说明：
            bool: 如果支持则返回 True，否则返回 False。
        """
        pass
