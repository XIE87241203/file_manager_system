# -*- coding: utf-8 -*-
"""
@author: 视频分析器
@time: 2024/05/22
"""
import os
import threading
from typing import List, Optional

import cv2
import imagehash
from PIL import Image

from src.utils.log_utils import logger
from src.video_duplicate_check.model.video_features_info import VideoFeaturesInfo
from src.video_duplicate_check.model.video_info import VideoInfo
from src.video_duplicate_check.utils.md5_helper import MD5Helper
from src.video_duplicate_check.utils.video_cache_manager import VideoCacheManager


class VideoAnalyzer:
    """
    视频分析器类（单例），提供视频时长获取、关键帧提取、生成视频信息等功能。
    支持多线程并发调用。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
        实现单例模式，确保全局只有一个 VideoAnalyzer 实例。
        """
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(VideoAnalyzer, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        初始化视频分析器。使用标识位确保初始化逻辑只运行一次。
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return
            self._initialized = True
            self._cache_manager: Optional[VideoCacheManager] = None

    def set_cache_manager(self, cache_manager: VideoCacheManager):
        """
        设置缓存管理器。
        """
        self._cache_manager = cache_manager

    def get_video_duration(self, cap: cv2.VideoCapture, video_path: str) -> Optional[float]:
        """
        使用 OpenCV 获取视频的总时长（单位：秒）。
        """
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        if fps <= 0:
            logger.info(f"无法解析视频帧率: {video_path}", caller=self)
            return None

        duration = frame_count / fps
        return duration

    def extract_frame_hash(self, cap: cv2.VideoCapture, timestamp: float) -> Optional[
        imagehash.ImageHash]:
        """
        从视频的指定时间点提取单帧，并计算其感知哈希（pHash）。
        """
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ret, frame = cap.read()

        if not ret or frame is None:
            return None

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)
        return imagehash.phash(image)

    def generate_hash_sequence(self, cap: cv2.VideoCapture, video_path: str, interval: int,
                               duration: float) -> List[imagehash.ImageHash]:
        """
        按固定时间间隔为视频生成哈希序列（指纹）。
        """
        hashes = []
        for timestamp in range(0, int(duration), interval):
            frame_hash = self.extract_frame_hash(cap, float(timestamp))
            if frame_hash:
                hashes.append(frame_hash)
            else:
                logger.info(f"警告: 无法获取 {video_path} 在 {timestamp}s 处的采样哈希。",
                            caller=self)
        return hashes

    def create_video_info(self, video_path: str, interval_seconds: int) -> Optional[VideoInfo]:
        """
        根据视频路径生成 VideoInfo 对象。
        """
        if not os.path.exists(video_path):
            logger.error(f"视频文件路径不存在: {video_path}", caller=self)
            return None

        try:
            video_md5 = MD5Helper.calculate_md5(video_path)

            # 1. 尝试从缓存获取
            if self._cache_manager:
                cached_info = self._cache_manager.get_video_info_cache(video_md5)
                if cached_info:
                    logger.info(f"从缓存中获取到视频信息: {video_path}", caller=self)
                    cached_info.path = video_path
                    cached_info.video_name = os.path.basename(video_path)
                    return cached_info

            cap = None
            try:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    return None

                # 2. 缓存中没有或缓存管理器未设置，生成新的视频信息
                duration = self.get_video_duration(cap, video_path)
                if duration is None:
                    logger.error(f"无法获取视频时长: {video_path}", caller=self)
                    return None

                # 尝试从特征缓存获取哈希序列
                video_feature = None
                if self._cache_manager:
                    video_feature = self._cache_manager.get_video_features_cache(video_md5)

                if video_feature and video_feature.video_hashes:
                    logger.info(f"从特征缓存中获取到哈希序列: {video_path}", caller=self)
                else:
                    logger.info(f"正在为视频生成哈希序列: {video_path}", caller=self)
                    video_hashes = self.generate_hash_sequence(cap, video_path, interval_seconds,
                                                               duration)

                    if not video_hashes:
                        logger.info(f"未能为视频 {video_path} 生成哈希序列。", caller=self)
                        return None

                    if video_feature is None:
                        video_feature = VideoFeaturesInfo(video_md5)
                    video_feature.set_hashes_from_list(video_hashes)

                video_info = VideoInfo(video_path, os.path.basename(video_path), duration,
                                       video_feature)

                # 3. 存入缓存
                if self._cache_manager:
                    self._cache_manager.save_video_features_cache(video_info.feature)
                    self._cache_manager.save_video_info_cache(video_info)
                    logger.info(f"视频信息已存入缓存: {video_path}", caller=self)

                return video_info
            except Exception as e:
                logger.info(f"处理视频 {video_path} 时出错: {e}", caller=self)
                return None
            finally:
                if cap:
                    cap.release()
        except Exception as e:
            logger.error(f"处理视频 {video_path} 时出错: {e}", caller=self)
            return None
