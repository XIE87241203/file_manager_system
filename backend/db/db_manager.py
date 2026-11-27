import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, List, Optional, Dict

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.common.repo_context import get_current_repo_id


class DBManager:
    """
    用途：数据库管理类，负责数据库的连接、初始化、版本管理、事务管理和表结构维护。
    多仓库支持：每个仓库对应一个独立 SQLite 库文件，连接按当前仓库上下文路由；
    仓库元数据集中存放于独立主数据库 repositories.db。
    """
    _instance = None

    # 默认仓库数据库名（承载历史数据）
    DB_NAME: str = 'file_manager.db'
    # 仓库元数据主数据库名
    MASTER_DB_NAME: str = 'repositories.db'

    _db_path: str = os.path.join(Utils.get_runtime_path(), DB_NAME)
    _master_db_path: str = os.path.join(Utils.get_runtime_path(), MASTER_DB_NAME)

    # 仓库 ID -> 库文件绝对路径 缓存
    _repo_path_cache: Dict[int, str] = {}
    # 主数据库是否已初始化（确保早期 DB 访问前 repositories 表已就绪）
    _master_ready: bool = False

    def __new__(cls):
        """
        用途说明：实现单例模式，确保全局只有一个数据库管理器实例。
        入参说明：无
        返回值说明：DBManager 实例
        """
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
        return cls._instance

    def get_master_connection(self) -> sqlite3.Connection:
        """
        用途说明：获取仓库元数据主数据库连接（独立于各仓库业务库）。
        入参说明：无
        返回值说明：sqlite3.Connection: 主数据库连接对象，行工厂为 sqlite3.Row。
        """
        conn: sqlite3.Connection = sqlite3.connect(DBManager._master_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_master(self) -> None:
        """
        用途说明：初始化仓库元数据主数据库，创建仓库、用户、用户仓库权限、登录历史和更新日志已读表（若不存在）。
        入参说明：无
        返回值说明：无
        """
        from backend.db.db_constants import DBConstants
        conn: Optional[sqlite3.Connection] = None
        DBManager._master_ready = False
        try:
            conn = self.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.Repository.TABLE_NAME} (
                    {DBConstants.Repository.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.Repository.COL_NAME} TEXT NOT NULL UNIQUE,
                    {DBConstants.Repository.COL_CONFIG} TEXT NOT NULL,
                    {DBConstants.Repository.COL_DB_FILE} TEXT NOT NULL,
                    {DBConstants.Repository.COL_CREATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 全局用户账户表（登录不分仓库，故存于主库；用户名唯一，密码存加盐慢哈希）
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.User.TABLE_NAME} (
                    {DBConstants.User.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.User.COL_USERNAME} TEXT NOT NULL UNIQUE,
                    {DBConstants.User.COL_PASSWORD_HASH} TEXT NOT NULL,
                    {DBConstants.User.COL_IS_ADMIN} INTEGER NOT NULL DEFAULT 0,
                    {DBConstants.User.COL_CREATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP,
                    {DBConstants.User.COL_UPDATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 首次引入用户仓库权限时，为已有系统使用者保留原有仓库访问能力。
            # 系统管理员不落逐仓库记录，查询时隐式拥有全部仓库的管理员权限。
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = ?",
                (DBConstants.UserRepositoryPermission.TABLE_NAME,)
            )
            permission_table_exists: bool = cursor.fetchone()[0] > 0
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.UserRepositoryPermission.TABLE_NAME} (
                    {DBConstants.UserRepositoryPermission.COL_USER_ID} INTEGER NOT NULL,
                    {DBConstants.UserRepositoryPermission.COL_REPO_ID} INTEGER NOT NULL,
                    {DBConstants.UserRepositoryPermission.COL_PERMISSION} TEXT NOT NULL,
                    PRIMARY KEY ({DBConstants.UserRepositoryPermission.COL_USER_ID}, {DBConstants.UserRepositoryPermission.COL_REPO_ID})
                )
            ''')
            if not permission_table_exists:
                cursor.execute(f'''
                    INSERT OR IGNORE INTO {DBConstants.UserRepositoryPermission.TABLE_NAME}
                        ({DBConstants.UserRepositoryPermission.COL_USER_ID},
                         {DBConstants.UserRepositoryPermission.COL_REPO_ID},
                         {DBConstants.UserRepositoryPermission.COL_PERMISSION})
                    SELECT u.{DBConstants.User.COL_ID}, r.{DBConstants.Repository.COL_ID}, ?
                    FROM {DBConstants.User.TABLE_NAME} u
                    CROSS JOIN {DBConstants.Repository.TABLE_NAME} r
                    WHERE u.{DBConstants.User.COL_IS_ADMIN} = 0
                ''', (DBConstants.UserRepositoryPermission.PERMISSION_ADMIN,))
            # 全局用户更新日志已读表（每个用户一行，不按仓库重复记录）
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.UserChangelogRead.TABLE_NAME} (
                    {DBConstants.UserChangelogRead.COL_USER_ID} INTEGER PRIMARY KEY,
                    {DBConstants.UserChangelogRead.COL_VERSION} TEXT NOT NULL,
                    {DBConstants.UserChangelogRead.COL_READ_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 全局用户登录历史表（记录每次成功登录的时间与来源 IP，按用户追溯）
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.LoginHistory.TABLE_NAME} (
                    {DBConstants.LoginHistory.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.LoginHistory.COL_USER_ID} INTEGER NOT NULL,
                    {DBConstants.LoginHistory.COL_USERNAME} TEXT NOT NULL,
                    {DBConstants.LoginHistory.COL_LOGIN_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP,
                    {DBConstants.LoginHistory.COL_IP} TEXT
                )
            ''')
            # 按用户查询登录历史的索引（分页查询条件为 user_id）
            cursor.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_login_history_user_id
                ON {DBConstants.LoginHistory.TABLE_NAME} ({DBConstants.LoginHistory.COL_USER_ID})
            ''')
            conn.commit()
            DBManager._master_ready = True
        except Exception as e:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    LogUtils.error(t('db_rollback_failed', error=str(rollback_error)))
            LogUtils.error(t('db_init_failed', error=str(e)))
            raise
        finally:
            if conn is not None:
                conn.close()

    def resolve_db_path(self, repo_id: int) -> str:
        """
        用途说明：根据仓库 ID 解析其业务库文件的绝对路径（带缓存）。
        入参说明：repo_id (int): 仓库 ID。
        返回值说明：str - 库文件绝对路径；仓库不存在时回退到默认仓库库文件。
        """
        if repo_id in DBManager._repo_path_cache:
            return DBManager._repo_path_cache[repo_id]

        # 确保主数据库表已就绪（兼容应用初始化前的早期 DB 访问）
        if not DBManager._master_ready:
            self.init_master()

        from backend.db.db_constants import DBConstants
        abs_path: str = DBManager._db_path
        try:
            conn: sqlite3.Connection = self.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT {DBConstants.Repository.COL_DB_FILE} FROM {DBConstants.Repository.TABLE_NAME} "
                f"WHERE {DBConstants.Repository.COL_ID} = ?",
                (repo_id,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                abs_path = os.path.join(Utils.get_runtime_path(), row[0])
        except Exception as e:
            LogUtils.error(t('db_init_failed', error=str(e)))

        DBManager._repo_path_cache[repo_id] = abs_path
        return abs_path

    def clear_repo_path_cache(self) -> None:
        """
        用途说明：清空仓库库文件路径缓存，在仓库新增/删除后调用以刷新路由。
        入参说明：无
        返回值说明：无
        """
        DBManager._repo_path_cache.clear()

    def get_connection(self) -> sqlite3.Connection:
        """
        用途说明：获取当前仓库上下文对应的业务库连接，并启用 WAL 模式及同步设置以优化并发性能。
        入参说明：无
        返回值说明：sqlite3.Connection: 数据库连接对象
        """
        db_path: str = self.resolve_db_path(get_current_repo_id())
        conn: sqlite3.Connection = sqlite3.connect(db_path)
        # 注册文件名首字母函数，供相册在 SQLite 内完成全局排序，避免把全表读入内存
        from backend.common.filename_sort_utils import FilenameSortUtils
        conn.create_function('filename_initial', 1, FilenameSortUtils.get_initial, deterministic=True)
        # 启用 WAL (Write-Ahead Logging) 模式
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception as e:
            LogUtils.error(t('db_wal_failed', error=str(e)))
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        用途说明：事务上下文管理器，提供自动提交 and 异常回滚功能，确保跨表操作的原子性。
        入参说明：无
        返回值说明：Generator[sqlite3.Connection, None, None]: 数据库连接
        """
        conn: sqlite3.Connection = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            LogUtils.error(t('db_transaction_failed', error=str(e)))
            raise e
        finally:
            conn.close()

    def init_db(self, db_path: Optional[str] = None) -> None:
        """
        用途说明：初始化指定仓库数据库，每次调用都检查版本，并在版本落后时执行原子迁移。
        入参说明：db_path (Optional[str]): 目标库文件绝对路径；为 None 时使用当前仓库上下文对应的库。
        返回值说明：无；初始化或迁移失败时记录日志并抛出异常，阻止系统带不完整结构启动。
        """
        from backend.db.db_constants import DBConstants
        target_path: str = db_path or self.resolve_db_path(get_current_repo_id())
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(target_path)
            cursor: sqlite3.Cursor = conn.cursor()

            # 先确保版本表存在并提交，后续建表、迁移和版本号更新放在同一个事务中。
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.VersionInfo.TABLE_NAME} (
                    {DBConstants.VersionInfo.COL_VERSION} INTEGER PRIMARY KEY
                )
            ''')
            conn.commit()

            cursor.execute(f"SELECT {DBConstants.VersionInfo.COL_VERSION} FROM {DBConstants.VersionInfo.TABLE_NAME}")
            row = cursor.fetchone()
            current_db_version: int = row[0] if row else 0
            target_version: int = DBConstants.DB_VERSION
            LogUtils.info(t('db_version_read_success', version=current_db_version))

            if current_db_version > target_version:
                raise RuntimeError(t(
                    'db_version_newer_than_supported',
                    current=current_db_version,
                    target=target_version
                ))

            # 显式事务覆盖 DDL，避免进程中断或某步迁移失败后留下半成品结构。
            cursor.execute("BEGIN IMMEDIATE")
            migrated: bool = False
            if current_db_version == 0:
                self._create_tables(cursor)
                cursor.execute(
                    f"INSERT INTO {DBConstants.VersionInfo.TABLE_NAME} "
                    f"({DBConstants.VersionInfo.COL_VERSION}) VALUES (?)",
                    (target_version,)
                )
            elif current_db_version < target_version:
                LogUtils.info(t('db_version_update_detected', old=current_db_version, new=target_version))
                self.migrate_db_version(current_db_version, target_version, cursor)
                cursor.execute(
                    f"UPDATE {DBConstants.VersionInfo.TABLE_NAME} "
                    f"SET {DBConstants.VersionInfo.COL_VERSION} = ?",
                    (target_version,)
                )
                migrated = True
            else:
                LogUtils.info(t('db_version_latest', version=target_version))

            # 兼容历史上版本号已更新但结构未完整的数据库；只补结构，不扫描文件。
            self._ensure_file_index_album_columns(cursor)
            DBManager._create_face_tables(cursor)
            conn.commit()
            if current_db_version == 0:
                LogUtils.info(t('db_init_success', version=target_version))
            elif migrated:
                LogUtils.info(t('db_version_update_done'))
        except Exception as e:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    LogUtils.error(t('db_rollback_failed', error=str(rollback_error)))
            LogUtils.error(t('db_init_failed', error=str(e)))
            raise
        finally:
            if conn is not None:
                conn.close()

    def init_all_repo_databases(self) -> None:
        """
        用途说明：启动时读取主数据库中的全部仓库，并逐一检查、初始化或迁移其业务数据库。
        入参说明：无；仓库清单来自主数据库，库文件路径按运行时目录解析。
        返回值说明：无；任一仓库迁移失败时抛出异常，阻止系统继续启动。
        """
        from backend.db.db_constants import DBConstants
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = self.get_master_connection()
            rows: List[sqlite3.Row] = conn.execute(
                f"SELECT {DBConstants.Repository.COL_ID}, {DBConstants.Repository.COL_DB_FILE} "
                f"FROM {DBConstants.Repository.TABLE_NAME} ORDER BY {DBConstants.Repository.COL_ID}"
            ).fetchall()
        except Exception as e:
            LogUtils.error(t('db_repo_list_failed', error=str(e)))
            raise
        finally:
            if conn is not None:
                conn.close()

        if not rows:
            self.init_db()
            return

        for row in rows:
            repo_id: int = int(row[0])
            db_file: str = row[1] or self.DB_NAME
            target_path: str = os.path.join(Utils.get_runtime_path(), db_file)
            try:
                self.init_db(target_path)
            except Exception as e:
                LogUtils.error(t('db_repo_init_failed', repo_id=repo_id, path=target_path, error=str(e)))
                raise

    def _create_tables(self, cursor: sqlite3.Cursor) -> None:
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
                {DBConstants.FileIndex.COL_FILE_NAME} TEXT,
                {DBConstants.FileIndex.COL_FILE_MD5} TEXT NOT NULL,
                {DBConstants.FileIndex.COL_FILE_SIZE} INTEGER DEFAULT 0,
                {DBConstants.FileIndex.COL_FILE_TYPE} TEXT,
                {DBConstants.FileIndex.COL_VIDEO_DURATION} REAL,
                {DBConstants.FileIndex.COL_VIDEO_CODEC} TEXT,
                {DBConstants.FileIndex.COL_SCAN_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP,
                {DBConstants.FileIndex.COL_THUMBNAIL_PATH} TEXT,
                {DBConstants.FileIndex.COL_RECYCLE_BIN_TIME} DATETIME,
                {DBConstants.FileIndex.COL_FILE_MTIME} DATETIME,
                {DBConstants.FileIndex.COL_FILE_EXIF_TIME} DATETIME,
                {DBConstants.FileIndex.COL_FILE_LOCATION} TEXT,
                {DBConstants.FileIndex.COL_MEDIA_WIDTH} INTEGER,
                {DBConstants.FileIndex.COL_MEDIA_HEIGHT} INTEGER
            )
        ''')
        
        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_file_index_md5 
            ON {DBConstants.FileIndex.TABLE_NAME} ({DBConstants.FileIndex.COL_FILE_MD5})
        ''')

        # 文件修改时间索引：相册时间轴按该字段倒序分页
        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_file_index_mtime
            ON {DBConstants.FileIndex.TABLE_NAME} ({DBConstants.FileIndex.COL_FILE_MTIME})
        ''')

        # 相册实际排序时间索引：优先 EXIF 拍摄时间，缺失时回退文件修改时间
        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_file_index_album_time
            ON {DBConstants.FileIndex.TABLE_NAME} ({DBConstants.FileIndex.ALBUM_TIME_EXPRESSION})
        ''')

        # 2. 创建 history_file_index 表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.HistoryFileIndex.TABLE_NAME} (
                {DBConstants.HistoryFileIndex.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.HistoryFileIndex.COL_FILE_PATH} TEXT NOT NULL UNIQUE,
                {DBConstants.HistoryFileIndex.COL_FILE_NAME} TEXT,
                {DBConstants.HistoryFileIndex.COL_FILE_MD5} TEXT NOT NULL UNIQUE,
                {DBConstants.HistoryFileIndex.COL_FILE_SIZE} INTEGER DEFAULT 0,
                {DBConstants.HistoryFileIndex.COL_FILE_TYPE} TEXT,
                {DBConstants.HistoryFileIndex.COL_VIDEO_DURATION} REAL,
                {DBConstants.HistoryFileIndex.COL_VIDEO_CODEC} TEXT,
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

        # 3.1 创建 image_features 表（图片感知哈希缓存）
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.ImageFeature.TABLE_NAME} (
                {DBConstants.ImageFeature.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.ImageFeature.COL_FILE_MD5} TEXT NOT NULL UNIQUE,
                {DBConstants.ImageFeature.COL_IMAGE_HASH} TEXT NOT NULL
            )
        ''')

        # 3.2 创建 duplicate_check_meta 表（记录最近一次查重完成时间与耗时）
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.DuplicateCheckMeta.TABLE_NAME} (
                {DBConstants.DuplicateCheckMeta.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_TIME} DATETIME,
                {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_DURATION} REAL DEFAULT 0
            )
        ''')

        # 4. 创建 duplicate_groups 表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.DuplicateGroup.TABLE_GROUPS} (
                {DBConstants.DuplicateGroup.COL_GRP_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME} TEXT NOT NULL,
                {DBConstants.DuplicateGroup.COL_GRP_CREATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 5. 创建 duplicate_files 表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.DuplicateFile.TABLE_FILES} (
                {DBConstants.DuplicateFile.COL_FILE_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} INTEGER NOT NULL,
                {DBConstants.DuplicateFile.COL_FILE_PATH} TEXT NOT NULL,
                {DBConstants.DuplicateFile.COL_SIMILARITY_TYPE} TEXT,
                {DBConstants.DuplicateFile.COL_SIMILARITY_RATE} REAL DEFAULT 1.0
            )
        ''')

        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_duplicate_files_group_id 
            ON {DBConstants.DuplicateFile.TABLE_FILES} ({DBConstants.DuplicateFile.COL_FILE_GROUP_ID})
        ''')
        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_duplicate_files_file_path 
            ON {DBConstants.DuplicateFile.TABLE_FILES} ({DBConstants.DuplicateFile.COL_FILE_PATH})
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

        # 9. 创建 batch_check_results 表
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.BatchCheckResult.TABLE_NAME} (
                {DBConstants.BatchCheckResult.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.BatchCheckResult.COL_NAME} TEXT NOT NULL,
                {DBConstants.BatchCheckResult.COL_SOURCE} TEXT NOT NULL,
                {DBConstants.BatchCheckResult.COL_DETAIL} TEXT
            )
        ''')

        # 10. 创建 organize_settings 表（整理模块专用设置，单行记录）
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.OrganizeSetting.TABLE_NAME} (
                {DBConstants.OrganizeSetting.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.OrganizeSetting.COL_PENDING_DIRS} TEXT NOT NULL DEFAULT '[]',
                {DBConstants.OrganizeSetting.COL_ORGANIZED_DIR} TEXT NOT NULL DEFAULT '',
                {DBConstants.OrganizeSetting.COL_EXTENSIONS} TEXT NOT NULL DEFAULT '[]',
                {DBConstants.OrganizeSetting.COL_RENAME_SCRIPT_PATH} TEXT NOT NULL DEFAULT '',
                {DBConstants.OrganizeSetting.COL_SIZE_OP} TEXT NOT NULL DEFAULT '',
                {DBConstants.OrganizeSetting.COL_SIZE_VALUE} REAL NOT NULL DEFAULT 0,
                {DBConstants.OrganizeSetting.COL_SIZE_UNIT} TEXT NOT NULL DEFAULT 'MB',
                {DBConstants.OrganizeSetting.COL_UPDATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 11. 创建 organize_records 表（整理历史，每整理一个文件记录一条）
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {DBConstants.OrganizeRecord.TABLE_NAME} (
                {DBConstants.OrganizeRecord.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {DBConstants.OrganizeRecord.COL_ORIGINAL_PATH} TEXT NOT NULL,
                {DBConstants.OrganizeRecord.COL_ORIGINAL_NAME} TEXT NOT NULL,
                {DBConstants.OrganizeRecord.COL_ORGANIZED_PATH} TEXT NOT NULL,
                {DBConstants.OrganizeRecord.COL_ORGANIZED_NAME} TEXT NOT NULL,
                {DBConstants.OrganizeRecord.COL_ORGANIZE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 12. 创建图片多人脸索引表（新库直接具备当前结构）
        DBManager._create_face_tables(cursor)

    @staticmethod
    def _create_face_tables(cursor: sqlite3.Cursor) -> None:
        """
        用途说明：创建人脸处理状态与多人脸特征表，供新库初始化和旧库迁移共用。
        入参说明：cursor (sqlite3.Cursor) - 数据库游标。
        返回值说明：无
        """
        from backend.db.db_constants import DBConstants
        state = DBConstants.FaceIndexState
        face = DBConstants.FaceEmbedding
        queue = DBConstants.FaceRecognitionQueue
        file_index = DBConstants.FileIndex

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {queue.TABLE_NAME} (
                {queue.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {queue.COL_FILE_PATH} TEXT NOT NULL UNIQUE,
                {queue.COL_FILE_MD5} TEXT NOT NULL,
                {queue.COL_QUEUED_AT} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {state.TABLE_NAME} (
                {state.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {state.COL_FILE_PATH} TEXT NOT NULL UNIQUE,
                {state.COL_FILE_MD5} TEXT NOT NULL,
                {state.COL_PIPELINE_VERSION} TEXT NOT NULL,
                {state.COL_FACE_COUNT} INTEGER NOT NULL DEFAULT 0,
                {state.COL_PROCESSED_AT} DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {face.TABLE_NAME} (
                {face.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                {face.COL_FILE_PATH} TEXT NOT NULL,
                {face.COL_FILE_MD5} TEXT NOT NULL,
                {face.COL_FACE_INDEX} INTEGER NOT NULL,
                {face.COL_BBOX_X} REAL NOT NULL DEFAULT 0,
                {face.COL_BBOX_Y} REAL NOT NULL DEFAULT 0,
                {face.COL_BBOX_WIDTH} REAL NOT NULL DEFAULT 0,
                {face.COL_BBOX_HEIGHT} REAL NOT NULL DEFAULT 0,
                {face.COL_CONFIDENCE} REAL NOT NULL DEFAULT 0,
                {face.COL_EMBEDDING} BLOB NOT NULL,
                {face.COL_PIPELINE_VERSION} TEXT NOT NULL,
                {face.COL_CREATED_AT} DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE ({face.COL_FILE_PATH}, {face.COL_FACE_INDEX}, {face.COL_PIPELINE_VERSION})
            )
        ''')

        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_face_embeddings_file_path
            ON {face.TABLE_NAME} ({face.COL_FILE_PATH})
        ''')
        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_file_index_face_pending
            ON {file_index.TABLE_NAME} (
                {file_index.COL_FILE_TYPE}, {file_index.COL_RECYCLE_BIN_TIME}, {file_index.COL_FILE_PATH}
            )
        ''')

    @staticmethod
    def _backfill_file_names(cursor: sqlite3.Cursor, table_name: str) -> None:
        """
        用途说明：分批为旧索引中缺失的文件名列补值，避免一次性读取全表。
        入参说明：
            cursor (sqlite3.Cursor): 数据库游标。
            table_name (str): file_index 或 history_file_index 表名，仅使用项目内常量。
        返回值说明：无；只更新文件名为空的历史记录。
        """
        from backend.db.db_constants import DBConstants
        last_id: int = 0
        batch_size: int = 500
        while True:
            rows: List[tuple] = cursor.execute(
                f"SELECT {DBConstants.FileIndex.COL_ID}, {DBConstants.FileIndex.COL_FILE_PATH} "
                f"FROM {table_name} "
                f"WHERE {DBConstants.FileIndex.COL_ID} > ? "
                f"AND ({DBConstants.FileIndex.COL_FILE_NAME} IS NULL "
                f"OR {DBConstants.FileIndex.COL_FILE_NAME} = '') "
                f"ORDER BY {DBConstants.FileIndex.COL_ID} LIMIT ?",
                (last_id, batch_size)
            ).fetchall()
            if not rows:
                break
            data: List[tuple] = [
                (os.path.basename(row[1]), row[0]) for row in rows
            ]
            cursor.executemany(
                f"UPDATE {table_name} SET {DBConstants.FileIndex.COL_FILE_NAME} = ? "
                f"WHERE {DBConstants.FileIndex.COL_ID} = ?",
                data
            )
            last_id = int(rows[-1][0])

    def migrate_db_version(self, old_version: int, new_version: int, cursor: sqlite3.Cursor) -> None:
        """
        用途说明：数据库版本迁移适配逻辑，处理不同版本间的结构差异。
        入参说明：
            old_version (int): 当前数据库中的旧版本号
            new_version (int): 目标新版本号（DBConstants.DB_VERSION）
            cursor (sqlite3.Cursor): 数据库游标对象，用于执行 SQL
        返回值说明：无
        """
        from backend.db.db_constants import DBConstants

        # 先补齐相册依赖列，避免旧库已有部分列时，后续索引创建因缺列而中断。
        DBManager._ensure_file_index_album_columns(cursor)

        if old_version < 8:
            # 升级到版本 8: 为 duplicate_files 添加相似度字段
            try:
                DBManager._add_column_if_missing(
                    cursor, DBConstants.DuplicateFile.TABLE_FILES,
                    DBConstants.DuplicateFile.COL_SIMILARITY_TYPE, 'TEXT'
                )
                DBManager._add_column_if_missing(
                    cursor, DBConstants.DuplicateFile.TABLE_FILES,
                    DBConstants.DuplicateFile.COL_SIMILARITY_RATE, 'REAL DEFAULT 1.0'
                )
                LogUtils.info(t('db_migrate_v8_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v8_failed', error=str(e)))
                raise

        if old_version < 9:
            # 升级到版本 9: 添加 batch_check_results 表
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {DBConstants.BatchCheckResult.TABLE_NAME} (
                    {DBConstants.BatchCheckResult.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                    {DBConstants.BatchCheckResult.COL_NAME} TEXT NOT NULL,
                    {DBConstants.BatchCheckResult.COL_SOURCE} TEXT NOT NULL,
                    {DBConstants.BatchCheckResult.COL_DETAIL} TEXT
                )
            ''')
            LogUtils.info(t('db_migrate_v9_success'))

        if old_version < 10:
            # 升级到版本 10: 为 file_index 和 history_file_index 添加 file_name 列
            try:
                # 1. 为 file_index 添加列并分批补全历史文件名
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_FILE_NAME, 'TEXT'
                )
                DBManager._backfill_file_names(cursor, DBConstants.FileIndex.TABLE_NAME)

                # 2. 为 history_file_index 添加列并分批补全历史文件名
                DBManager._add_column_if_missing(
                    cursor, DBConstants.HistoryFileIndex.TABLE_NAME,
                    DBConstants.HistoryFileIndex.COL_FILE_NAME, 'TEXT'
                )
                DBManager._backfill_file_names(cursor, DBConstants.HistoryFileIndex.TABLE_NAME)

                LogUtils.info(t('db_migrate_v10_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v10_failed', error=str(e)))
                raise

        if old_version < 12:
            # 升级到版本 12: 为 duplicate_groups 添加 create_time 列
            try:
                # 使用“重建表”的方式避开 SQLite 对 ALTER TABLE ADD COLUMN 非常量默认值的限制
                temp_table: str = f"{DBConstants.DuplicateGroup.TABLE_GROUPS}_backup"
                table_name: str = DBConstants.DuplicateGroup.TABLE_GROUPS
                columns: set[str] = {
                    row[1] for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
                }
                if not columns:
                    # 兼容旧版本在重命名后中断的数据库，先恢复备份表再重新执行。
                    backup_columns: set[str] = {
                        row[1] for row in cursor.execute(f"PRAGMA table_info({temp_table})").fetchall()
                    }
                    if not backup_columns:
                        raise RuntimeError(t('db_required_table_missing', table=table_name))
                    cursor.execute(f"ALTER TABLE {temp_table} RENAME TO {table_name}")
                    columns = backup_columns

                if DBConstants.DuplicateGroup.COL_GRP_CREATE_TIME not in columns:
                    # 原表仍存在时，先清理中断残留的旧备份，再执行可重试的重建。
                    cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")
                    # 1. 将原表重命名
                    cursor.execute(f"ALTER TABLE {table_name} RENAME TO {temp_table}")

                    # 2. 创建符合新结构的新表（包含 DEFAULT CURRENT_TIMESTAMP）
                    cursor.execute(f'''
                        CREATE TABLE {table_name} (
                            {DBConstants.DuplicateGroup.COL_GRP_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                            {DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME} TEXT NOT NULL,
                            {DBConstants.DuplicateGroup.COL_GRP_CREATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                    # 3. 迁移数据，将旧数据导入新表，create_time 设为当前时间
                    cursor.execute(f'''
                        INSERT INTO {table_name} (
                            {DBConstants.DuplicateGroup.COL_GRP_ID_PK},
                            {DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME},
                            {DBConstants.DuplicateGroup.COL_GRP_CREATE_TIME}
                        )
                        SELECT
                            {DBConstants.DuplicateGroup.COL_GRP_ID_PK},
                            {DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME},
                            CURRENT_TIMESTAMP
                        FROM {temp_table}
                    ''')

                    # 4. 删除备份表
                    cursor.execute(f"DROP TABLE {temp_table}")
                else:
                    # 结构已完整时清理可能残留的旧备份表，保证迁移可重复执行。
                    cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")

                LogUtils.info(t('db_migrate_v12_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v12_failed', error=str(e)))
                raise e

        if old_version < 13:
            # 升级到版本 13: 添加文件类型、视频时长、视频编码
            try:
                # file_index
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_FILE_TYPE, 'TEXT'
                )
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_VIDEO_DURATION, 'REAL'
                )
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_VIDEO_CODEC, 'TEXT'
                )

                # history_file_index
                DBManager._add_column_if_missing(
                    cursor, DBConstants.HistoryFileIndex.TABLE_NAME,
                    DBConstants.HistoryFileIndex.COL_FILE_TYPE, 'TEXT'
                )
                DBManager._add_column_if_missing(
                    cursor, DBConstants.HistoryFileIndex.TABLE_NAME,
                    DBConstants.HistoryFileIndex.COL_VIDEO_DURATION, 'REAL'
                )
                DBManager._add_column_if_missing(
                    cursor, DBConstants.HistoryFileIndex.TABLE_NAME,
                    DBConstants.HistoryFileIndex.COL_VIDEO_CODEC, 'TEXT'
                )

                LogUtils.info(t('db_migrate_v13_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v13_failed', error=str(e)))
                raise e

        if old_version < 14:
            # 升级到版本 14: 重置查重表结构，从关联 ID 改为关联路径
            try:
                # 1. 直接删除旧的重复文件关联表
                cursor.execute(f"DROP TABLE IF EXISTS {DBConstants.DuplicateFile.TABLE_FILES}")
                
                # 2. 清空重复分组表数据（因为旧关联已失效，重置分组以保证数据一致性）
                cursor.execute(f"DELETE FROM {DBConstants.DuplicateGroup.TABLE_GROUPS}")
                
                # 3. 创建符合新结构的新表 (使用 file_path 关联)
                cursor.execute(f'''
                    CREATE TABLE {DBConstants.DuplicateFile.TABLE_FILES} (
                        {DBConstants.DuplicateFile.COL_FILE_ID_PK} INTEGER PRIMARY KEY AUTOINCREMENT,
                        {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} INTEGER NOT NULL,
                        {DBConstants.DuplicateFile.COL_FILE_PATH} TEXT NOT NULL,
                        {DBConstants.DuplicateFile.COL_SIMILARITY_TYPE} TEXT,
                        {DBConstants.DuplicateFile.COL_SIMILARITY_RATE} REAL DEFAULT 1.0
                    )
                ''')

                # 4. 创建新索引
                cursor.execute(f'''
                    CREATE INDEX IF NOT EXISTS idx_duplicate_files_group_id 
                    ON {DBConstants.DuplicateFile.TABLE_FILES} ({DBConstants.DuplicateFile.COL_FILE_GROUP_ID})
                ''')
                cursor.execute(f'''
                    CREATE INDEX IF NOT EXISTS idx_duplicate_files_file_path 
                    ON {DBConstants.DuplicateFile.TABLE_FILES} ({DBConstants.DuplicateFile.COL_FILE_PATH})
                ''')

                LogUtils.info(t('db_migrate_v14_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v14_failed', error=str(e)))
                raise e

        if old_version < 15:
            # 升级到版本 15: 新增图片特征缓存表与查重时间元数据表
            try:
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {DBConstants.ImageFeature.TABLE_NAME} (
                        {DBConstants.ImageFeature.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                        {DBConstants.ImageFeature.COL_FILE_MD5} TEXT NOT NULL UNIQUE,
                        {DBConstants.ImageFeature.COL_IMAGE_HASH} TEXT NOT NULL
                    )
                ''')
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {DBConstants.DuplicateCheckMeta.TABLE_NAME} (
                        {DBConstants.DuplicateCheckMeta.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                        {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_TIME} DATETIME
                    )
                ''')
                LogUtils.info(t('db_migrate_v15_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v15_failed', error=str(e)))
                raise e

        if old_version < 16:
            # 升级到版本 16: 为 duplicate_check_meta 添加查重耗时列
            try:
                DBManager._add_column_if_missing(
                    cursor, DBConstants.DuplicateCheckMeta.TABLE_NAME,
                    DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_DURATION, 'REAL DEFAULT 0'
                )
                LogUtils.info(t('db_migrate_v16_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v16_failed', error=str(e)))
                raise e

        if old_version < 17:
            # 升级到版本 17: 新增整理模块专用设置表
            try:
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {DBConstants.OrganizeSetting.TABLE_NAME} (
                        {DBConstants.OrganizeSetting.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                        {DBConstants.OrganizeSetting.COL_PENDING_DIRS} TEXT NOT NULL DEFAULT '[]',
                        {DBConstants.OrganizeSetting.COL_ORGANIZED_DIR} TEXT NOT NULL DEFAULT '',
                        {DBConstants.OrganizeSetting.COL_EXTENSIONS} TEXT NOT NULL DEFAULT '[]',
                        {DBConstants.OrganizeSetting.COL_UPDATE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                LogUtils.info(t('db_migrate_v17_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v17_failed', error=str(e)))
                raise e

        if old_version < 18:
            # 升级到版本 18: 为 organize_settings 添加文件名整理脚本路径列
            try:
                DBManager._add_column_if_missing(
                    cursor, DBConstants.OrganizeSetting.TABLE_NAME,
                    DBConstants.OrganizeSetting.COL_RENAME_SCRIPT_PATH, "TEXT NOT NULL DEFAULT ''"
                )
                LogUtils.info(t('db_migrate_v18_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v18_failed', error=str(e)))
                raise e

        if old_version < 19:
            # 升级到版本 19: 新增整理历史表 organize_records
            try:
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {DBConstants.OrganizeRecord.TABLE_NAME} (
                        {DBConstants.OrganizeRecord.COL_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
                        {DBConstants.OrganizeRecord.COL_ORIGINAL_PATH} TEXT NOT NULL,
                        {DBConstants.OrganizeRecord.COL_ORIGINAL_NAME} TEXT NOT NULL,
                        {DBConstants.OrganizeRecord.COL_ORGANIZED_PATH} TEXT NOT NULL,
                        {DBConstants.OrganizeRecord.COL_ORGANIZED_NAME} TEXT NOT NULL,
                        {DBConstants.OrganizeRecord.COL_ORGANIZE_TIME} DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                LogUtils.info(t('db_migrate_v19_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v19_failed', error=str(e)))
                raise e

        if old_version < 20:
            # 升级到版本 20: 为 organize_settings 添加文件大小筛选三列（比较符/数值/单位）
            try:
                DBManager._add_column_if_missing(
                    cursor, DBConstants.OrganizeSetting.TABLE_NAME,
                    DBConstants.OrganizeSetting.COL_SIZE_OP, "TEXT NOT NULL DEFAULT ''"
                )
                DBManager._add_column_if_missing(
                    cursor, DBConstants.OrganizeSetting.TABLE_NAME,
                    DBConstants.OrganizeSetting.COL_SIZE_VALUE, 'REAL NOT NULL DEFAULT 0'
                )
                DBManager._add_column_if_missing(
                    cursor, DBConstants.OrganizeSetting.TABLE_NAME,
                    DBConstants.OrganizeSetting.COL_SIZE_UNIT, "TEXT NOT NULL DEFAULT 'MB'"
                )
                LogUtils.info(t('db_migrate_v20_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v20_failed', error=str(e)))
                raise e

        if old_version < 21:
            # 升级到版本 21: 直接添加文件修改时间空列，历史数据等待下次索引扫描写入
            try:
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_FILE_MTIME, 'DATETIME'
                )
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_file_index_mtime "
                    f"ON {DBConstants.FileIndex.TABLE_NAME} ({DBConstants.FileIndex.COL_FILE_MTIME})"
                )
                LogUtils.info(t('db_migrate_v21_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v21_failed', error=str(e)))
                raise e

        if old_version < 22:
            # 升级到版本 22: 直接添加 EXIF/拍摄时间空列，避免启动时扫描媒体文件
            try:
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_FILE_EXIF_TIME, 'DATETIME'
                )
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_file_index_album_time "
                    f"ON {DBConstants.FileIndex.TABLE_NAME} ({DBConstants.FileIndex.ALBUM_TIME_EXPRESSION})"
                )
                LogUtils.info(t('db_migrate_v22_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v22_failed', error=str(e)))
                raise e

        if old_version < 23:
            # 升级到版本 23: 直接添加拍摄地点空列，历史数据等待下次索引扫描写入
            try:
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_FILE_LOCATION, 'TEXT'
                )
                LogUtils.info(t('db_migrate_v23_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v23_failed', error=str(e)))
                raise e

        if old_version < 24:
            # 升级到版本 24: 新增图片处理状态与多人脸特征表，不自动执行全量识别
            try:
                DBManager._create_face_tables(cursor)
                LogUtils.info(t('db_migrate_v24_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v24_failed', error=str(e)))
                raise e

        if old_version < 25:
            # 升级到版本 25: 新增按文件路径去重的持久化人脸识别队列
            try:
                DBManager._create_face_tables(cursor)
                LogUtils.info(t('db_migrate_v25_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v25_failed', error=str(e)))
                raise e

        if old_version < 26:
            # 升级到版本 26: 直接添加图片/视频分辨率空列，历史数据等待索引或手动补全时写入
            try:
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_MEDIA_WIDTH, 'INTEGER'
                )
                DBManager._add_column_if_missing(
                    cursor, DBConstants.FileIndex.TABLE_NAME,
                    DBConstants.FileIndex.COL_MEDIA_HEIGHT, 'INTEGER'
                )
                LogUtils.info(t('db_migrate_v26_success'))
            except Exception as e:
                LogUtils.error(t('db_migrate_v26_failed', error=str(e)))
                raise e

    @staticmethod
    def _add_column_if_missing(cursor: sqlite3.Cursor, table_name: str,
                               column_name: str, column_definition: str) -> None:
        """
        用途说明：检查表结构并在缺失时添加列，供版本迁移和启动结构校验共用。
        入参说明：
            cursor (sqlite3.Cursor): 数据库游标。
            table_name (str): 表名，仅使用项目内常量。
            column_name (str): 列名，仅使用项目内常量。
            column_definition (str): SQLite 列类型或默认值定义。
        返回值说明：无；列已存在时不执行任何修改。
        """
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns: set[str] = {row[1] for row in cursor.fetchall()}
        if column_name not in columns:
            cursor.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

    @staticmethod
    def _ensure_file_index_album_columns(cursor: sqlite3.Cursor) -> None:
        """
        用途说明：补齐相册依赖的修改时间、拍摄时间、拍摄地点和分辨率空列及索引，不读取或扫描任何文件。
        入参说明：cursor (sqlite3.Cursor) - 初始化或迁移过程中的数据库游标。
        返回值说明：无；可重复执行，已有列和索引保持不变。
        """
        from backend.db.db_constants import DBConstants

        file_index = DBConstants.FileIndex
        DBManager._add_column_if_missing(
            cursor, file_index.TABLE_NAME, file_index.COL_FILE_MTIME, 'DATETIME'
        )
        DBManager._add_column_if_missing(
            cursor, file_index.TABLE_NAME, file_index.COL_FILE_EXIF_TIME, 'DATETIME'
        )
        DBManager._add_column_if_missing(
            cursor, file_index.TABLE_NAME, file_index.COL_FILE_LOCATION, 'TEXT'
        )
        DBManager._add_column_if_missing(
            cursor, file_index.TABLE_NAME, file_index.COL_MEDIA_WIDTH, 'INTEGER'
        )
        DBManager._add_column_if_missing(
            cursor, file_index.TABLE_NAME, file_index.COL_MEDIA_HEIGHT, 'INTEGER'
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_file_index_mtime "
            f"ON {file_index.TABLE_NAME} ({file_index.COL_FILE_MTIME})"
        )
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_file_index_album_time "
            f"ON {file_index.TABLE_NAME} ({file_index.ALBUM_TIME_EXPRESSION})"
        )


# 创建全局唯一的处理器管理器实例，供外部统一调用
db_manager: DBManager = DBManager()
