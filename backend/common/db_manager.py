import sqlite3
import os
from backend.common.utils import Utils
from backend.common.log_utils import LogUtils

class DBManager:
    """
    用途：数据库管理类，负责数据库的连接、初始化和基本操作
    """
    _instance = None
    _db_path = os.path.join(Utils.get_runtime_path(), 'file_manager.db')

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
        用途：初始化数据库和数据表
        入参说明：无
        返回值说明：无
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # 创建文件索引表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_md5 TEXT NOT NULL,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 创建历史文件索引表，file_path 设置为 UNIQUE 以支持冲突更新
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS history_file_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_md5 TEXT NOT NULL,
                    scan_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
            LogUtils.info("数据库初始化成功")
        except Exception as e:
            LogUtils.error(f"数据库初始化失败: {e}")

    def execute_query(self, query, params=()):
        """
        用途：执行查询语句（SELECT）
        入参说明：query - SQL 语句, params - 参数元组
        返回值说明：查询结果列表
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            conn.close()
            return result
        except Exception as e:
            LogUtils.error(f"查询失败: {query}, 错误: {e}")
            return []

    def execute_update(self, query, params=()):
        """
        用途：执行更新语句（INSERT, UPDATE, DELETE）
        入参说明：query - SQL 语句, params - 参数元组
        返回值说明：受影响的行数
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            rowcount = cursor.rowcount
            conn.close()
            return rowcount
        except Exception as e:
            LogUtils.error(f"执行更新失败: {query}, 错误: {e}")
            return 0

    def batch_insert_files(self, file_list):
        """
        用途：批量插入或更新文件索引信息
        入参说明：file_list - 包含 (file_path, file_name, file_md5) 元组的列表
        返回值说明：无
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # 使用 INSERT OR REPLACE 确保路径唯一，如果路径已存在则更新
            cursor.executemany('''
                INSERT OR REPLACE INTO file_index (file_path, file_name, file_md5, scan_time)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', file_list)
            conn.commit()
            conn.close()
            LogUtils.info(f"成功更新 {len(file_list)} 条文件记录")
        except Exception as e:
            LogUtils.error(f"批量插入文件记录失败: {e}")

    def clear_file_index(self):
        """
        用途：清空当前文件索引表（file_index）
        入参说明：无
        返回值说明：bool - 是否执行成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM file_index')
            conn.commit()
            conn.close()
            LogUtils.info("已成功清空当前文件索引表")
            return True
        except Exception as e:
            LogUtils.error(f"清空当前文件索引表失败: {e}")
            return False

    def copy_to_history(self):
        """
        用途：将 file_index 的数据复制到 history_file_index。
              如果路径冲突，则更新历史表中的数据。
        入参说明：无
        返回值说明：bool - 是否执行成功
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # 将数据复制到历史表，使用 INSERT OR REPLACE 处理路径冲突
            cursor.execute('''
                INSERT OR REPLACE INTO history_file_index (file_path, file_name, file_md5, scan_time)
                SELECT file_path, file_name, file_md5, scan_time FROM file_index
            ''')
            conn.commit()
            conn.close()
            LogUtils.info("已成功将本次扫描结果复制到历史表")
            return True
        except Exception as e:
            LogUtils.error(f"复制索引到历史表失败: {e}")
            return False

db_manager = DBManager()
