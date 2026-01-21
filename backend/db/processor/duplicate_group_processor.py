import sqlite3
from typing import List, Dict, Optional

from backend.common.log_utils import LogUtils
from backend.db.db_constants import DBConstants
from backend.db.db_manager import db_manager
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.duplicate_group_result import DuplicateGroupResult, DuplicateFileResult
from backend.model.pagination_result import PaginationResult


class DuplicateGroupProcessor(BaseDBProcessor):
    """
    用途：重复文件分组数据库处理器，负责 duplicate_groups 和 duplicate_files 表的相关操作
    """

    @staticmethod
    def batch_save_duplicate_groups(groups: List[DuplicateGroupDBModel], conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途：批量存储重复文件分组及其详情，记录相似类型和相似率
        入参说明：
            groups (List[DuplicateGroupDBModel]): 重复文件分组模型列表
            conn (Optional[sqlite3.Connection]): 数据库连接对象（可选，用于事务支持）
        返回值说明：
            bool: 是否全部成功存储
        """
        local_conn: bool = False
        if conn is None:
            conn = db_manager.get_connection()
            local_conn = True

        try:
            cursor = conn.cursor()

            for group in groups:
                # 1. 插入分组并获取生成的组 ID
                cursor.execute(
                    f"INSERT INTO {DBConstants.DuplicateGroup.TABLE_GROUPS} ({DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME}) VALUES (?)",
                    (group.group_name,)
                )
                group_id: int = cursor.lastrowid

                # 2. 准备该组的文件详情数据
                files_data: List[tuple] = []
                
                # 使用 files 列表（包含相似度信息）
                for f_model in group.files:
                    files_data.append((
                        group_id, 
                        f_model.file_id, 
                        f_model.similarity_type, 
                        f_model.similarity_rate
                    ))

                # 3. 批量插入该组的文件记录
                if files_data:
                    cursor.executemany(
                        f"INSERT INTO {DBConstants.DuplicateFile.TABLE_FILES} "
                        f"({DBConstants.DuplicateFile.COL_FILE_GROUP_ID}, "
                        f"{DBConstants.DuplicateFile.COL_FILE_ID}, "
                        f"{DBConstants.DuplicateFile.COL_SIMILARITY_TYPE}, "
                        f"{DBConstants.DuplicateFile.COL_SIMILARITY_RATE}) "
                        f"VALUES (?, ?, ?, ?)",
                        files_data
                    )

            if local_conn:
                conn.commit()
            return True
        except Exception as e:
            if local_conn and conn:
                conn.rollback()
            LogUtils.error(f"批量存储重复分组失败: {e}")
            return False
        finally:
            if local_conn and conn:
                conn.close()

    @staticmethod
    def delete_file_by_id(file_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途：根据 ID 从重复文件记录中删除，并维护分组完整性
        入参说明：
            file_id (int): 记录的唯一标识 ID
            conn (Optional[sqlite3.Connection]): 数据库连接对象（可选，用于事务支持）
        返回值说明：
            bool: 是否操作成功
        """
        local_conn: bool = False
        if conn is None:
            conn = db_manager.get_connection()
            local_conn = True

        try:
            cursor = conn.cursor()

            # 2. 查询该文件所属的 group_id
            cursor.execute(
                f"SELECT {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} FROM {DBConstants.DuplicateFile.TABLE_FILES} "
                f"WHERE {DBConstants.DuplicateFile.COL_FILE_ID} = ?",
                (file_id,)
            )
            row = cursor.fetchone()
            if not row:
                # 不在查重结果中，视为成功（幂等性）
                return True

            group_id: int = row[0]

            # 3. 从重复文件中删除该记录
            cursor.execute(
                f"DELETE FROM {DBConstants.DuplicateFile.TABLE_FILES} WHERE {DBConstants.DuplicateFile.COL_FILE_ID} = ?",
                (file_id,)
            )

            # 4. 检查组内剩余文件数量
            cursor.execute(
                f"SELECT COUNT(*) FROM {DBConstants.DuplicateFile.TABLE_FILES} WHERE {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} = ?",
                (group_id,)
            )
            count: int = cursor.fetchone()[0]

            # 5. 若少于2个文件，则解散分组
            if count < 2:
                # 删除组内剩余的文件记录
                cursor.execute(
                    f"DELETE FROM {DBConstants.DuplicateFile.TABLE_FILES} WHERE {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} = ?",
                    (group_id,)
                )
                # 删除分组记录
                cursor.execute(
                    f"DELETE FROM {DBConstants.DuplicateGroup.TABLE_GROUPS} WHERE {DBConstants.DuplicateGroup.COL_GRP_ID_PK} = ?",
                    (group_id,)
                )
                LogUtils.info(f"由于成员不足2个，已自动解散重复分组 ID: {group_id}")

            if local_conn:
                conn.commit()
            return True
        except Exception as e:
            if local_conn and conn:
                conn.rollback()
            LogUtils.error(f"根据 ID 删除重复记录失败: {e}")
            return False
        finally:
            if local_conn and conn:
                conn.close()

    @staticmethod
    def clear_all_table() -> bool:
        """
        用途：清空重复文件相关的两张表
        入参说明：无
        返回值说明：
            bool: 是否清空成功
        """
        result_clear_groups: bool = BaseDBProcessor._clear_table(DBConstants.DuplicateGroup.TABLE_GROUPS)
        result_clear_files: bool = BaseDBProcessor._clear_table(DBConstants.DuplicateFile.TABLE_FILES)
        return result_clear_groups and result_clear_files

    @staticmethod
    def get_duplicate_groups_paged(
            page: int,
            limit: int,
            similarity_type: Optional[str] = None
    ) -> PaginationResult[DuplicateGroupResult]:
        """
        用途：分页获取重复文件分组数据（已优化：通过批量查询避免 N+1 问题）
        入参说明：
            page (int): 当前页码
            limit (int): 每页展示的分组条数
            similarity_type (Optional[str]): 筛选相似度类型 (如 'md5', 'hash', 'video_feature')
        返回值说明：
            PaginationResult[DuplicateGroupResult]: 包含分组及其文件列表的分页结果对象
        """
        # 1. 查询总分组数（如果有筛选，需要按筛选条件计数）
        if similarity_type:
            count_query: str = f"""
                SELECT COUNT(DISTINCT {DBConstants.DuplicateFile.COL_FILE_GROUP_ID}) as total 
                FROM {DBConstants.DuplicateFile.TABLE_FILES}
                WHERE {DBConstants.DuplicateFile.COL_SIMILARITY_TYPE} = ?
            """
            count_res = BaseDBProcessor._execute(count_query, (similarity_type,), is_query=True, fetch_one=True)
            total: int = count_res['total'] if count_res else 0
        else:
            total: int = DuplicateGroupProcessor.get_group_count()

        if total == 0:
            return PaginationResult(total=0, list=[], page=page, limit=limit, sort_by="", order="ASC")

        # 2. 分页查询分组列表
        offset: int = max(0, (page - 1) * limit)
        if similarity_type:
            group_query: str = f"""
                SELECT g.* FROM {DBConstants.DuplicateGroup.TABLE_GROUPS} g
                JOIN (
                    SELECT DISTINCT {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} 
                    FROM {DBConstants.DuplicateFile.TABLE_FILES} 
                    WHERE {DBConstants.DuplicateFile.COL_SIMILARITY_TYPE} = ?
                ) f ON g.{DBConstants.DuplicateGroup.COL_GRP_ID_PK} = f.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID}
                LIMIT ? OFFSET ?
            """
            group_rows: List[dict] = BaseDBProcessor._execute(group_query, (similarity_type, limit, offset), is_query=True)
        else:
            group_query: str = f"""
                SELECT * FROM {DBConstants.DuplicateGroup.TABLE_GROUPS}
                LIMIT ? OFFSET ?
            """
            group_rows: List[dict] = BaseDBProcessor._execute(group_query, (limit, offset), is_query=True)
        
        if not group_rows:
            return PaginationResult(total=total, list=[], page=page, limit=limit, sort_by="", order="ASC")

        # 3. 提取所有组 ID，并批量查询这些组关联的所有文件
        group_ids: List[int] = [row[DBConstants.DuplicateGroup.COL_GRP_ID_PK] for row in group_rows]
        placeholders: str = ','.join(['?'] * len(group_ids))
        
        file_query: str = f"""
            SELECT df.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID}, 
                   df.{DBConstants.DuplicateFile.COL_SIMILARITY_TYPE},
                   df.{DBConstants.DuplicateFile.COL_SIMILARITY_RATE},
                   fi.* 
            FROM {DBConstants.FileIndex.TABLE_NAME} fi
            JOIN {DBConstants.DuplicateFile.TABLE_FILES} df 
            ON fi.{DBConstants.FileIndex.COL_ID} = df.{DBConstants.DuplicateFile.COL_FILE_ID}
            WHERE df.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID} IN ({placeholders})
        """
        all_file_rows: List[dict] = BaseDBProcessor._execute(file_query, tuple(group_ids), is_query=True)

        # 4. 按 group_id 组织文件数据
        group_files_map: Dict[int, List[DuplicateFileResult]] = {}
        for f_row in all_file_rows:
            gid: int = f_row.pop(DBConstants.DuplicateFile.COL_FILE_GROUP_ID)
            # 获取相似度信息
            sim_type: str = f_row.pop(DBConstants.DuplicateFile.COL_SIMILARITY_TYPE)
            sim_rate: float = f_row.pop(DBConstants.DuplicateFile.COL_SIMILARITY_RATE)
            
            # 剩余字段构建文件模型
            file_info: FileIndexDBModel = FileIndexDBModel(**f_row)
            
            if gid not in group_files_map:
                group_files_map[gid] = []
            
            group_files_map[gid].append(DuplicateFileResult(
                file_info=file_info,
                similarity_type=sim_type or DBConstants.SimilarityType.MD5,
                similarity_rate=sim_rate if sim_rate is not None else 1.0
            ))

        # 5. 封装结果
        results: List[DuplicateGroupResult] = []
        for g_row in group_rows:
            group_id: int = g_row[DBConstants.DuplicateGroup.COL_GRP_ID_PK]
            results.append(DuplicateGroupResult(
                id=group_id,
                group_name=g_row[DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME],
                files=group_files_map.get(group_id, [])
            ))

        return PaginationResult(
            total=total,
            list=results,
            page=page,
            limit=limit,
            sort_by="",
            order="ASC"
        )

    @staticmethod
    def get_group_count() -> int:
        """
        用途：获取重复分组总数
        返回值说明：int: 重复分组总数
        """
        count_query: str = f"SELECT COUNT(*) as total FROM {DBConstants.DuplicateGroup.TABLE_GROUPS}"
        count_res: Optional[dict] = BaseDBProcessor._execute(count_query, (), is_query=True, fetch_one=True)
        return count_res['total'] if count_res else 0
