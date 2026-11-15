# -*- coding: utf-8 -*-
"""
@author: 文件校验工具
@time: 2024/05/16
"""
from typing import List

import imagehash
import numpy as np

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils

# 字节级 popcount 查找表（0-255 每个字节值对应的二进制 1 的个数），
# 用于向量化统计汉明距离，避免逐帧调用 imagehash 的减法运算
_POPCOUNT_TABLE: np.ndarray = np.array([bin(v).count('1') for v in range(256)], dtype=np.uint8)


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
            LogUtils.error(t('dup_video_parse_hash_error', error=str(e)))
            return []

    @staticmethod
    def _pack_hashes(hashes: List[imagehash.ImageHash]) -> np.ndarray:
        """
        用途：将 64 位感知哈希列表打包为 uint64 数组，供向量化异或运算使用。
        入参说明：
            - hashes (List[imagehash.ImageHash]): 感知哈希对象列表。
        返回值说明：
            - np.ndarray: dtype 为 uint64 的一维哈希数组。
        """
        packed: np.ndarray = np.empty(len(hashes), dtype=np.uint64)
        for idx, h in enumerate(hashes):
            packed[idx] = np.packbits(np.asarray(h.hash, dtype=bool).flatten()).view(np.uint64)[0]
        return packed

    @staticmethod
    def calculate_max_similarity(hashes1: List[imagehash.ImageHash],
                                 hashes2: List[imagehash.ImageHash],
                                 similar_distance: int = 8) -> float:
        """
        用途：计算两组已解析哈希序列的最大相似率（支持片段匹配）。
        性能说明：采用 numpy 向量化滑窗比对（uint64 打包 + 异或 + popcount 查表），
        一次性计算所有窗口内全部帧的汉明距离，避免逐帧 Python 循环在长视频场景下的性能损耗。
        判定语义与逐帧版本完全一致：帧距离严格小于阈值记为匹配，相似率 = 匹配帧数 / 短序列长度。

        入参说明：
            - hashes1 (List[imagehash.ImageHash]): 哈希序列1。
            - hashes2 (List[imagehash.ImageHash]): 哈希序列2。
            - similar_distance (int): 相似判定阈值（汉明距离，严格小于）。

        返回值说明：
            - float: 最大相似率。
        """
        if not hashes1 or not hashes2:
            return 0.0

        # 区分长短序列
        long_h, short_h = (hashes1, hashes2) if len(hashes1) >= len(hashes2) else (hashes2, hashes1)
        short_len: int = len(short_h)

        # 打包为 uint64 后构造滑动窗口视图：(窗口数, 短序列长度)
        long_packed: np.ndarray = VideoComparisonUtil._pack_hashes(long_h)
        short_packed: np.ndarray = VideoComparisonUtil._pack_hashes(short_h)
        windows: np.ndarray = np.lib.stride_tricks.sliding_window_view(long_packed, short_len)

        # 向量化计算每个窗口内各帧的汉明距离（异或后按字节查表统计 1 的个数）
        xor_bytes: np.ndarray = np.bitwise_xor(windows, short_packed).view(np.uint8).reshape(-1, 8)
        distances: np.ndarray = _POPCOUNT_TABLE[xor_bytes].sum(axis=1).reshape(windows.shape)

        # 各窗口匹配帧占比的最大值即最大相似率
        rates: np.ndarray = (distances < similar_distance).sum(axis=1) / short_len
        return float(rates.max())