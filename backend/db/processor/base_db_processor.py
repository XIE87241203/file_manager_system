from abc import ABC, abstractmethod
import sqlite3
from typing import List, Any, Type, TypeVar, Generic, Optional

from backend.common.log_utils import LogUtils
from backend.db.db_manager import db_manager
from backend.model.pagination_result import PaginationResult
from backend.setting.setting_service import settingService

T = TypeVar('T')

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

    @staticmethod
    def _search_paged_list(
            table_name: str,
            model_class: Type[T],
            page: int,
            limit: int,
            sort_by: str,
            order: bool,
            search_query: str,
            search_column: str,
            allowed_sort_columns: List[str],
            default_sort_column: str
    ) -> PaginationResult[T]:
        """
        用途：通用的分页查询逻辑封装
        入参说明：
            table_name (str): 表名
            model_class (Type[T]): 结果转换的目标类
            page (int): 当前页码
            limit (int): 每页大小
            sort_by (str): 排序字段
            order (bool): 排序方向 (True 为 ASC)
            search_query (str): 搜索文本
            search_column (str): 搜索匹配的列
            allowed_sort_columns (List[str]): 允许排序的列列表
            default_sort_column (str): 默认排序字段
        返回值说明：
            PaginationResult[T]: 分页结果对象
        """
        # 1. 处理搜索关键词
        search_replace_chars = settingService.get_config().file_repository.search_replace_chars
        processed_query = search_query
        if processed_query:
            for char in search_replace_chars:
                if char:
                    processed_query = processed_query.replace(char, '%')
            sql_search_param = f"%{processed_query}%"
        else:
            sql_search_param = "%"

        # 2. 校验排序字段
        if sort_by not in allowed_sort_columns:
            sort_by = default_sort_column
        
        order_str = "ASC" if order else "DESC"

        # 3. 分页计算
        offset = max(0, (page - 1) * limit)

        # 4. 总数查询
        count_query = f"SELECT COUNT(*) as total FROM {table_name} WHERE {search_column} LIKE ?"
        total_res = BaseDBProcessor._execute(count_query, (sql_search_param,), is_query=True, fetch_one=True)
        total = total_res['total'] if total_res else 0

        # 5. 列表查询
        list_query = f"""
            SELECT * FROM {table_name}
            WHERE {search_column} LIKE ?
            ORDER BY {sort_by} {order_str}
            LIMIT ? OFFSET ?
        """
        rows = BaseDBProcessor._execute(list_query, (sql_search_param, limit, offset), is_query=True)
        
        data_list = [model_class(**row) for row in rows]

        return PaginationResult(
            total=total,
            list=data_list,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order_str
        )
