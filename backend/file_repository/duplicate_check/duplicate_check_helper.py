from typing import List
import os
from backend.file_repository.duplicate_check.checker.md5_checker import MD5Checker
from backend.db.model.file_index import FileIndex
from backend.file_repository.duplicate_check.checker.video_checker import VideoChecker
from backend.file_repository.duplicate_check.checker.models.duplicate_models import DuplicateGroup


class DuplicateCheckHelper:
    """
    用途：文件查重助手，负责根据文件类型协调不同的查重策略。
    """

    def __init__(self) -> None:
        """
        用途：初始化查重助手，实例化所有注册的检查器。
        入参说明：无
        返回值说明：无
        """
        # 维护一个检查器列表，注意顺序：专用检查器在前，兜底检查器在后
        self.checkers = [VideoChecker(), MD5Checker()]

    def add_file(self, file_info: FileIndex) -> None:
        """
        用途：遍历检查器列表，利用检查器的 is_supported 方法进行文件分发录入。
        入参说明：
            file_info (FileIndex): 文件索引对象，包含文件名、路径和 MD5 等信息。
        返回值说明：
            None
        """
        file_name = file_info.file_name or ""
        _, ext = os.path.splitext(file_name.lower())
        
        # 遍历所有检查器，找到第一个支持该后缀名的检查器并处理
        for checker in self.checkers:
            if checker.is_supported(ext):
                checker.add_file(file_info)
                break

    def get_all_results(self) -> List[DuplicateGroup]:
        """
        用途：汇总所有检查器的查重结果。
        入参说明：无
        返回值说明：
            List[DuplicateGroup]: 合并后的重复文件组列表。
        """
        all_results: List[DuplicateGroup] = []
        for checker in self.checkers:
            all_results.extend(checker.get_results())
        return all_results
