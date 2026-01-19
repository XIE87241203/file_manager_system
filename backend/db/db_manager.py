import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

from backend.common.log_utils import LogUtils
from backend.common.utils import Utils


class DBManager:
    """
    用途：数据库管理类，负责数据库的连接、初始化、版本管理、事务管理和表结构维护
    """
    _instance = None

    # 数据库名
    DB_NAME: str = 'file_manager.db'

    _db_path: str = os.path.join(Utils.get_runtime_path(), DB_NAME)

    def __new__(cls):
        """
        用途说明：实现单例模式，确保全局只有一个数据库管理器实例。
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
        用途说明：获取数据库连接，并启用 WAL 模式及同步设置以优化并发性能。
        入参说明：无
        返回值说明：sqlite3.Connection: 数据库连接对象
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
        用途说明：事务上下文管理器，提供自动提交 and 异常回滚功能，确保跨表操作的原子性。
        入参说明：无
        返回值说明：Generator[sqlite3.Connection, None, None]: 数据库连接
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
        用途说明：初始化数据库和数据表，并执行版本检查与升级逻辑。
        入参说明：无
        返回值说明：无
        """
        from backend.db.db_constants import DBConstants
        try:
            conn: sqlite3.Connection = self.get_connection()
            cursor: sqlite3.Cursor = conn.cursor()

            # 1. 创建版本信息表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.VersionInfo.TABLE_NAME} (
                    {DBConstants.VersionInfo.COL_VERSION} INTEGER PRIMARY KEY
                )
            ''')

            # 2. 获取当前数据库版本
            cursor.execute(f"SELECT {DBConstants.VersionInfo.COL_VERSION} FROM {DBConstants.VersionInfo.TABLE_NAME}")
            row = cursor.fetchone()
            current_db_version: int = row[0] if row else 0
            # 3. 创建基础表结构（如果不存在）
            self._create_tables(cursor)

            # 4. 版本检查与升级
            target_version: int = DBConstants.DB_VERSION
            if current_db_version == 0:
                # 新数据库，直接插入当前版本号
                cursor.execute(f"INSERT INTO {DBConstants.VersionInfo.TABLE_NAME} ({DBConstants.VersionInfo.COL_VERSION}) VALUES (?)", (target_version,))
                LogUtils.info(f"数据库初始化成功，版本: {target_version}")
            elif current_db_version < target_version:
                # 需要升级
                LogUtils.info(f"检测到数据库版本更新: {current_db_version} -> {target_version}，开始执行适配...")
                self.migrate_db_version(current_db_version, target_version, cursor)
                # 更新版本号
                cursor.execute(f"UPDATE {DBConstants.VersionInfo.TABLE_NAME} SET {DBConstants.VersionInfo.COL_VERSION} = ?", (target_version,))
                LogUtils.info("数据库版本适配完成")

            conn.commit()
            conn.close()
        except Exception as e:
            LogUtils.error(f"数据库初始化或升级失败: {e}")

    @staticmethod
    def _create_tables(cursor: sqlite3.Cursor) -> None:
        """
        用途说明：创建所有核心业务表及其索引（内部方法，由 init_db 调用）。
        入参说明：cursor - 数据库游标对象
        返回值说明：无
        """
        from backend.db.db_constants import DBConstants
        # 1. 创建 file_index 表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.FileIndex.TABLE_NAME} (
                {DBConstants.FileIndex.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.FileIndex.COL_FILE_PATH} TEXT NOT NULL UNIQUE,
                {DBConstants.FileIndex.COL_FILE_MD5} TEXT NOT NULL,
                {DBConstants.FileIndex.COL_FILE_SIZE} INTEGER DEFAULT 0,
                {DBConstants.FileIndex.COL_SCAN_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP,
                {DBConstants.FileIndex.COL_THUMBNAIL_PATH} TEXT,
                {DBConstants.FileIndex.COL_RECYCLE_BIN_TIME} DATETIME
            )
        ''')
        
        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_file_index_md5 
            ON {DBConstants.FileIndex.TABLE_NAME} ({DBConstants.FileIndex.COL_FILE_MD5})
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
                {DBConstants.DuplicateFile.COL_FILE_ID} INTEGER NOT NULL,
                {DBConstants.DuplicateFile.COL_SIMILARITY_TYPE} TEXT,
                {DBConstants.DuplicateFile.COL_SIMILARITY_RATE} REAL DEFAULT 1.0
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

        # 6. 创建 already_entered_file 表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.AlreadyEnteredFile.TABLE_NAME} (
                {DBConstants.AlreadyEnteredFile.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.AlreadyEnteredFile.COL_FILE_NAME} TEXT NOT NULL UNIQUE,
                {DBConstants.AlreadyEnteredFile.COL_ADD_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 7. 创建 pending_entry_file 表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.PendingEntryFile.TABLE_NAME} (
                {DBConstants.PendingEntryFile.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.PendingEntryFile.COL_FILE_NAME} TEXT NOT NULL UNIQUE,
                {DBConstants.PendingEntryFile.COL_ADD_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 8. 创建 file_repo_detail 表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.FileRepoDetail.TABLE_NAME} (
                {DBConstants.FileRepoDetail.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.FileRepoDetail.COL_TOTAL_COUNT} INTEGER DEFAULT 0,
                {DBConstants.FileRepoDetail.COL_TOTAL_SIZE} INTEGER DEFAULT 0,
                {DBConstants.FileRepoDetail.COL_UPDATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    @staticmethod
    def migrate_db_version(old_version: int, new_version: int, cursor: sqlite3.Cursor) -> None:
        """
        用途说明：数据库版本迁移适配逻辑，处理不同版本间的结构差异。
        入参说明：
            old_version (int): 当前数据库中的旧版本号
            new_version (int): 目标新版本号（DBConstants.DB_VERSION）
            cursor (sqlite3.Cursor): 数据库游标对象，用于执行 SQL
        返回值说明：无
        """
        from backend.db.db_constants import DBConstants
        if old_version < 4:
            # 升级到版本 4: 添加 ignore_file 表 (对应旧版名称)
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS ignore_file (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL UNIQUE,
                    add_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            LogUtils.info("数据库升级到版本 4: 已创建 ignore_file 表")
        
        if old_version < 5:
            # 升级到版本 5: 添加 pending_entry_file 表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.PendingEntryFile.TABLE_NAME} (
                    {DBConstants.PendingEntryFile.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.PendingEntryFile.COL_FILE_NAME} TEXT NOT NULL UNIQUE,
                    {DBConstants.PendingEntryFile.COL_ADD_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            LogUtils.info("数据库升级到版本 5: 已创建 pending_entry_file 表")

        if old_version < 6:
            # 升级到版本 6: 将 ignore_file 重命名为 already_entered_file
            try:
                # 检查原表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ignore_file'")
                if cursor.fetchone():
                    cursor.execute(f"ALTER TABLE ignore_file RENAME TO {DBConstants.AlreadyEnteredFile.TABLE_NAME}")
                    LogUtils.info(f"数据库升级到版本 6: 已将 ignore_file 重命名为 {DBConstants.AlreadyEnteredFile.TABLE_NAME}")
                else:
                    # 如果原表不存在，则直接创建新表
                    cursor.execute(f'''
                        CREATE TABLE IF NOT EXISTS {DBConstants.AlreadyEnteredFile.TABLE_NAME} (
                            {DBConstants.AlreadyEnteredFile.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                            {DBConstants.AlreadyEnteredFile.COL_FILE_NAME} TEXT NOT NULL UNIQUE,
                            {DBConstants.AlreadyEnteredFile.COL_ADD_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    LogUtils.info(f"数据库升级到版本 6: 直接创建了 {DBConstants.AlreadyEnteredFile.TABLE_NAME} 表")
            except Exception as e:
                LogUtils.error(f"重命名 ignore_file 表失败: {e}")

        if old_version < 7:
            # 升级到版本 7: 添加 file_repo_detail 表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.FileRepoDetail.TABLE_NAME} (
                    {DBConstants.FileRepoDetail.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.FileRepoDetail.COL_TOTAL_COUNT} INTEGER DEFAULT 0,
                    {DBConstants.FileRepoDetail.COL_TOTAL_SIZE} INTEGER DEFAULT 0,
                    {DBConstants.FileRepoDetail.COL_UPDATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            LogUtils.info(f"数据库升级到版本 7: 已创建 {DBConstants.FileRepoDetail.TABLE_NAME} 表")

        if old_version < 8:
            # 升级到版本 8: 为 duplicate_files 表添加相似类型和相似率字段
            try:
                cursor.execute(f"ALTER TABLE {DBConstants.DuplicateFile.TABLE_FILES} ADD COLUMN {DBConstants.DuplicateFile.COL_SIMILARITY_TYPE} TEXT")
                cursor.execute(f"ALTER TABLE {DBConstants.DuplicateFile.TABLE_FILES} ADD COLUMN {DBConstants.DuplicateFile.COL_SIMILARITY_RATE} REAL DEFAULT 1.0")
                LogUtils.info("数据库升级到版本 8: 已为 duplicate_files 表添加相似度相关字段")
            except Exception as e:
                LogUtils.error(f"数据库升级到版本 8 失败: {e}")

db_manager: DBManager = DBManager()
