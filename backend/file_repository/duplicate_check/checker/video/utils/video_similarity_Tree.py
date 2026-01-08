# -*- coding: utf-8 -*-
"""
@author: 视频相似性聚合
@time: 2024/05/23
"""
from typing import List, Dict

import imagehash
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.model.video_file_info_result import VideoFileInfoResult
from backend.file_repository.duplicate_check.checker.video.utils.video_analyzer import VideoAnalyzer
from backend.file_repository.duplicate_check.checker.video.utils.video_comparison_util import \
    VideoComparisonUtil


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
        # self.video_groups 存储的是文件路径的列表，每个列表代表一个相似组
        self.video_groups: List[List[str]] = []
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
        # 使用 video_analyzer 确保视频信息已提取并存入数据库，返回 VideoFileInfo 对象
        video_info = self.video_analyzer.create_video_info(video_path, self.interval_seconds)
        if video_info:
            self._compare_video_and_group(video_info)

    def _get_or_parse_hashes(self, video_info: VideoFileInfoResult) -> List[imagehash.ImageHash]:
        """
        用途：获取视频的哈希列表，优先从本地缓存读取。
        """
        if video_info.file_index.file_md5 not in self._parsed_hash_cache:
            self._parsed_hash_cache[video_info.file_index.file_md5] = VideoComparisonUtil.parse_hashes(video_info.video_feature.video_hashes)
        return self._parsed_hash_cache[video_info.file_index.file_md5]

    def _compare_video_and_group(self, video_info: VideoFileInfoResult) -> None:
        """
        用途：核心归类逻辑。将视频与现有各组的代表进行指纹比对。
        """
        # 1. 预解析当前视频哈希
        current_hashes = self._get_or_parse_hashes(video_info)
        current_path = video_info.file_index.file_path
        
        if not current_hashes:
            self.video_groups.append([current_path])
            return

        for group in self.video_groups:
            # 每一组的第一个元素约定为该组最长的视频（代表视频）
            representative_path = group[0]
            # 通过数据库获取代表视频的完整信息
            representative = DBOperations.get_video_file_info(representative_path)
            
            if not representative:
                continue

            # 2. 快速时长过滤 (Fast-fail)
            # 作用：如果两个视频时长差异过大，则直接判定为不相似，跳过耗时的指纹比对。
            if self.max_duration_diff_ratio > 0:
                d1, d2 = video_info.video_feature.duration, representative.video_feature.duration
                if d1 is not None and d2 is not None:
                    min_d, max_d = (d1, d2) if d1 < d2 else (d2, d1)
                    if max_d > 0 and (min_d / max_d) < self.max_duration_diff_ratio:
                        continue

            # 3. 核心指纹比对
            rep_hashes = self._get_or_parse_hashes(representative)
            similarity = VideoComparisonUtil.calculate_max_similarity(
                current_hashes, rep_hashes, self.frame_similar_distance
            )
            video_name = Utils.get_filename(current_path)
            representative_name = Utils.get_filename(representative_path)

            if similarity >= self.frame_similarity_rate:
                LogUtils.info(f"匹配成功：{video_name} -> 组 {representative_name} (相似度: {similarity:.2%})")
                # 保持组内第一个视频是时长最长的
                if video_info.video_feature.duration > representative.video_feature.duration:
                    group.insert(0, current_path)
                else:
                    group.append(current_path)
                return

        # 4. 无匹配组，作为新组的代表
        self.video_groups.append([current_path])

    def get_similar_video_groups(self, min_group_size: int = 2) -> List[List[VideoFileInfoResult]]:
        """
        用途：获取达到最小规模要求的相似视频分组，并将路径转换为 VideoFileInfo 对象。
        
        入参说明：
            - min_group_size (int): 最小组规模。
            
        返回值说明：
            - List[List[VideoFileInfo]]: 相似视频组列表。
        """
        results = []
        for group_paths in self.video_groups:
            if len(group_paths) >= min_group_size:
                info_group = []
                for path in group_paths:
                    info = DBOperations.get_video_file_info(path)
                    if info:
                        info_group.append(info)
                
                if len(info_group) >= min_group_size:
                    results.append(info_group)
        return results
