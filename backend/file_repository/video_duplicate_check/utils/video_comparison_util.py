# -*- coding: utf-8 -*-
"""
@author: 文件校验工具
@time: 2024/05/16
"""
from typing import List, Optional

import imagehash

from src.utils.log_utils import logger
from src.video_duplicate_check.model.video_info import VideoInfo


class VideoComparisonUtil:
    """
    视频对比工具类，提供视频相似度比对功能。
    """

    @staticmethod
    def find_video_fragment_similarity(video1: VideoInfo, video2: VideoInfo,
                                       similar_distance: int = 8,
                                       max_duration_diff_ratio: float = 0.5) -> Optional[float]:
        """
        使用滑动窗口策略比较两个视频的相似度，判断其中一个是否为另一个的片段。

        该算法的核心思想是：如果视频 A 是视频 B 的一部分，那么 A 的特征序列应该与 B 的某一段连续特征序列高度相似。
        通过计算两个特征序列之间的匹配程度（相似率）来衡量。

        优化策略：
        1. 优先比对 MD5 值，若一致则判定为完全相同。
        2. 时长预过滤：若两个视频时长比例低于设定阈值，则跳过指纹比对。

        :param video1: 视频信息对象1，包含时长、路径及特征信息。
        :param video2: 视频信息对象2，包含时长、路径及特征信息。
        :param similar_distance: 相似判定阈值，汉明距离小于此值则认为相似。
        :param max_duration_diff_ratio: 最大时长比例阈值（0.0-1.0）。如果短视频时长小于长视频时长的该比例，则判定为非相似。
                                       默认为 0.5。
        :return: 最大相似率（0.0 到 1.0 之间的浮点数）。值越接近 1.0 表示越相似。若 MD5 一致则返回 1.0。
        """
        # 1. 基础校验：检查参与对比的视频对象及其特征信息是否有效
        if not video1 or not video2 or not video1.feature or not video2.feature:
            logger.error("比对失败：视频对象或特征信息不能为空。", caller="VideoComparisonUtil")
            return None

        # --- 2. MD5 校验优化 ---
        # 如果 MD5 相同，说明文件内容完全一致（或哈希碰撞，但在视频查重中可视为一致）
        if video1.feature.md5 == video2.feature.md5:
            logger.info(f"MD5 匹配成功：{video1.video_name} 与 {video2.video_name} 完全一致。", caller="VideoComparisonUtil")
            return 1.0

        # --- 3. 时长过滤优化 ---
        if max_duration_diff_ratio > 0:
            d1 = video1.duration
            d2 = video2.duration
            min_d, max_d = (d1, d2) if d1 < d2 else (d2, d1)
            duration_ratio = (min_d / max_d) if max_d > 0 else 0
            
            if duration_ratio < max_duration_diff_ratio:
                # 时长比例低于阈值，判定为非相似，直接返回 0
                return 0.0

        video_hashes1 = video1.feature.get_hashes_list()
        video_hashes2 = video2.feature.get_hashes_list()

        if not video_hashes1 or not video_hashes2:
            logger.info("比对失败：视频指纹序列缺失，请先生成指纹。", caller="VideoComparisonUtil")
            return None

        # 4. 逻辑准备：区分长序列和短序列
        # 目标是拿“短序列”在“长序列”中不断滑动寻找最匹配的一段
        if len(video_hashes1) >= len(video_hashes2):
            long_hashes, short_hashes = video_hashes1, video_hashes2
        else:
            long_hashes, short_hashes = video_hashes2, video_hashes1

        long_len = len(long_hashes)
        short_len = len(short_hashes)

        # 5. 执行滑动窗口对比 (Sliding Window)
        max_similarity_rate = 0.0

        # 在长序列中遍历每一个可能的起始位置
        for i in range(long_len - short_len + 1):
            # 截取长视频中与短视频等长的当前窗口
            window = long_hashes[i: i + short_len]

            # 计算当前窗口与短视频序列的相似率
            similarity_rate = VideoComparisonUtil.compare_videos_hashs(
                window, short_hashes, similar_distance
            )

            # 更新记录到的最大相似度
            if similarity_rate > max_similarity_rate:
                max_similarity_rate = similarity_rate

            # 如果已经达到 1.0 (完全一致)，可提前结束比对
            if max_similarity_rate >= 1.0:
                break

        # 6. 输出并返回比对结果
        logger.info(f"视频片段比对完成，最高相似率: {max_similarity_rate:.4f}", caller="VideoComparisonUtil")
        return max_similarity_rate

    @staticmethod
    def compare_videos_hashs(window: List[imagehash.ImageHash],
                             short_video_hashes: List[imagehash.ImageHash],
                             similar_distance: int = 8) -> float:
        """
        对比两组等长的哈希序列，计算它们的相似率。

        逻辑：遍历每一对哈希值，计算汉明距离。如果距离小于给定的阈值（similar_distance），则认为该帧相似。
        最后返回相似帧数量占总对比帧数量的比例。

        :param window: 待对比的哈希窗口序列（截取的长视频片段）。
        :param short_video_hashes: 参考的短视频哈希序列。
        :param similar_distance: 相似判定阈值，汉明距离小于此值则认为相似，默认为 8。
        :return: 相似率（0.0 到 1.0 之间的浮点数）。
        """
        if not window or not short_video_hashes:
            return 0.0

        # 确保对比的长度一致
        total_count = min(len(window), len(short_video_hashes))
        if total_count == 0:
            return 0.0

        similar_count = 0
        # 逐帧对比哈希值
        for h1, h2 in zip(window, short_video_hashes):
            # 计算汉明距离（不同比特位的个数）
            if (h1 - h2) < similar_distance:
                similar_count += 1

        # 计算相似比例
        return similar_count / total_count
