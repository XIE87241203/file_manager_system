# -*- coding: utf-8 -*-
"""
@author: 视频信息缓存管理器
@time: 2024/05/22
"""
import sqlite3
from typing import Optional
from src.video_duplicate_check.model.video_info import VideoInfo
from src.video_duplicate_check.model.video_features_info import VideoFeaturesInfo
from src.video_duplicate_check.storage.video_info_cache_storage import VideoInfoCacheStorage
from src.video_duplicate_check.storage.video_features_storage import VideoFeaturesStorage
from src.utils.log_utils import logger


class VideoCacheManager:
    """
    视频信息缓存管理器，负责管理数据库连接和视频信息的存储与检索。
    """

    def __init__(self):
        """
        初始化视频缓存管理器。
        """
        self._cache_storage = VideoInfoCacheStorage()
        self._features_storage = VideoFeaturesStorage()
        self._conn: Optional[sqlite3.Connection] = None

    def open_db(self):
        """
        打开数据库连接。如果连接已存在则忽略。
        """
        if self._conn is None:
            try:
                from src.video_duplicate_check.storage.db_helper import DBHelper
                self._conn = DBHelper().get_connection()
                logger.info("VideoCacheManager 数据库连接已开启。", caller=self)
            except Exception as e:
                logger.error(f"打开数据库连接失败: {e}", caller=self)

    def close_db(self):
        """
        关闭数据库连接。
        """
        if self._conn:
            try:
                from src.video_duplicate_check.storage.db_helper import DBHelper
                DBHelper().close_connection(self._conn)
                self._conn = None
                logger.info("VideoCacheManager 数据库连接已关闭。", caller=self)
            except Exception as e:
                logger.error(f"关闭数据库连接失败: {e}", caller=self)

    def get_video_info_cache(self, md5: str) -> Optional[VideoInfo]:
        """
        根据视频 MD5 获取缓存的视频信息。

        :param md5: 视频的 MD5 字符串
        :return: 缓存的 VideoInfo 对象，如果未找到或连接未开启则返回 None
        """
        if self._conn:
            return self._cache_storage.get_video_info_by_md5(self._conn, md5)
        return None

    def save_video_info_cache(self, video_info: VideoInfo):
        """
        将视频信息保存到缓存数据库。

        :param video_info: 要保存的 VideoInfo 对象
        """
        if self._conn:
            try:
                self._cache_storage.add_video_info(self._conn, video_info)
            except Exception as e:
                logger.error(f"保存视频信息到缓存失败: {e}", caller=self)

    def clear_video_info_cache(self):
        """
        清空视频信息缓存 (VideoInfoCacheStorage)。
        """
        if self._conn:
            try:
                self._cache_storage.clear_cache(self._conn)
                logger.info("已清空视频信息缓存。", caller=self)
            except Exception as e:
                logger.error(f"清空视频信息缓存失败: {e}", caller=self)

    def get_video_features_cache(self, md5: str) -> Optional[VideoFeaturesInfo]:
        """
        根据视频 MD5 获取缓存的视频特征信息。

        :param md5: 视频的 MD5 字符串
        :return: 缓存的 VideoFeaturesInfo 对象，如果未找到或连接未开启则返回 None
        """
        if self._conn:
            try:
                return self._features_storage.get_features_info(self._conn, md5)
            except Exception as e:
                logger.error(f"获取视频特征信息失败: {e}", caller=self)
        return None

    def save_video_features_cache(self, feature_info: VideoFeaturesInfo):
        """
        将视频特征信息保存到缓存数据库。

        :param feature_info: 要保存的 VideoFeaturesInfo 对象
        """
        if self._conn:
            try:
                self._features_storage.add_features_info(self._conn, feature_info)
            except Exception as e:
                logger.error(f"保存视频特征信息失败: {e}", caller=self)

    def clear_video_features_cache(self):
        """
        清空视频特征缓存 (VideoFeaturesStorage)。
        """
        if self._conn:
            try:
                self._features_storage.clear_features(self._conn)
                logger.info("已清空视频特征缓存。", caller=self)
            except Exception as e:
                logger.error(f"清空视频特征缓存失败: {e}", caller=self)

    def clear_all_cache(self):
        try:
            self.open_db()
            self.clear_video_features_cache()
            self.clear_video_info_cache()
        finally:
            self.close_db()
