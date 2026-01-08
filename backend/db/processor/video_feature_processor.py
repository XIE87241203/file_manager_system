import sqlite3
from dataclasses import dataclass
from typing import Optional
from backend.db.base_db_processor import BaseDBProcessor
from backend.model.video_feature_db_model import VideoFeature


class VideoFeatureProcessor(BaseDBProcessor):
    """
    用途：视频特征数据库处理器，负责 video_features 表的结构维护及相关操作
    """

    # 表名
    TABLE_NAME = 'video_features'

    # 列名常量
    COL_ID = 'id'
    COL_FILE_MD5 = 'file_md5'
    COL_VIDEO_HASHES = 'video_hashes'
    COL_DURATION = 'duration'

    def create_table(self, conn: sqlite3.Connection) -> None:
        """
        用途：创建视频特征表，用于记录视频文件的信息
        入参说明：
            conn: sqlite3.Connection 数据库连接对象
        返回值说明：无
        """
        cursor = conn.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                {self.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self.COL_FILE_MD5} TEXT NOT NULL UNIQUE,
                {self.COL_VIDEO_HASHES} TEXT NOT NULL,
                {self.COL_DURATION} REAL
            )
        ''')
        conn.commit()

    def add_or_update_feature(self, features: VideoFeature) -> bool:
        """
        用途：添加或更新视频特征信息
        入参说明：
            features (VideoFeature): 视频特征对象
        返回值说明：
            bool: 是否成功
        """
        query = f"""
            INSERT INTO {self.TABLE_NAME} ({self.COL_FILE_MD5}, {self.COL_VIDEO_HASHES}, {self.COL_DURATION})
            VALUES (?, ?, ?)
            ON CONFLICT({self.COL_FILE_MD5}) DO UPDATE SET
                {self.COL_VIDEO_HASHES} = EXCLUDED.{self.COL_VIDEO_HASHES},
                {self.COL_DURATION} = EXCLUDED.{self.COL_DURATION}
        """
        params = (features.file_md5, features.video_hashes, features.duration)
        result = self._execute(query, params)
        return result is not None and result > 0

    def get_feature_by_md5(self, file_md5: str) -> Optional[VideoFeature]:
        """
        用途：根据 MD5 获取视频特征信息
        入参说明：
            file_md5 (str): 文件的 MD5 值
        返回值说明：
            Optional[VideoFeature]: 视频特征对象，若不存在则返回 None
        """
        query = f"SELECT * FROM {self.TABLE_NAME} WHERE {self.COL_FILE_MD5} = ?"
        row = self._execute(query, (file_md5,), is_query=True, fetch_one=True)
        if row:
            return VideoFeature(**row)
        return None
    @staticmethod
    def clear_video_features() -> bool:
        """
        用途：清空视频特征表
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        return BaseDBProcessor._clear_table(VideoFeatureProcessor.TABLE_NAME)
