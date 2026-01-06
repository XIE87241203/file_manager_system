# -*- coding: utf-8 -*-
"""
@author: 文件校验工具
@time: 2024/05/16
"""
from typing import List, Optional, Union

import imagehash
from backend.common.log_utils import LogUtils
from backend.db.model.video_info_cache import VideoInfoCache


class VideoComparisonUtil:
    """
    用途：视频对比工具类，提供视频相似度比对功能。
    """

    @staticmethod
    def parse_hashes(hash_str: str) -> List[imagehash.ImageHash]:
        """
        用途：将数据库中存储的逗号分隔十六进制哈希字符串解析为 ImageHash 对象列表。

        入参说明：
            - hash_str (str): 原始哈希字符串。

        返回值说明：
            - List[imagehash.ImageHash]: 解析后的哈希对象列表。
        """
        if not hash_str:
            return []
        try:
            return [imagehash.hex_to_hash(h.strip()) for h in hash_str.split(',') if h.strip()]
        except Exception as e:
            LogUtils.error(f"解析视频哈希序列出错: {e}")
            return []

    @staticmethod
    def find_video_fragment_similarity(video1: VideoInfoCache, video2: VideoInfoCache,
                                       similar_distance: int = 8,
                                       max_duration_diff_ratio: float = 0.5) -> Optional[float]:
        """
        用途：使用滑动窗口策略比较两个视频的相似度。

        入参说明：
            - video1 (VideoInfoCache): 视频信息对象1。
            - video2 (VideoInfoCache): 视频信息对象2。
            - similar_distance (int): 相似判定阈值，汉明距离小于此值则认为相似。
            - max_duration_diff_ratio (float): 最大时长比例阈值（0.0-1.0）。

        返回值说明：
            - Optional[float]: 最大相似率（0.0 到 1.0），失败返回 None。
        """
        if not video1 or not video2:
            return None

        # 1. MD5 校验优化（完全一致）
        if video1.md5 == video2.md5:
            return 1.0

        # 2. 时长过滤优化
        if max_duration_diff_ratio > 0:
            d1, d2 = video1.duration, video2.duration
            if d1 is not None and d2 is not None:
                min_d, max_d = (d1, d2) if d1 < d2 else (d2, d1)
                if max_d > 0 and (min_d / max_d) < max_duration_diff_ratio:
                    return 0.0

        # 3. 解析指纹并对比
        hashes1 = VideoComparisonUtil.parse_hashes(video1.video_hashes)
        hashes2 = VideoComparisonUtil.parse_hashes(video2.video_hashes)

        return VideoComparisonUtil.calculate_max_similarity(hashes1, hashes2, similar_distance)

    @staticmethod
    def calculate_max_similarity(hashes1: List[imagehash.ImageHash],
                                 hashes2: List[imagehash.ImageHash],
                                 similar_distance: int = 8) -> float:
        """
        用途：计算两组已解析哈希序列的最大相似率（支持片段匹配）。

        入参说明：
            - hashes1 (List[imagehash.ImageHash]): 哈希序列1。
            - hashes2 (List[imagehash.ImageHash]): 哈希序列2。
            - similar_distance (int): 汉明距离阈值。

        返回值说明：
            - float: 最大相似率。
        """
        if not hashes1 or not hashes2:
            return 0.0

        # 区分长短序列
        long_h, short_h = (hashes1, hashes2) if len(hashes1) >= len(hashes2) else (hashes2, hashes1)
        long_len, short_len = len(long_h), len(short_h)

        max_rate = 0.0
        # 滑动窗口对比
        for i in range(long_len - short_len + 1):
            window = long_h[i: i + short_len]
            similar_count = sum(1 for h1, h2 in zip(window, short_h) if (h1 - h2) < similar_distance)
            
            current_rate = similar_count / short_len
            if current_rate > max_rate:
                max_rate = current_rate
            
            if max_rate >= 1.0:
                break

        return max_rate
