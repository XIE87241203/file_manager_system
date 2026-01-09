import os
from typing import List

from backend.common.utils import Utils
from backend.file_repository.duplicate_check.checker.image_checker import ImageChecker
from backend.file_repository.duplicate_check.checker.md5_checker import MD5Checker
from backend.file_repository.duplicate_check.checker.video.video_checker import VideoChecker
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModule
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.setting.setting_service import settingService


class DuplicateCheckHelper:
    """
    用途：文件查重助手，负责根据文件类型协调不同的查重策略。
    """

    def __init__(self) -> None:
        """
        用途：初始化查重助手，实例化所有注册的检查器。从配置中加载参数。
        入参说明：无
        返回值说明：无
        """
        # 从 settings 中读取查重配置
        dup_config = settingService.get_config().duplicate_check
        
        # 初始化视频检查器
        video_checker = VideoChecker(
            frame_similar_distance=dup_config.video_frame_similar_distance,
            frame_similarity_rate=dup_config.video_frame_similarity_rate,
            interval_seconds=dup_config.video_interval_seconds,
            max_duration_diff_ratio=dup_config.video_max_duration_diff_ratio
        )
        
        # 初始化图片检查器
        image_checker = ImageChecker(
            threshold=dup_config.image_threshold
        )
        
        # 维护一个检查器列表，注意顺序：专用检查器在前，兜底检查器在后
        # ImageChecker 建议放在 MD5Checker 之前，以便对图片进行相似度（汉明距离）分析
        self.checkers = [video_checker, image_checker, MD5Checker()]

    def add_file(self, file_info: FileIndexDBModel) -> None:
        """
        用途：遍历检查器列表，利用检查器的 is_supported 方法进行文件分发录入。
        入参说明：
            file_info (FileIndex): 文件索引对象，包含文件名、路径和 MD5 等信息。
        返回值说明：
            None
        """
        file_name = Utils.get_filename(file_info.file_path) or ""
        _, ext = os.path.splitext(file_name.lower())
        
        # 遍历所有检查器，找到第一个支持该后缀名的检查器并处理
        for checker in self.checkers:
            if checker.is_supported(ext):
                checker.add_file(file_info)
                break

    def get_all_results(self) -> List[DuplicateGroupDBModule]:
        """
        用途：汇总所有检查器的查重结果。
        入参说明：无
        返回值说明：
            List[DuplicateGroupDBModule]: 合并后的重复文件组列表。
        """
        all_results: List[DuplicateGroupDBModule] = []
        for checker in self.checkers:
            all_results.extend(checker.get_results())
        return all_results
