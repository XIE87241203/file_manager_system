# -*- coding: utf-8 -*-
"""
@author: 数据库辅助类
@time: 2024/05/17
"""
import sqlite3
import os
import threading
from typing import Final, Optional


class DBHelper:
    """
    数据库辅助类，用于封装数据库连接和表创建（单例模式）。
    """
    _instance = None
    _lock = threading.Lock()

    # 静态常量
    DB_NAME: Final[str] = 'fileCheckHelper.db'
    DB_VERSION: Final[int] = 1
    TABLE_VIDEO_FEATURES: Final[str] = 'video_features'
    TABLE_VIDEO_INFO_CACHE: Final[str] = 'video_info_cache'
    DB_DIR: Final[str] = 'db'

    def __new__(cls, *args, **kwargs):
        """
        实现线程安全的单例模式。

        :param args: 可变位置参数。
        :param kwargs: 可变关键字参数。
        :return: DBHelper 的单例对象。
        """
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        初始化数据库辅助类，配置数据库路径并初始化表结构。
        """
        if hasattr(self, '_initialized'):
            return

        base_dir = os.getcwd()
        # 使用类名访问静态常量
        db_path = os.path.join(base_dir, DBHelper.DB_DIR, DBHelper.DB_NAME)
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._create_or_update_tables()
        self._initialized = True

    def _create_or_update_tables(self):
        """
        创建或更新数据库表结构，处理版本管理。
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA user_version")
            current_version = cursor.fetchone()[0]

            self._create_base_tables(cursor)
            self._update_db(current_version)

            if current_version != DBHelper.DB_VERSION:
                cursor.execute(f"PRAGMA user_version = {DBHelper.DB_VERSION}")
            conn.commit()

    def _update_db(self, old_version: int, new_version: int = DB_VERSION):
        """
        执行数据库升级逻辑。

        :param old_version: 当前数据库版本。
        :param new_version: 目标数据库版本。
        """
        return

    @staticmethod
    def _create_base_tables(cursor: sqlite3.Cursor):
        """
        创建基础数据表。

        :param cursor: 数据库游标。
        """
        # 使用类名访问静态常量
        # 视频特征表：存储 MD5 和感知哈希
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBHelper.TABLE_VIDEO_FEATURES} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                md5 TEXT NOT NULL UNIQUE,
                video_hashes TEXT
            )
        ''')
        # 视频信息缓存表：存储文件路径、名称、时长及特征引用
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBHelper.TABLE_VIDEO_INFO_CACHE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                video_name TEXT NOT NULL,
                md5 TEXT NOT NULL,
                duration REAL,
                video_hashes TEXT
            )
        ''')

    def get_connection(self) -> sqlite3.Connection:
        """
        获取一个新的数据库连接。

        :return: 返回一个新的 sqlite3.Connection 实例。
        """
        return sqlite3.connect(self.db_path)

    def close_connection(self, conn: Optional[sqlite3.Connection]):
        """
        关闭指定的数据库连接。

        :param conn: 要关闭的数据库连接对象。
        """
        if conn:
            try:
                conn.close()
            except Exception:
                pass
