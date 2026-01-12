import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_constants import DBConstants


class DBManager:
    """
    用途：数据库管理类，负责数据库的连接、初始化、事务管理和表结构维护
    """
    _instance = None

    # 数据库名
    DB_NAME: str = 'file_manager.db'

    _db_path: str = os.path.join(Utils.get_runtime_path(), DB_NAME)

    def __new__(cls):
        """
        用途：实现单例模式
        入参说明：无
        返回值说明：DBManager 实例
        """
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
            # 初始化数据库
            cls._instance.init_db()
        return cls._instance

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        """
        用途：获取数据库连接，并启用 WAL 模式以优化性能
        入参说明：无
        返回值说明：sqlite3 连接对象
        """
        conn: sqlite3.Connection = sqlite3.connect(DBManager._db_path)
        # 启用 WAL (Write-Ahead Logging) 模式
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception as e:
            LogUtils.error(f"启用 WAL 模式失败: {e}")
        return conn

    @staticmethod
    @contextmanager
    def transaction() -> Generator[sqlite3.Connection, None, None]:
        """
        用途：事务上下文管理器，用于确保跨表操作的原子性
        入参说明：无
        返回值说明：Generator[sqlite3.Connection, None, None]: 数据库连接
        用法示例：
            with DBManager.transaction() as conn:
                processor.do_a(..., conn=conn)
                processor.do_b(..., conn=conn)
        """
        conn: sqlite3.Connection = DBManager.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            LogUtils.error(f"事务执行失败，已回滚: {e}")
            raise e
        finally:
            conn.close()

    def init_db(self) -> None:
        """
        用途：初始化数据库和数据表（建表逻辑），并建立必要的索引以优化查询性能。
        入参说明：无
        返回值说明：无
        """
        try:
            conn: sqlite3.Connection = self.get_connection()
            cursor: sqlite3.Cursor = conn.cursor()

            # 1. 创建 file_index 表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.FileIndex.TABLE_NAME} (
                    {DBConstants.FileIndex.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.FileIndex.COL_FILE_PATH} TEXT NOT NULL UNIQUE,
                    {DBConstants.FileIndex.COL_FILE_MD5} TEXT NOT NULL,
                    {DBConstants.FileIndex.COL_FILE_SIZE} INTEGER DEFAULT 0,
                    {DBConstants.FileIndex.COL_SCAN_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP,
                    {DBConstants.FileIndex.COL_THUMBNAIL_PATH} TEXT,
                    {DBConstants.FileIndex.COL_IS_IN_RECYCLE_BIN} INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_file_index_md5 
                ON {DBConstants.FileIndex.TABLE_NAME} ({DBConstants.FileIndex.COL_FILE_MD5})
            ''')

            # 2. 创建 history_file_index 表 (MD5 必须 UNIQUE)
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.HistoryFileIndex.TABLE_NAME} (
                    {DBConstants.HistoryFileIndex.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.HistoryFileIndex.COL_FILE_PATH} TEXT NOT NULL UNIQUE,
                    {DBConstants.HistoryFileIndex.COL_FILE_MD5} TEXT NOT NULL UNIQUE,
                    {DBConstants.HistoryFileIndex.COL_FILE_SIZE} INTEGER DEFAULT 0,
                    {DBConstants.HistoryFileIndex.COL_SCAN_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP,
                    {DBConstants.HistoryFileIndex.COL_DELETE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 3. 创建 video_features 表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.VideoFeature.TABLE_NAME} (
                    {DBConstants.VideoFeature.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.VideoFeature.COL_FILE_MD5} TEXT NOT NULL UNIQUE,
                    {DBConstants.VideoFeature.COL_VIDEO_HASHES} TEXT NOT NULL,
                    {DBConstants.VideoFeature.COL_DURATION} REAL
                )
            ''')

            # 4. 创建 duplicate_groups 表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.DuplicateGroup.TABLE_GROUPS} (
                    {DBConstants.DuplicateGroup.COL_GRP_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME} TEXT NOT NULL
                )
            ''')

            # 5. 创建 duplicate_files 表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.DuplicateFile.TABLE_FILES} (
                    {DBConstants.DuplicateFile.COL_FILE_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} INTEGER NOT NULL,
                    {DBConstants.DuplicateFile.COL_FILE_ID} INTEGER NOT NULL
                )
            ''')

            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_duplicate_files_group_id 
                ON {DBConstants.DuplicateFile.TABLE_FILES} ({DBConstants.DuplicateFile.COL_FILE_GROUP_ID})
            ''')
            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_duplicate_files_file_id 
                ON {DBConstants.DuplicateFile.TABLE_FILES} ({DBConstants.DuplicateFile.COL_FILE_ID})
            ''')

            conn.commit()
            conn.close()
            LogUtils.info("数据库初始化及索引创建成功")
        except Exception as e:
            LogUtils.error(f"数据库初始化失败: {e}")


db_manager: DBManager = DBManager()
