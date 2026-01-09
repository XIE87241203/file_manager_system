import os
import sqlite3

from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_constants import DBConstants


class DBManager:
    """
    用途：数据库管理类，负责数据库的连接、初始化和表结构维护
    """
    _instance = None

    # 数据库名
    DB_NAME = 'file_manager.db'

    _db_path = os.path.join(Utils.get_runtime_path(), DB_NAME)

    def __new__(cls):
        """
        用途：实现单例模式
        入参说明：无
        返回值说明：DBManager 实例
        """
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
            # 初始化处理器
            cls._instance.init_db()
        return cls._instance

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        """
        用途：获取数据库连接
        入参说明：无
        返回值说明：sqlite3 连接对象
        """
        return sqlite3.connect(DBManager._db_path)

    # 确定历史索引是否要存储相同md5文件
    # 继续测试功能

    def init_db(self) -> None:
        """
        用途：初始化数据库和数据表（建表逻辑）
        入参说明：无
        返回值说明：无
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

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

            # 2. 创建 history_file_index 表
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

            conn.commit()
            conn.close()
            LogUtils.info("数据库初始化及所有表创建成功")
        except Exception as e:
            LogUtils.error(f"数据库初始化失败: {e}")


db_manager = DBManager()
