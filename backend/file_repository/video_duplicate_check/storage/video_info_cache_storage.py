# -*- coding: utf-8 -*-
"""
@author: 视频信息缓存存储器
@time: 2024/05/17
"""
import sqlite3
from typing import List, Optional

from src.video_duplicate_check.model.video_info import VideoInfo
from src.video_duplicate_check.model.video_features_info import VideoFeaturesInfo
from src.video_duplicate_check.storage.db_helper import DBHelper


class VideoInfoCacheStorage:
    """
    管理视频信息缓存，用于存储和检索 VideoInfo 对象。
    数据库连接由调用方通过参数传入。
    """

    @staticmethod
    def add_video_info(conn: sqlite3.Connection, video_info: VideoInfo):
        """
        将一个 VideoInfo 对象添加到缓存中。
        """
        cursor = conn.cursor()
        
        feature = video_info.feature
        md5 = feature.md5
        hashes_str = feature.video_hashes

        # 检查路径是否存在
        cursor.execute(f"SELECT id FROM {DBHelper.TABLE_VIDEO_INFO_CACHE} WHERE path = ?", (video_info.path,))
        result = cursor.fetchone()

        if result:
            # 更新现有记录
            existing_id = result[0]
            video_info.id = existing_id
            cursor.execute(f"""
                UPDATE {DBHelper.TABLE_VIDEO_INFO_CACHE}
                SET video_name = ?, md5 = ?, duration = ?, video_hashes = ?
                WHERE id = ?
            """, (video_info.video_name, md5, video_info.duration, hashes_str, existing_id))
        else:
            # 插入新记录
            cursor.execute(f"""
                INSERT INTO {DBHelper.TABLE_VIDEO_INFO_CACHE} (path, video_name, md5, duration, video_hashes)
                VALUES (?, ?, ?, ?, ?)
            """, (video_info.path, video_info.video_name, md5, video_info.duration, hashes_str))
            video_info.id = cursor.lastrowid

        conn.commit()

    @staticmethod
    def get_video_info_by_md5(conn: sqlite3.Connection, md5: str) -> Optional[VideoInfo]:
        """
        根据MD5值从缓存中检索第一个匹配的VideoInfo对象。
        """
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, path, video_name, md5, duration, video_hashes FROM {DBHelper.TABLE_VIDEO_INFO_CACHE} WHERE md5 = ?", (md5,))
        result = cursor.fetchone()

        if result:
            id_val, path, video_name, db_md5, duration, hashes_str = result
            feature = VideoFeaturesInfo(md5=db_md5, video_hashes=hashes_str)
            return VideoInfo(id=id_val, path=path, video_name=video_name, duration=duration, feature=feature)

        return None

    @staticmethod
    def get_all_video_infos(conn: sqlite3.Connection) -> List[VideoInfo]:
        """
        从缓存中检索所有的 VideoInfo 对象。
        """
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, path, video_name, md5, duration, video_hashes FROM {DBHelper.TABLE_VIDEO_INFO_CACHE}")
        results = cursor.fetchall()

        video_infos = []
        for row in results:
            id_val, path, video_name, md5, duration, hashes_str = row
            feature = VideoFeaturesInfo(md5=md5, video_hashes=hashes_str)
            video_infos.append(VideoInfo(id=id_val, path=path, video_name=video_name, duration=duration, feature=feature))

        return video_infos

    @staticmethod
    def clear_cache(conn: sqlite3.Connection):
        """
        清空 `video_info_cache` 表中的所有数据。
        """

        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {DBHelper.TABLE_VIDEO_INFO_CACHE}")
        conn.commit()
