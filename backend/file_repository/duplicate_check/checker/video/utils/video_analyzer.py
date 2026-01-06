# -*- coding: utf-8 -*-
"""
@author: 视频分析器
@time: 2024/05/22
"""
import os
import threading
from typing import List, Optional, Tuple

import cv2
import imagehash
from PIL import Image
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.db.model.video_features import VideoFeatures
from backend.db.model.video_info_cache import VideoInfoCache


class VideoAnalyzer:
    """
    用途：视频分析器类（单例），提供视频时长获取、关键帧提取、生成视频信息等功能。
    支持多线程并发调用。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> 'VideoAnalyzer':
        """
        用途：实现单例模式，确保全局只有一个 VideoAnalyzer 实例。
        入参说明：无
        返回值说明：VideoAnalyzer - 单例实例
        """
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(VideoAnalyzer, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """
        用途：初始化视频分析器。使用标识位确保初始化逻辑只运行一次。
        入参说明：无
        返回值说明：无
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return
            self._initialized = True

    def get_video_duration(self, cap: cv2.VideoCapture, video_path: str) -> Optional[float]:
        """
        用途：使用 OpenCV 获取视频的总时长（单位：秒）。

        入参说明：
            - cap (cv2.VideoCapture): 已打开的视频捕获对象。
            - video_path (str): 视频文件路径。

        返回值说明：
            - Optional[float]: 视频时长，失败返回 None。
        """
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        if fps <= 0 or frame_count <= 0:
            LogUtils.info(f"无法解析视频时长信息（FPS 或帧数无效）: {video_path}")
            return None

        return frame_count / fps

    def extract_frame_hash(self, cap: cv2.VideoCapture, timestamp: float) -> Optional[imagehash.ImageHash]:
        """
        用途：从视频的指定时间点提取单帧，并计算其感知哈希（pHash）。

        入参说明：
            - cap (cv2.VideoCapture): 视频捕获对象。
            - timestamp (float): 时间戳（秒）。

        返回值说明：
            - Optional[imagehash.ImageHash]: 帧的哈希值。
        """
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()

        if not ret or frame is None:
            return None

        # 优化：转换 BGR 为 RGB 并生成 PIL Image
        try:
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            return imagehash.phash(image)
        except Exception as e:
            LogUtils.debug(f"提取帧哈希失败: {e}")
            return None

    def generate_hash_sequence(self, cap: cv2.VideoCapture, video_path: str, interval: int,
                               duration: float) -> List[imagehash.ImageHash]:
        """
        用途：按固定时间间隔为视频生成哈希序列（指纹）。

        入参说明：
            - cap (cv2.VideoCapture): 视频捕获对象。
            - video_path (str): 视频文件路径。
            - interval (int): 采样间隔（秒）。
            - duration (float): 视频时长。

        返回值说明：
            - List[imagehash.ImageHash]: 哈希序列。
        """
        hashes = []
        for timestamp in range(0, int(duration), interval):
            frame_hash = self.extract_frame_hash(cap, float(timestamp))
            if frame_hash:
                hashes.append(frame_hash)
            else:
                LogUtils.info(f"警告: 无法获取 {video_path} 在 {timestamp}s 处的采样哈希。")
        return hashes

    def create_video_info(self, video_path: str, interval_seconds: int) -> Optional[VideoInfoCache]:
        """
        用途：根据视频路径生成 VideoInfoCache 对象。

        入参说明：
            - video_path (str): 视频文件路径。
            - interval_seconds (int): 哈希采样间隔。

        返回值说明：
            - Optional[VideoInfoCache]: 视频信息对象。
        """
        if not os.path.exists(video_path):
            LogUtils.error(f"视频文件路径不存在: {video_path}")
            return None

        try:
            # 修复点 3：优先从数据库索引获取 MD5，避免重复计算大文件的 MD5 (耗时 IO)
            video_md5 = ""
            thumbnail_path = None
            file_idx = DBOperations.get_file_index_by_path(video_path)
            
            if file_idx and file_idx.file_md5:
                video_md5 = file_idx.file_md5
                thumbnail_path = file_idx.thumbnail_path
            else:
                _, video_md5 = Utils.calculate_md5(video_path)
            
            if not video_md5:
                LogUtils.error(f"无法获取视频 MD5: {video_path}")
                return None

            # 1. 尝试从缓存获取 (VideoInfoCache)
            cached_infos = DBOperations.get_video_info_cache_by_md5(video_md5)
            if cached_infos:
                info = cached_infos[0]
                LogUtils.info(f"从缓存中获取到视频信息: {video_path}")
                info.path = video_path
                info.video_name = os.path.basename(video_path)
                info.thumbnail_path = thumbnail_path
                return info

            # 2. 尝试从特征库获取 (VideoFeatures) - 避免不必要的视频打开操作
            video_feature = DBOperations.get_video_features_by_md5(video_md5)
            
            if video_feature and video_feature.video_hashes:
                LogUtils.info(f"从特征库中匹配到视频指纹: {video_path}")
                video_info = VideoInfoCache(
                    path=video_path,
                    video_name=os.path.basename(video_path),
                    md5=video_md5,
                    duration=video_feature.duration,
                    video_hashes=video_feature.video_hashes,
                    thumbnail_path=thumbnail_path
                )
                DBOperations.add_video_info_cache(video_info)
                return video_info

            # 3. 实时分析视频
            cap = cv2.VideoCapture(video_path)
            try:
                if not cap.isOpened():
                    LogUtils.error(f"无法打开视频文件: {video_path}")
                    return None

                duration = self.get_video_duration(cap, video_path)
                if duration is None:
                    return None

                LogUtils.info(f"正在为视频生成哈希序列: {video_path}")
                video_hashes_list = self.generate_hash_sequence(cap, video_path, interval_seconds, duration)

                if not video_hashes_list:
                    LogUtils.info(f"未能为视频 {video_path} 生成任何有效哈希。")
                    return None
                
                video_hashes_str = ",".join(map(str, video_hashes_list))

                # 更新或创建特征记录
                if video_feature is None:
                    video_feature = VideoFeatures(md5=video_md5, video_hashes=video_hashes_str, duration=duration)
                else:
                    video_feature.video_hashes = video_hashes_str
                    video_feature.duration = duration

                video_info = VideoInfoCache(
                    path=video_path,
                    video_name=os.path.basename(video_path),
                    md5=video_md5,
                    duration=duration,
                    video_hashes=video_hashes_str,
                    thumbnail_path=thumbnail_path
                )

                # 4. 持久化
                DBOperations.add_video_features(video_feature)
                DBOperations.add_video_info_cache(video_info)
                LogUtils.info(f"视频分析完成并存入数据库: {video_path}")

                return video_info
            finally:
                cap.release()

        except Exception as e:
            LogUtils.error(f"处理视频 {video_path} 时发生异常: {e}")
            return None
