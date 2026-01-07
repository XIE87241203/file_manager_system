from abc import ABC, abstractmethod
import sqlite3

from backend.common.log_utils import LogUtils
from backend.db.db_manager import db_manager
from typing import List, Any


class BaseDBProcessor(ABC):
    """
    用途：数据库处理器基类，定义数据库处理的通用接口
    """

    @abstractmethod
    def create_table(self, conn: sqlite3.Connection) -> None:
        """
        用途：创建数据库表（抽象方法，由子类实现具体建表逻辑）
        入参说明：
            conn: sqlite3.Connection 数据库连接对象
        返回值说明：无
        """
        pass

    # --- 私有辅助方法 ---
    @staticmethod
    def _execute(query: str, params: tuple = (), is_query: bool = False,
                 fetch_one: bool = False) -> Any:
        """
        用途：通用的执行 SQL 语句方法
        入参说明：
            query (str): SQL 语句
            params (tuple): 参数元组
            is_query (bool): 是否为查询操作
            fetch_one (bool): 是否仅获取单条记录
        返回值说明：
            Any: 查询结果（列表或字典）或受影响的行数
        """
        conn = None
        try:
            conn = db_manager.get_connection()
            conn.row_factory = sqlite3.Row  # 启用字段名访问
            cursor = conn.cursor()
            cursor.execute(query, params)

            if is_query:
                if fetch_one:
                    row = cursor.fetchone()
                    return dict(row) if row else None
                else:
                    rows = cursor.fetchall()
                    return [dict(r) for r in rows]
            else:
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            LogUtils.error(f"SQL 执行失败: {query}, 错误: {e}")
            return [] if is_query and not fetch_one else (None if fetch_one else 0)
        finally:
            if conn:
                conn.close()

    @staticmethod
    def _execute_batch(query: str, data: List[tuple]) -> int:
        """
        用途：批量执行 SQL 语句（用于高效插入）
        入参说明：
            query (str): SQL 语句
            data (List[tuple]): 待插入的数据元组列表
        返回值说明：
            int: 受影响的总行数
        """
        conn = None
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.executemany(query, data)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            LogUtils.error(f"批量执行失败: {query}, 错误: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    @staticmethod
    def _clear_table(table_name: str) -> bool:
        """
        用途：清空指定表并重置其自增主键序列
        入参说明：
            table_name (str): 表名
        返回值说明：
            bool: 是否成功
        """
        BaseDBProcessor._execute(f'DELETE FROM {table_name}')
        BaseDBProcessor._execute("DELETE FROM sqlite_sequence WHERE name=?", (table_name,))
        LogUtils.info(f"表 {table_name} 已清空")
        return True
