# -*- coding: utf-8 -*-
"""
@author: 视频特征存储器
@time: 2024/05/17
"""
import sqlite3
from typing import Optional

from src.video_duplicate_check.model.video_features_info import VideoFeaturesInfo
from src.video_duplicate_check.storage.db_helper import DBHelper


class VideoFeaturesStorage:
    """
    管理视频 MD5 和感知哈希签名的存储。
    """

    @staticmethod
    def add_features_info(conn: sqlite3.Connection, feature_info: VideoFeaturesInfo):
        """
        存储或更新视频特征信息。

        :param conn: 数据库连接。
        :param feature_info: VideoFeaturesInfo 对象。
        """
        if not conn:
            raise ConnectionError("数据库未连接。")

        cursor = conn.cursor()

        # 使用 MD5 检查是否存在记录
        cursor.execute(f"SELECT id FROM {DBHelper.TABLE_VIDEO_FEATURES} WHERE md5 = ?", (feature_info.md5,))
        result = cursor.fetchone()

        if result:
            # 更新现有记录
            feature_info.id = result[0]
            cursor.execute(f"""
                UPDATE {DBHelper.TABLE_VIDEO_FEATURES}
                SET video_hashes = ?
                WHERE md5 = ?
            """, (feature_info.video_hashes, feature_info.md5))
        else:
            # 插入新记录
            cursor.execute(f"""
                INSERT INTO {DBHelper.TABLE_VIDEO_FEATURES} (md5, video_hashes)
                VALUES (?, ?)
            """, (feature_info.md5, feature_info.video_hashes))
            feature_info.id = cursor.lastrowid

        conn.commit()

    @staticmethod
    def get_features_info(conn: sqlite3.Connection, md5: str) -> Optional[VideoFeaturesInfo]:
        """
        根据 MD5 值获取视频特征信息。

        :param conn: 数据库连接。
        :param md5: 视频的 MD5 值。
        :return: VideoFeaturesInfo 对象，如果不存在则返回 None。
        """
        if not conn:
            raise ConnectionError("数据库未连接。")

        cursor = conn.cursor()
        cursor.execute(f"SELECT id, md5, video_hashes FROM {DBHelper.TABLE_VIDEO_FEATURES} WHERE md5 = ?", (md5,))
        result = cursor.fetchone()

        if result:
            id_val, db_md5, hashes_str = result
            return VideoFeaturesInfo(id=id_val, md5=db_md5, video_hashes=hashes_str)

        return None

    @staticmethod
    def clear_features(conn: sqlite3.Connection):
        """
        清空 `video_features` 表中的所有数据。
        """
        if not conn:
            raise ConnectionError("数据库未连接。")

        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {DBHelper.TABLE_VIDEO_FEATURES}")
        conn.commit()
