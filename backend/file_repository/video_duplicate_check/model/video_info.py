# -*- coding: utf-8 -*-
"""
@author: 视频信息
@time: 2024/05/17
"""
from typing import Optional

from imagehash import ImageHash

from src.video_duplicate_check.model.video_features_info import VideoFeaturesInfo


class VideoInfo:
    """
    存储视频信息的类。
    """

    def __init__(self, path: str, video_name: str, duration: float,feature: VideoFeaturesInfo,
                 id: Optional[int] = None):
        """
        初始化视频信息对象。

        :param path: 视频文件的绝对路径。
        :param video_name: 视频文件名。
        :param md5: 视频文件的MD5哈希值。
        :param id: (可选) 数据库中的ID。
        """
        self.id: Optional[int] = id
        self.path: str = path
        self.video_name: str = video_name
        self.feature: VideoFeaturesInfo = feature
        self.duration: float = duration
