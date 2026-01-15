import sqlite3
from abc import ABC
from typing import List, Any, Type, TypeVar, Optional

from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_manager import DBManager
from backend.model.pagination_result import PaginationResult

T = TypeVar('T')

class BaseDBProcessor(ABC):
    """
    用途：数据库处理器基类，定义数据库处理的通用接口
    """
    
    @staticmethod
    def _execute(query: str, params: tuple = (), is_query: bool = False,
                 fetch_one: bool = False, conn: Optional[sqlite3.Connection] = None) -> Any:
        """
        用途：通用的执行 SQL 语句方法
        """
        local_conn: bool = False
        if conn is None:
            conn = DBManager.get_connection()
            local_conn = True
            
        try:
            conn.row_factory = sqlite3.Row
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
                if local_conn:
                    conn.commit()
                return cursor.rowcount
        except Exception as e:
            LogUtils.error(f"SQL 执行失败: {query}, 错误: {e}")
            if local_conn and conn:
                conn.rollback()
            # 优化：重新抛出异常，让上层业务及 API 能够感知错误并返回 500
            raise e
        finally:
            if local_conn and conn:
                conn.close()

    @staticmethod
    def _execute_batch(query: str, data: List[tuple], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途：批量执行 SQL 语句
        """
        local_conn: bool = False
        if conn is None:
            conn = DBManager.get_connection()
            local_conn = True
            
        try:
            cursor = conn.cursor()
            cursor.executemany(query, data)
            if local_conn:
                conn.commit()
            return cursor.rowcount
        except Exception as e:
            LogUtils.error(f"批量执行失败: {query}, 错误: {e}")
            if local_conn and conn:
                conn.rollback()
            # 优化：重新抛出异常
            raise e
        finally:
            if local_conn and conn:
                conn.close()

    @staticmethod
    def _clear_table(table_name: str) -> bool:
        """
        用途：清空指定表并重置其自增主键序列
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
            default_sort_column: str,
            extra_where: str = "",
            extra_params: tuple = ()
    ) -> PaginationResult[T]:
        """
        用途：通用的分页查询逻辑封装
        入参说明：
            extra_where: 额外的过滤条件 (例如 "AND status = ?")
            extra_params: 额外过滤条件的参数
        """
        # 1. 处理搜索关键词：调用 Utils 工具类进行统一预处理
        sql_search_param: str = Utils.process_search_query(search_query)

        # 2. 校验排序字段
        if sort_by not in allowed_sort_columns:
            sort_by = default_sort_column
        
        order_str: str = "ASC" if order else "DESC"

        # 3. 分页计算
        offset: int = max(0, (page - 1) * limit)

        # 4. 总数查询
        count_query: str = f"SELECT COUNT(*) as total FROM {table_name} WHERE {search_column} LIKE ? {extra_where}"
        total_res = BaseDBProcessor._execute(count_query, (sql_search_param,) + extra_params, is_query=True, fetch_one=True)
        total: int = total_res['total'] if total_res else 0

        # 5. 列表查询
        list_query: str = f"""
            SELECT * FROM {table_name}
            WHERE {search_column} LIKE ? {extra_where}
            ORDER BY {sort_by} {order_str}
            LIMIT ? OFFSET ?
        """
        rows = BaseDBProcessor._execute(list_query, (sql_search_param,) + extra_params + (limit, offset), is_query=True)
        
        data_list: List[T] = [model_class(**row) for row in rows]

        return PaginationResult(
            total=total,
            list=data_list,
            page=page,
            limit=limit,
            sort_by=sort_by,
            order=order_str
        )
