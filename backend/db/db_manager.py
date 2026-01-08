import sqlite3
import os
from backend.common.utils import Utils
from backend.common.log_utils import LogUtils
from backend.db.processor.duplicate_group_processor import DuplicateGroupDBModuleProcessor
from backend.db.processor.file_index_processor import FileIndexProcessor
from backend.db.processor.history_file_index_processor import HistoryFileIndexProcessor
from backend.db.processor.video_feature_processor import VideoFeatureProcessor


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
            cls._instance.file_index_processor = FileIndexProcessor()
            cls._instance.history_file_index_processor = HistoryFileIndexProcessor()
            cls._instance.video_feature_processor = VideoFeatureProcessor()
            cls._instance.duplicate_group_processor = DuplicateGroupDBModuleProcessor()
            cls._instance.init_db()
        return cls._instance

    def get_connection(self) -> sqlite3.Connection:
        """
        用途：获取数据库连接
        入参说明：无
        返回值说明：sqlite3 连接对象
        """
        return sqlite3.connect(self._db_path)

    def init_db(self) -> None:
        """
        用途：初始化数据库和数据表（建表逻辑）
        入参说明：无
        返回值说明：无
        """
        try:
            conn = self.get_connection()
            # 使用处理器创建所有数据表
            self.file_index_processor.create_table(conn)
            self.history_file_index_processor.create_table(conn)
            self.video_feature_processor.create_table(conn)
            self.duplicate_group_processor.create_table(conn)

            conn.commit()
            conn.close()
            LogUtils.info("数据库初始化及所有表创建成功")
        except Exception as e:
            LogUtils.error(f"数据库初始化失败: {e}")


db_manager = DBManager()
