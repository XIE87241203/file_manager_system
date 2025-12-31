from typing import List, Tuple, Optional, Union
from backend.db.db_manager import db_manager, DBManager
from backend.common.log_utils import LogUtils
from dataclasses import asdict

from backend.db.model.file_index import FileIndex
from backend.db.model.history_file_index import HistoryFileIndex


class DBOperations:
    """
    用途：数据库操作类，负责所有数据的增删改查业务逻辑
    """
    
    @staticmethod
    def __execute_query(query: str, params: tuple = ()) -> List[Tuple]:
        """
        用途：执行查询语句（SELECT）- 私有方法
        入参说明：
            query (str): SQL 语句
            params (tuple): 参数元组
        返回值说明：
            List[Tuple]: 查询结果列表（原始元组格式）
        """
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            conn.close()
            return result
        except Exception as e:
            LogUtils.error(f"查询失败: {query}, 错误: {e}")
            return []

    @staticmethod
    def __execute_update(query: str, params: tuple = ()) -> int:
        """
        用途：执行更新语句（INSERT, UPDATE, DELETE）- 私有方法
        入参说明：
            query (str): SQL 语句
            params (tuple): 参数元组
        返回值说明：
            int: 受影响的行数
        """
        try:
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            rowcount = cursor.rowcount
            conn.close()
            return rowcount
        except Exception as e:
            LogUtils.error(f"执行更新失败: {query}, 错误: {e}")
            return 0

    @staticmethod
    def batch_insert_files(file_list: List[FileIndex]) -> None:
        """
        用途：批量插入或更新文件索引信息到 file_index 表
        入参说明：
            file_list (List[FileIndex]): FileIndex 对象列表
        返回值说明：
            None
        """
        if not file_list:
            return
            
        try:
            # 提取对象中的数据为元组列表
            data = [(f.file_path, f.file_name, f.file_md5) for f in file_list]
            
            conn = db_manager.get_connection()
            cursor = conn.cursor()
            cursor.executemany(f'''
                INSERT OR REPLACE INTO {DBManager.TABLE_FILE_INDEX} (file_path, file_name, file_md5, scan_time)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', data)
            conn.commit()
            conn.close()
            LogUtils.info(f"成功更新 {len(file_list)} 条文件记录")
        except Exception as e:
            LogUtils.error(f"批量插入文件记录失败: {e}")

    @staticmethod
    def clear_file_index() -> bool:
        """
        用途：清空当前文件索引表（file_index）
        入参说明：无
        返回值说明：
            bool: 是否执行成功
        """
        try:
            DBOperations.__execute_update(f'DELETE FROM {DBManager.TABLE_FILE_INDEX}')
            DBOperations.__execute_update(f"DELETE FROM sqlite_sequence WHERE name='{DBManager.TABLE_FILE_INDEX}'")
            LogUtils.info("已成功清空当前文件索引表及自增序列")
            return True
        except Exception as e:
            LogUtils.error(f"清空当前文件索引表失败: {e}")
            return False

    @staticmethod
    def clear_history_index() -> bool:
        """
        用途：清空历史文件索引表（history_file_index）
        入参说明：无
        返回值说明：
            bool: 是否执行成功
        """
        try:
            DBOperations.__execute_update(f'DELETE FROM {DBManager.TABLE_HISTORY_INDEX}')
            DBOperations.__execute_update(f"DELETE FROM sqlite_sequence WHERE name='{DBManager.TABLE_HISTORY_INDEX}'")
            LogUtils.info("已成功清空历史文件索引表及自增序列")
            return True
        except Exception as e:
            LogUtils.error(f"清空历史文件索引表失败: {e}")
            return False

    @staticmethod
    def copy_to_history() -> bool:
        """
        用途：将 file_index 的数据复制到 history_file_index
        入参说明：无
        返回值说明：
            bool: 是否执行成功
        """
        try:
            query = f'''
                INSERT OR REPLACE INTO {DBManager.TABLE_HISTORY_INDEX} (file_path, file_name, file_md5, scan_time)
                SELECT file_path, file_name, file_md5, scan_time FROM {DBManager.TABLE_FILE_INDEX}
            '''
            DBOperations.__execute_update(query)
            LogUtils.info("已成功将本次扫描结果复制到历史表")
            return True
        except Exception as e:
            LogUtils.error(f"复制索引到历史表失败: {e}")
            return False

    @staticmethod
    def get_duplicate_md5s() -> List[Tuple[str, int]]:
        """
        用途：获取数据库中 MD5 重复的分组信息
        入参说明：无
        返回值说明：
            List[Tuple[str, int]]: 包含 (file_md5, count) 的列表
        """
        query = f"SELECT file_md5, COUNT(*) as count FROM {DBManager.TABLE_FILE_INDEX} GROUP BY file_md5 HAVING count > 1"
        return DBOperations.__execute_query(query)

    @staticmethod
    def get_files_by_md5(md5: str) -> List[FileIndex]:
        """
        用途：根据 MD5 获取文件详情列表
        入参说明：
            md5 (str): 文件的 MD5 哈希值
        返回值说明：
            List[FileIndex]: FileIndex 对象列表
        """
        query = f"SELECT id, file_path, file_name, file_md5, scan_time FROM {DBManager.TABLE_FILE_INDEX} WHERE file_md5 = ?"
        rows = DBOperations.__execute_query(query, (md5,))
        return [FileIndex(id=r[0], file_path=r[1], file_name=r[2], file_md5=r[3], scan_time=r[4]) for r in rows]

    @staticmethod
    def delete_file_index_by_path(file_path: str) -> int:
        """
        用途：从当前文件索引表中根据路径删除记录
        入参说明：
            file_path (str): 文件的绝对路径
        返回值说明：
            int: 受影响的行数
        """
        query = f"DELETE FROM {DBManager.TABLE_FILE_INDEX} WHERE file_path = ?"
        return DBOperations.__execute_update(query, (file_path,))

    @staticmethod
    def get_file_list_with_pagination(
        table_name: str, 
        where_clause: str = "", 
        params: tuple = (), 
        sort_by: str = "scan_time", 
        order: str = "DESC", 
        limit: int = 100, 
        offset: int = 0
    ) -> List[Union[FileIndex, HistoryFileIndex]]:
        """
        用途：通用分页获取文件列表
        入参说明：
            table_name (str): 表名
            where_clause (str): 过滤条件语句
            params (tuple): 过滤参数
            sort_by (str): 排序字段
            order (str): 排序顺序 (ASC/DESC)
            limit (int): 限制数量
            offset (int): 偏移量
        返回值说明：
            List[Union[FileIndex, HistoryFileIndex]]: FileIndex 或 HistoryFileIndex 对象列表
        """
        query = f"SELECT id, file_path, file_name, file_md5, scan_time FROM {table_name} {where_clause} ORDER BY {sort_by} {order} LIMIT ? OFFSET ?"
        full_params = list(params) + [limit, offset]
        rows = DBOperations.__execute_query(query, tuple(full_params))
        
        # 根据表名选择返回的数据类
        model_cls = HistoryFileIndex if table_name == DBManager.TABLE_HISTORY_INDEX else FileIndex
        return [model_cls(id=r[0], file_path=r[1], file_name=r[2], file_md5=r[3], scan_time=r[4]) for r in rows]

    @staticmethod
    def get_file_count(table_name: str, where_clause: str = "", params: tuple = ()) -> int:
        """
        用途：获取表中的记录总数
        入参说明：
            table_name (str): 表名
            where_clause (str): 过滤条件
            params (tuple): 参数
        返回值说明：
            int: 总数
        """
        query = f"SELECT COUNT(*) FROM {table_name} {where_clause}"
        res = DBOperations.__execute_query(query, params)
        return res[0][0] if res else 0

    @staticmethod
    def get_paths_by_md5(md5: str) -> List[str]:
        """
        用途：根据 MD5 获取所有相关的文件路径
        入参说明：
            md5 (str): 文件的 MD5 哈希值
        返回值说明：
            List[str]: 包含路径的字符串列表
        """
        query = f"SELECT file_path FROM {DBManager.TABLE_FILE_INDEX} WHERE file_md5 = ?"
        rows = DBOperations.__execute_query(query, (md5,))
        return [r[0] for r in rows]
