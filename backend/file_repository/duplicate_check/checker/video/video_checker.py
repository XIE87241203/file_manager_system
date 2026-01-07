import os
from typing import List, Set
from backend.file_repository.duplicate_check.checker.base_checker import BaseDuplicateChecker
from backend.db.file_index_processor import FileIndex
from backend.db.db_operations import DBOperations
from backend.file_repository.duplicate_check.checker.video.utils.video_similarity_Tree import VideoSimilarityTree
from backend.file_repository.duplicate_check.checker.video.utils.video_analyzer import VideoAnalyzer
from backend.common.log_utils import LogUtils
from backend.file_repository.duplicate_check.checker.models.duplicate_models import DuplicateGroup, \
    DuplicateFile


class VideoChecker(BaseDuplicateChecker):
    """
    用途：视频文件查重检查器，通过感知哈希和相似性树识别内容重复或高度相似的视频。
    """

    # 常见视频文件后缀名集合
    VIDEO_EXTENSIONS: Set[str] = {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.mpeg', '.mpg', '.m4v', '.3gp'
    }

    def __init__(self, frame_similar_distance: int = 5,
                 frame_similarity_rate: float = 0.7, interval_seconds: int = 30,
                 max_duration_diff_ratio: float = 0.6):
        """
        用途：初始化视频检查器，配置分析引擎。
        入参说明：
            - frame_similar_distance (int): 相似判定阈值（汉明距离）。
            - frame_similarity_rate (float): 帧匹配成功的占比阈值（0.0-1.0）。
            - interval_seconds (int): 采样间隔（秒）。
            - max_duration_diff_ratio (float): 最大时长比例阈值。
        """
        # 获取 VideoAnalyzer 单例
        self.analyzer = VideoAnalyzer()

        # 初始化相似度树，用于管理视频分组
        self.tree = VideoSimilarityTree(
            self.analyzer,
            frame_similar_distance=frame_similar_distance,
            frame_similarity_rate=frame_similarity_rate,
            interval_seconds=interval_seconds,
            max_duration_diff_ratio=max_duration_diff_ratio
        )

    def add_file(self, file_info: FileIndex) -> None:
        """
        用途：录入一个视频文件信息进行相似度分析。
        入参说明：
            file_info (FileIndex): 文件索引对象。
        返回值说明：
            None
        """
        if self.is_supported(os.path.splitext(file_info.file_path)[1]):
            LogUtils.info(f"VideoChecker 正在处理视频: {file_info.file_path}")
            # 将视频添加到相似性树中进行分析
            self.tree.add_video(file_info.file_path)

    def get_results(self) -> List[DuplicateGroup]:
        """
        用途：获取视频查重分析后的结果。
        入参说明：无
        返回值说明：
            List[DuplicateGroup]: 查重结果组列表。每组包含重复文件的详细信息。
        """
        # 获取所有成员数量达到最小规模（默认2个）的相似组
        similar_groups = self.tree.get_similar_video_groups()

        results = []
        for i, group in enumerate(similar_groups):
            # 转换 VideoInfo 对象为 DuplicateFile 数据类
            duplicate_files = []
            for video in group:
                duplicate_files.append(DuplicateFile(
                    file_name=video.video_name,
                    file_path=video.path,
                    file_md5=video.md5,
                    thumbnail_path=video.thumbnail_path,
                    extra_info={
                        "duration": round(video.duration, 2)
                    }
                ))

            # 创建重复组对象
            group_obj = DuplicateGroup(
                group_id=f"video_sim_{i}",
                checker_type="video_similarity",
                files=duplicate_files
            )
            results.append(group_obj)

        # 完成后清理中间缓存
        DBOperations.clear_video_info_cache()
        return results

    def is_supported(self, file_extension: str) -> bool:
        """
        用途：查询该检查器是否支持处理指定后缀名的文件。
        入参说明：
            file_extension (str): 文件后缀名（带点，如 '.mp4'）。
        返回值说明：
            bool: 如果支持则返回 True，否则返回 False。
        """
        return file_extension.lower() in self.VIDEO_EXTENSIONS
