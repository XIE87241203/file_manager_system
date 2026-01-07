import sqlite3
from dataclasses import dataclass
from typing import Optional
from backend.db.base_db_processor import BaseDBProcessor

@dataclass
class VideoFeature:
    """
    用途：视频特征数据类，对应 video_features 表
    """
    id: Optional[int] = None
    file_md5: str = ""
    video_hashes: Optional[str] = None
    duration: Optional[float] = None

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
            其中COL_FILE_ID对应file_index的id
        入参说明：
            conn: sqlite3.Connection 数据库连接对象
        返回值说明：无
        """
        cursor = conn.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                {self.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {self.COL_FILE_MD5} TEXT NOT NULL UNIQUE,
                {self.COL_VIDEO_HASHES} TEXT NOT NULL UNIQUE,
                {self.COL_DURATION} REAL,
            )
        ''')
        conn.commit()
