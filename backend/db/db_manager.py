import sqlite3
import os
from backend.common.utils import Utils
from backend.common.log_utils import LogUtils

class DBManager:
    """
    用途：数据库管理类，负责数据库的连接、初始化和表结构维护
    """
    _instance = None
    
    # 数据库名
    DB_NAME = 'file_manager.db'
    # 文件索引表名
    TABLE_FILE_INDEX = 'file_index'
    # 历史文件索引表名
    TABLE_HISTORY_INDEX = 'history_file_index'
    # 视频特征表名
    TABLE_VIDEO_FEATURES = 'video_features'
    # 视频信息缓存表名
    TABLE_VIDEO_INFO_CACHE = 'video_info_cache'

    _db_path = os.path.join(Utils.get_runtime_path(), DB_NAME)

    def __new__(cls):
        """
        用途：实现单例模式
        入参说明：无
        返回值说明：DBManager 实例
        """
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
            cls._instance.init_db()
        return cls._instance

    def get_connection(self):
        """
        用途：获取数据库连接
        入参说明：无
        返回值说明：sqlite3 连接对象
        """
        return sqlite3.connect(self._db_path)

    def init_db(self):
        """
        用途：初始化数据库和数据表（建表逻辑）
        入参说明：无
        返回值说明：无
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # 创建文件索引表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.TABLE_FILE_INDEX} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_md5 TEXT NOT NULL,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 创建历史文件索引表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.TABLE_HISTORY_INDEX} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_md5 TEXT NOT NULL,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 创建视频特征表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.TABLE_VIDEO_FEATURES} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    md5 TEXT NOT NULL UNIQUE,
                    video_hashes TEXT,
                    duration REAL
                )
            ''')
            # 创建视频信息缓存表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {self.TABLE_VIDEO_INFO_CACHE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    video_name TEXT NOT NULL,
                    md5 TEXT NOT NULL,
                    duration REAL,
                    video_hashes TEXT
                )
            ''')
            conn.commit()
            conn.close()
            LogUtils.info("数据库初始化及表创建成功")
        except Exception as e:
            LogUtils.error(f"数据库初始化失败: {e}")

db_manager = DBManager()
