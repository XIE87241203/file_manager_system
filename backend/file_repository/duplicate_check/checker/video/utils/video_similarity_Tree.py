# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import List, Dict

import imagehash

from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.duplicate_check.checker.video.utils.video_analyzer import VideoAnalyzer
from backend.file_repository.duplicate_check.checker.video.utils.video_comparison_util import \
    VideoComparisonUtil
from backend.model.video_file_info_result import VideoFileInfoResult


@dataclass
class VideoSimilarityNode:
    """
    用途说明：存储视频相似性树中的节点信息，包含文件路径及相对于组代表视频的相似度。
    属性说明：
        path (str): 视频文件的绝对路径。
        similarity (float): 与该组代表视频的相似率（0.0-1.0）。
    """
    path: str
    similarity: float


class VideoSimilarityTree:
    """
    用途：视频相似性聚合树，用于通过感知哈希算法将相似的视频自动归类到同一组，并记录相似率。
    """

    def __init__(self, video_analyzer: VideoAnalyzer, frame_similar_distance: int = 5,
                 frame_similarity_rate: float = 0.7, interval_seconds: int = 30,
                 max_duration_diff_ratio: float = 0.6, backwards: bool = False):
        """
        用途说明：初始化视频相似性树配置。
        入参说明：
            video_analyzer (VideoAnalyzer): 视频分析器实例。
            frame_similar_distance (int): 相似判定阈值（汉明距离）。
            frame_similarity_rate (float): 帧匹配成功的占比阈值（0.0-1.0）。
            interval_seconds (int): 采样间隔（秒）。
            max_duration_diff_ratio (float): 最大时长比例阈值。
            backwards (bool): 是否从视频结尾倒序生成特征。
        返回值说明：无
        """
        # self.video_groups 存储的是相似组列表。
        # 每个组是一个列表，包含多个 VideoSimilarityNode 对象
        self.video_groups: List[List[VideoSimilarityNode]] = []
        # 性能优化：缓存已解析的哈希列表
        self._parsed_hash_cache: Dict[str, List[imagehash.ImageHash]] = {}

        self.frame_similar_distance: int = frame_similar_distance
        self.frame_similarity_rate: float = frame_similarity_rate
        self.interval_seconds: int = interval_seconds
        self.max_duration_diff_ratio: float = max_duration_diff_ratio
        self.backwards: bool = backwards
        self.video_analyzer: VideoAnalyzer = video_analyzer

    def add_video(self, video_path: str) -> None:
        """
        用途说明：分析指定视频文件并将其归类到合适的相似组中。
        入参说明：
            video_path (str): 视频文件的磁盘路径。
        返回值说明：无
        """
        video_info: VideoFileInfoResult = self.video_analyzer.create_video_info(video_path, self.interval_seconds, self.backwards)
        if video_info:
            self._compare_video_and_group(video_info)

    def _get_or_parse_hashes(self, video_info: VideoFileInfoResult) -> List[imagehash.ImageHash]:
        """
        用途说明：获取视频的哈希列表，优先从本地缓存读取。
        入参说明：
            video_info (VideoFileInfoResult): 视频文件详情对象。
        返回值说明：
            List[imagehash.ImageHash]: 解析后的图片哈希对象列表。
        """
        md5: str = video_info.file_index.file_md5
        if md5 not in self._parsed_hash_cache:
            self._parsed_hash_cache[md5] = VideoComparisonUtil.parse_hashes(video_info.video_feature.video_hashes)
        return self._parsed_hash_cache[md5]

    def _compare_video_and_group(self, video_info: VideoFileInfoResult) -> None:
        """
        用途说明：核心归类逻辑。将视频与现有各组的代表进行比对，并记录相似率。
        入参说明：
            video_info (VideoFileInfoResult): 待归类的视频文件详情对象。
        返回值说明：无
        """
        current_hashes: List[imagehash.ImageHash] = self._get_or_parse_hashes(video_info)
        current_path: str = video_info.file_index.file_path

        if not current_hashes:
            self.video_groups.append([VideoSimilarityNode(path=current_path, similarity=1.0)])
            return

        for group in self.video_groups:
            # 每一组的第一个元素约定为该组最长的视频（代表视频）
            representative_path: str = group[0].path
            representative: VideoFileInfoResult = DBOperations.get_video_file_info(representative_path)

            if not representative:
                continue

            # 快速时长过滤
            if self.max_duration_diff_ratio > 0:
                d1: float = video_info.video_feature.duration
                d2: float = representative.video_feature.duration
                if d1 is not None and d2 is not None:
                    min_d, max_d = (d1, d2) if d1 < d2 else (d2, d1)
                    if max_d > 0 and (min_d / max_d) < self.max_duration_diff_ratio:
                        continue

            # 指纹比对
            rep_hashes: List[imagehash.ImageHash] = self._get_or_parse_hashes(representative)
            similarity: float = VideoComparisonUtil.calculate_max_similarity(
                current_hashes, rep_hashes, self.frame_similar_distance
            )

            if similarity >= self.frame_similarity_rate:
                video_name: str = Utils.get_filename(current_path)
                representative_name: str = Utils.get_filename(representative_path)
                LogUtils.info(f"匹配成功：{video_name} -> 组 {representative_name} (相似度: {similarity:.2%})")

                # 创建新节点
                node: VideoSimilarityNode = VideoSimilarityNode(path=current_path, similarity=similarity)

                # 保持组内第一个视频是时长最长的
                if video_info.video_feature.duration > representative.video_feature.duration:
                    # 如果当前视频更长，它成为新的代表
                    group[0].similarity = similarity
                    node.similarity = 1.0
                    group.insert(0, node)
                else:
                    group.append(node)
                return

        # 无匹配组，作为新组的代表
        self.video_groups.append([VideoSimilarityNode(path=current_path, similarity=1.0)])

    def get_similar_video_groups(self, min_group_size: int = 2) -> List[List[VideoFileInfoResult]]:
        """
        用途说明：获取达到规模要求的相似组，并封装相似率。
        入参说明：
            min_group_size (int): 组内成员数量的最小阈值。
        返回值说明：
            List[List[VideoFileInfoResult]]: 符合要求的相似视频组列表。
        """
        results: List[List[VideoFileInfoResult]] = []
        for group in self.video_groups:
            if len(group) >= min_group_size:
                info_group: List[VideoFileInfoResult] = []
                for item in group:
                    info: VideoFileInfoResult = DBOperations.get_video_file_info(item.path)
                    if info:
                        info.similarity_rate = item.similarity
                        info_group.append(info)

                if len(info_group) >= min_group_size:
                    results.append(info_group)
        return results
