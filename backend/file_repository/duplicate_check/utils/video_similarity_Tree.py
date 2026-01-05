# -*- coding: utf-8 -*-
"""
@author: 视频相似性聚合
@time: 2024/05/23
"""
from typing import List, Dict

import imagehash
from backend.common.log_utils import LogUtils
from backend.db.model.video_info_cache import VideoInfoCache
from backend.file_repository.duplicate_check.utils.video_analyzer import VideoAnalyzer
from backend.file_repository.duplicate_check.utils.video_comparison_util import VideoComparisonUtil


class VideoSimilarityTree:
    """
    用途：视频相似性聚合树，用于通过感知哈希算法将相似的视频（包括剪辑片段）自动归类到同一组。
    """

    def __init__(self, video_analyzer: VideoAnalyzer, frame_similar_distance: int = 5,
                 frame_similarity_rate: float = 0.7, interval_seconds: int = 30,
                 max_duration_diff_ratio: float = 0.6):
        """
        用途：初始化视频相似性树配置。

        入参说明：
            - video_analyzer (VideoAnalyzer): 视频分析器实例。
            - frame_similar_distance (int): 相似判定阈值（汉明距离）。
            - frame_similarity_rate (float): 帧匹配成功的占比阈值（0.0-1.0）。
            - interval_seconds (int): 采样间隔（秒）。
            - max_duration_diff_ratio (float): 最大时长比例阈值。
        """
        self.video_groups: List[List[VideoInfoCache]] = []
        # 性能优化：缓存已解析的哈希列表，避免在多轮比对中重复解析字符串
        self._parsed_hash_cache: Dict[str, List[imagehash.ImageHash]] = {}
        
        self.frame_similar_distance = frame_similar_distance
        self.frame_similarity_rate = frame_similarity_rate
        self.interval_seconds = interval_seconds
        self.max_duration_diff_ratio = max_duration_diff_ratio
        self.video_analyzer = video_analyzer

    def add_video(self, video_path: str) -> None:
        """
        用途：分析指定视频文件并将其归类到合适的相似组中。

        入参说明：
            - video_path (str): 视频文件的磁盘路径。
        """
        video_info = self.video_analyzer.create_video_info(video_path, self.interval_seconds)
        if video_info:
            self._compare_video_and_group(video_info)

    def _get_or_parse_hashes(self, video_info: VideoInfoCache) -> List[imagehash.ImageHash]:
        """
        用途：获取视频的哈希列表，优先从本地缓存读取。
        """
        if video_info.md5 not in self._parsed_hash_cache:
            self._parsed_hash_cache[video_info.md5] = VideoComparisonUtil.parse_hashes(video_info.video_hashes)
        return self._parsed_hash_cache[video_info.md5]

    def _compare_video_and_group(self, video_info: VideoInfoCache) -> None:
        """
        用途：核心归类逻辑。将视频与现有各组的代表进行指纹比对。
        """
        # 1. 预解析当前视频哈希
        current_hashes = self._get_or_parse_hashes(video_info)
        if not current_hashes:
            self.video_groups.append([video_info])
            return

        for group in self.video_groups:
            # 每一组的第一个元素约定为该组最长的视频（代表视频）
            representative = group[0]

            # 2. 快速时长过滤 (Fast-fail)
            # 作用：如果两个视频时长差异过大，则直接判定为不相似，跳过耗时的指纹比对。
            if self.max_duration_diff_ratio > 0:
                d1, d2 = video_info.duration, representative.duration
                if d1 is not None and d2 is not None:
                    min_d, max_d = (d1, d2) if d1 < d2 else (d2, d1)
                    if max_d > 0 and (min_d / max_d) < self.max_duration_diff_ratio:
                        continue

            # 3. 核心指纹比对
            rep_hashes = self._get_or_parse_hashes(representative)
            similarity = VideoComparisonUtil.calculate_max_similarity(
                current_hashes, rep_hashes, self.frame_similar_distance
            )

            if similarity >= self.frame_similarity_rate:
                LogUtils.info(f"匹配成功：{video_info.video_name} -> 组 {representative.video_name} (相似度: {similarity:.2%})")
                # 保持组内第一个视频是时长最长的
                if video_info.duration > representative.duration:
                    group.insert(0, video_info)
                else:
                    group.append(video_info)
                return

        # 4. 无匹配组，作为新组的代表
        self.video_groups.append([video_info])

    def get_similar_video_groups(self, min_group_size: int = 2) -> List[List[VideoInfoCache]]:
        """
        用途：获取达到最小规模要求的相似视频分组。
        """
        return [g for g in self.video_groups if len(g) >= min_group_size]
