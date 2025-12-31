# -*- coding: utf-8 -*-
import os
from typing import List

from src.utils.log_utils import logger
from src.video_duplicate_check.model.video_info import VideoInfo
from src.video_duplicate_check.utils.video_comparison_util import VideoComparisonUtil
from src.video_duplicate_check.utils.video_analyzer import VideoAnalyzer


class VideoSimilarityTree:
    """
    视频相似性树（概念上），用于管理视频分组。
    功能上，它将相似的视频聚合到同一个组中。
    """

    def __init__(self, video_analyzer: VideoAnalyzer, frame_similar_distance: int = 8,
                 frame_similarity_rate: float = 0.7, interval_seconds: int = 30,
                 max_duration_diff_ratio: float = 0.8):
        """
        初始化视频相似性树。

        :param video_analyzer: 视频分析器实例。
        :param frame_similar_distance: 相似判定阈值，汉明距离小于此值则认为相似。
        :param frame_similarity_rate: 帧相似度占比阈值。
        :param interval_seconds: 生成哈希时的采样间隔（秒）。
        :param max_duration_diff_ratio: 最大时长比例阈值（0.0-1.0）。如果短视频时长小于长视频时长的该比例，则判定为非相似。
        """
        self.video_groups: List[List[VideoInfo]] = []
        self.frame_similar_distance = frame_similar_distance
        self.frame_similarity_rate = frame_similarity_rate
        self.interval_seconds = interval_seconds
        self.max_duration_diff_ratio = max_duration_diff_ratio

        self.video_analyzer = video_analyzer

    def add_video(self, video_path: str):
        """
        将视频添加到相似性树中。
        它会首先为视频生成哈希序列，然后与现有分组进行比较，
        如果找到足够相似的组，则加入该组；否则，创建一个新组。

        :param video_path: 要添加的视频的路径。
        """
        video_info = self.video_analyzer.create_video_info(video_path, self.interval_seconds)
        if video_info:
            self._compare_video_and_group(video_info)

    def get_similar_video_groups(self, min_group_size: int = 2) -> List[List[VideoInfo]]:
        """
        获取所有相似视频的路径分组。
        只返回成员数量达到最小规模（默认为2）的组。

        :param min_group_size: 分组的最小成员数。
        :return: 一个列表，其中每个子列表都是一组相似视频的 VideoInfo 对象。
        """
        similar_groups = [group for group in self.video_groups if len(group) >= min_group_size]
        logger.info(f"发现 {len(similar_groups)} 个相似视频分组。", caller=self)
        return similar_groups

    def _compare_video_and_group(self, video_info: VideoInfo):
        """
        比较视频与现有分组，并将其归类。
        确保每个组的首个视频是该组中时长最长的视频。

        :param video_info: 要添加的视频信息对象。
        """
        # 遍历现有分组，寻找相似的组
        for group in self.video_groups:
            representative = group[0]

            # --- 指纹比对 (内部包含时长预过滤逻辑) ---
            # 与组内的第一个视频（作为代表，即该组最长视频）进行比较
            similarity = VideoComparisonUtil.find_video_fragment_similarity(
                video_info, representative, self.frame_similar_distance, self.max_duration_diff_ratio
            )

            if similarity is not None and similarity >= self.frame_similarity_rate:
                logger.info(
                    f"视频 {video_info.path} (md5: {video_info.feature.md5}) 与现有组匹配，"
                    f"相似度: {similarity:.2f}。正在添加到组中。",
                    caller=self)

                # 保持组内第一个视频是时长最长的
                if video_info.duration > group[0].duration:
                    group.insert(0, video_info)
                else:
                    group.append(video_info)
                return

        # 如果没有找到相似的组（包括被时长过滤掉的），则创建一个新组
        logger.info(
            f"未找到相似组，为视频 {video_info.path} (md5: {video_info.feature.md5}) 创建一个新组。",
            caller=self)
        self.video_groups.append([video_info])
