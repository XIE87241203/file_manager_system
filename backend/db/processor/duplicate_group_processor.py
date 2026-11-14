import sqlite3
from typing import Any, List, Dict, Optional, Set

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.similarity_type import SimilarityType
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
                        f_model.file_path, 
                        f_model.similarity_type, 
                        f_model.similarity_rate
                    ))

                # 3. 批量插入该组的文件记录
                if files_data:
                    cursor.executemany(
                        f"INSERT INTO {DBConstants.DuplicateFile.TABLE_FILES} "
                        f"({DBConstants.DuplicateFile.COL_FILE_GROUP_ID}, "
                        f"{DBConstants.DuplicateFile.COL_FILE_PATH}, "
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
            LogUtils.error(t('db_execute_failed', query='batch_save_duplicate_groups', error=str(e)))
            return False
        finally:
            if local_conn and conn:
                conn.close()

    @staticmethod
    def delete_files_by_paths(file_paths: List[str], conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途：根据文件路径列表批量从重复文件记录中删除，并维护分组完整性
        入参说明：
            file_paths (List[str]): 待删除的文件完整路径列表
            conn (Optional[sqlite3.Connection]): 数据库连接对象（可选，用于事务支持）
        返回值说明：
            bool: 是否操作成功
        """
        if not file_paths:
            return True

        local_conn: bool = False
        if conn is None:
            conn = db_manager.get_connection()
            local_conn = True

        try:
            cursor: sqlite3.Cursor = conn.cursor()

            # 1. 查找这些文件涉及到的所有 group_id (为了后续维护分组完整性)
            placeholders: str = ','.join(['?'] * len(file_paths))
            cursor.execute(
                f"SELECT DISTINCT {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} "
                f"FROM {DBConstants.DuplicateFile.TABLE_FILES} "
                f"WHERE {DBConstants.DuplicateFile.COL_FILE_PATH} IN ({placeholders})",
                tuple(file_paths)
            )
            affected_groups: List[tuple] = cursor.fetchall()
            group_ids: List[int] = [row[0] for row in affected_groups]

            if not group_ids:
                return True

            # 2. 批量删除文件记录
            cursor.execute(
                f"DELETE FROM {DBConstants.DuplicateFile.TABLE_FILES} "
                f"WHERE {DBConstants.DuplicateFile.COL_FILE_PATH} IN ({placeholders})",
                tuple(file_paths)
            )

            # 3. 维护分组完整性：检查每个受影响的分组
            for group_id in group_ids:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {DBConstants.DuplicateFile.TABLE_FILES} "
                    f"WHERE {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} = ?",
                    (group_id,)
                )
                count: int = cursor.fetchone()[0]

                # 4. 若组内成员少于 2 个，则彻底清理该组
                if count < 2:
                    # 删除组内残留文件记录
                    cursor.execute(
                        f"DELETE FROM {DBConstants.DuplicateFile.TABLE_FILES} WHERE {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} = ?",
                        (group_id,)
                    )
                    # 删除分组记录
                    cursor.execute(
                        f"DELETE FROM {DBConstants.DuplicateGroup.TABLE_GROUPS} WHERE {DBConstants.DuplicateGroup.COL_GRP_ID_PK} = ?",
                        (group_id,)
                    )
                    LogUtils.info(t('dup_group_dissolved_log', id=group_id))

            if local_conn:
                conn.commit()
            return True
        except Exception as e:
            if local_conn and conn:
                conn.rollback()
            LogUtils.error(t('db_execute_failed', query='delete_files_by_paths', error=str(e)))
            return False
        finally:
            if local_conn and conn:
                conn.close()

    @staticmethod
    def _self_heal(conn: Optional[sqlite3.Connection] = None) -> None:
        """
        用途说明：核心数据库自愈逻辑，全表清理失效路径关联及解散成员不足 2 人的分组。
        流程说明：
            1. 使用子查询批量删除所有在 file_index 表中找不到 file_path 的重复记录。
            2. 使用 GROUP BY 识别出成员数量 < 2 的分组，并物理删除这些分组及其残余关联。
        入参说明：
            conn (Optional[sqlite3.Connection]): 可选数据库连接，用于支持事务嵌套。
        返回值说明：无
        """
        local_conn: bool = False
        if conn is None:
            conn = db_manager.get_connection()
            local_conn = True

        try:
            cursor: sqlite3.Cursor = conn.cursor()
            # 1. 清理孤儿文件关联（即 file_index 中已被删除的文件）
            cursor.execute(f"""
                DELETE FROM {DBConstants.DuplicateFile.TABLE_FILES}
                WHERE {DBConstants.DuplicateFile.COL_FILE_PATH} NOT IN (
                    SELECT {DBConstants.FileIndex.COL_FILE_PATH} FROM {DBConstants.FileIndex.TABLE_NAME}
                )
            """)

            # 2. 清理成员不足的分组（识别并解散）
            cursor.execute(f"""
                DELETE FROM {DBConstants.DuplicateGroup.TABLE_GROUPS}
                WHERE {DBConstants.DuplicateGroup.COL_GRP_ID_PK} NOT IN (
                    SELECT {DBConstants.DuplicateFile.COL_FILE_GROUP_ID}
                    FROM {DBConstants.DuplicateFile.TABLE_FILES}
                    GROUP BY {DBConstants.DuplicateFile.COL_FILE_GROUP_ID}
                    HAVING COUNT(*) >= 2
                )
            """)
            
            # 3. 同步清理 duplicate_files 中那些已经失去父分组的记录（防御性清理）
            cursor.execute(f"""
                DELETE FROM {DBConstants.DuplicateFile.TABLE_FILES}
                WHERE {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} NOT IN (
                    SELECT {DBConstants.DuplicateGroup.COL_GRP_ID_PK} FROM {DBConstants.DuplicateGroup.TABLE_GROUPS}
                )
            """)

            if local_conn:
                conn.commit()
        except Exception as e:
            if local_conn:
                conn.rollback()
            LogUtils.error(t('db_execute_failed', query='_self_heal', error=str(e)))
        finally:
            if local_conn:
                conn.close()

    @staticmethod
    def cleanup_invalid_results() -> None:
        """
        用途说明：清理失效的查重结果（删除文件索引中已不存在的关联，并解散成员不足 2 个的分组）。
        入参说明：无
        返回值说明：无
        """
        DuplicateGroupProcessor._self_heal()

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
            similarity_type: Optional[str] = None,
            file_type: Optional[str] = None
    ) -> PaginationResult[DuplicateGroupResult]:
        """
        用途说明：分页获取重复文件分组数据（基于先自愈后查询的优化方案）。
        流程说明：
            1. 调用 _self_heal() 进行全局自愈，确保数据库数据 100% 真实有效。
            2. 统计总数：由于数据已清理，直接统计即可获得准确的总条数。
            3. 分页查询：获取当前页的分组信息。
            4. 批量查询：获取所有成员详情（无需复杂的 LEFT JOIN 判断）。
            5. 返回封装：封装并返回分页结果。
        入参说明：
            page (int): 当前页码。
            limit (int): 每页条数。
            similarity_type (Optional[str]): 相似度类型。
            file_type (Optional[str]): 文件类型 (如 image, video)，按组内文件的实际类型筛选。
        返回值说明：
            PaginationResult[DuplicateGroupResult]: 清理后的准确分页结果。
        """
        # 1. 执行全表自愈，确保 total 计算前数据是干净的
        DuplicateGroupProcessor._self_heal()

        # 2. 构建筛选条件（相似度类型 / 文件类型），并统计准确的总分组数
        conditions: List[str] = []
        condition_params: List[Any] = []
        join_clause: str = ""
        if similarity_type:
            conditions.append(f"df.{DBConstants.DuplicateFile.COL_SIMILARITY_TYPE} = ?")
            condition_params.append(similarity_type)
        if file_type:
            join_clause = (
                f"INNER JOIN {DBConstants.FileIndex.TABLE_NAME} fi "
                f"ON fi.{DBConstants.FileIndex.COL_FILE_PATH} = df.{DBConstants.DuplicateFile.COL_FILE_PATH}"
            )
            conditions.append(f"fi.{DBConstants.FileIndex.COL_FILE_TYPE} = ?")
            condition_params.append(file_type)

        if conditions:
            where_clause: str = "WHERE " + " AND ".join(conditions)
            count_query: str = f"""
                SELECT COUNT(DISTINCT df.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID}) as total
                FROM {DBConstants.DuplicateFile.TABLE_FILES} df
                {join_clause}
                {where_clause}
            """
            count_res = BaseDBProcessor._execute(count_query, tuple(condition_params), is_query=True, fetch_one=True)
            total: int = count_res['total'] if count_res else 0
        else:
            total: int = DuplicateGroupProcessor.get_group_count()

        if total == 0:
            return PaginationResult(total=0, list=[], page=page, limit=limit, sort_by="", order="ASC")

        # 3. 分页查询分组列表
        offset: int = max(0, (page - 1) * limit)
        if conditions:
            group_query: str = f"""
                SELECT g.* FROM {DBConstants.DuplicateGroup.TABLE_GROUPS} g
                JOIN (
                    SELECT DISTINCT df.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID}
                    FROM {DBConstants.DuplicateFile.TABLE_FILES} df
                    {join_clause}
                    {where_clause}
                ) f ON g.{DBConstants.DuplicateGroup.COL_GRP_ID_PK} = f.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID}
                ORDER BY g.{DBConstants.DuplicateGroup.COL_GRP_CREATE_TIME} DESC
                LIMIT ? OFFSET ?
            """
            group_rows: List[dict] = BaseDBProcessor._execute(group_query, tuple(condition_params) + (limit, offset), is_query=True)
        else:
            group_query: str = f"""
                SELECT * FROM {DBConstants.DuplicateGroup.TABLE_GROUPS}
                ORDER BY {DBConstants.DuplicateGroup.COL_GRP_CREATE_TIME} DESC
                LIMIT ? OFFSET ?
            """
            group_rows: List[dict] = BaseDBProcessor._execute(group_query, (limit, offset), is_query=True)
        
        if not group_rows:
            return PaginationResult(total=total, list=[], page=page, limit=limit, sort_by="", order="ASC")

        # 4. 批量获取成员详情
        group_ids: List[int] = [row[DBConstants.DuplicateGroup.COL_GRP_ID_PK] for row in group_rows]
        placeholders: str = ','.join(['?'] * len(group_ids))
        
        file_query: str = f"""
            SELECT df.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID}, 
                   df.{DBConstants.DuplicateFile.COL_SIMILARITY_TYPE},
                   df.{DBConstants.DuplicateFile.COL_SIMILARITY_RATE},
                   fi.* 
            FROM {DBConstants.FileIndex.TABLE_NAME} fi
            INNER JOIN {DBConstants.DuplicateFile.TABLE_FILES} df 
            ON fi.{DBConstants.FileIndex.COL_FILE_PATH} = df.{DBConstants.DuplicateFile.COL_FILE_PATH}
            WHERE df.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID} IN ({placeholders})
        """
        all_file_rows: List[dict] = BaseDBProcessor._execute(file_query, tuple(group_ids), is_query=True)

        # 5. 组织数据
        group_files_map: Dict[int, List[DuplicateFileResult]] = {}
        for f_row in all_file_rows:
            gid: int = f_row.pop(DBConstants.DuplicateFile.COL_FILE_GROUP_ID)
            sim_type: str = f_row.pop(DBConstants.DuplicateFile.COL_SIMILARITY_TYPE)
            sim_rate: float = f_row.pop(DBConstants.DuplicateFile.COL_SIMILARITY_RATE)
            
            file_info: FileIndexDBModel = FileIndexDBModel(**f_row)
            if gid not in group_files_map:
                group_files_map[gid] = []
            group_files_map[gid].append(DuplicateFileResult(
                file_info=file_info,
                similarity_type=sim_type or SimilarityType.MD5,
                similarity_rate=sim_rate if sim_rate is not None else 1.0
            ))

        # 6. 封装返回
        results: List[DuplicateGroupResult] = []
        for g_row in group_rows:
            group_id: int = g_row[DBConstants.DuplicateGroup.COL_GRP_ID_PK]
            results.append(DuplicateGroupResult(
                id=group_id,
                group_name=g_row[DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME],
                create_time=g_row[DBConstants.DuplicateGroup.COL_GRP_CREATE_TIME],
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

    @staticmethod
    def get_last_check_time() -> Optional[str]:
        """
        用途说明：获取最近一次查重完成的时间点（用于新增查重判断新索引文件）。
        入参说明：无
        返回值说明：Optional[str]: 时间字符串，若从未查重则返回 None。
        """
        query: str = (
            f"SELECT {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_TIME} "
            f"FROM {DBConstants.DuplicateCheckMeta.TABLE_NAME} "
            f"WHERE {DBConstants.DuplicateCheckMeta.COL_ID} = 1"
        )
        row: Optional[dict] = BaseDBProcessor._execute(query, (), is_query=True, fetch_one=True)
        if row:
            return row[DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_TIME]
        return None

    @staticmethod
    def set_last_check_time(check_time: str, duration_seconds: float = 0.0) -> bool:
        """
        用途说明：记录最近一次查重完成的时间点与耗时（固定使用 id=1 的单行记录）。
        入参说明：
            check_time (str): 查重完成时间字符串。
            duration_seconds (float): 本次查重耗时（秒）。
        返回值说明：bool: 是否成功。
        """
        query: str = f"""
            INSERT INTO {DBConstants.DuplicateCheckMeta.TABLE_NAME} (
                {DBConstants.DuplicateCheckMeta.COL_ID},
                {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_TIME},
                {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_DURATION}
            )
            VALUES (1, ?, ?)
            ON CONFLICT({DBConstants.DuplicateCheckMeta.COL_ID}) DO UPDATE SET
                {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_TIME} = EXCLUDED.{DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_TIME},
                {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_DURATION} = EXCLUDED.{DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_DURATION}
        """
        result: int = BaseDBProcessor._execute(query, (check_time, duration_seconds))
        return result is not None and result > 0

    @staticmethod
    def get_last_check_duration() -> Optional[float]:
        """
        用途说明：获取最近一次查重的耗时（秒）。
        入参说明：无
        返回值说明：Optional[float]: 耗时秒数，若从未查重则返回 None。
        """
        query: str = (
            f"SELECT {DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_DURATION} "
            f"FROM {DBConstants.DuplicateCheckMeta.TABLE_NAME} "
            f"WHERE {DBConstants.DuplicateCheckMeta.COL_ID} = 1"
        )
        row: Optional[dict] = BaseDBProcessor._execute(query, (), is_query=True, fetch_one=True)
        if row and row[DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_DURATION] is not None:
            return float(row[DBConstants.DuplicateCheckMeta.COL_LAST_CHECK_DURATION])
        return None

    @staticmethod
    def save_incremental_results(groups: List[DuplicateGroupDBModel], new_file_paths: List[str]) -> bool:
        """
        用途说明：保存新增查重结果。仅保留涉及新文件的分组，并用其取代受影响的旧分组（事务保证原子性）。
        流程说明：
            1. 从所有分组中筛选出至少包含一个新文件的候选分组。
            2. 收集候选分组涉及的全部文件路径，删除与之关联的旧分组（这些分组将被重新计算的结果取代）。
            3. 插入候选分组及其成员详情。
        入参说明：
            groups (List[DuplicateGroupDBModel]): 查重器产出的全部分组。
            new_file_paths (List[str]): 本次新增查重的新文件路径列表。
        返回值说明：bool: 是否成功保存。
        """
        new_set: Set[str] = set(new_file_paths)
        candidates: List[DuplicateGroupDBModel] = [
            g for g in groups if any(f.file_path in new_set for f in g.files)
        ]

        affected_paths: Set[str] = set()
        for group in candidates:
            for f in group.files:
                affected_paths.add(f.file_path)

        try:
            with db_manager.transaction() as conn:
                cursor: sqlite3.Cursor = conn.cursor()

                # 1. 删除受影响的旧分组（先删成员关联，再删分组）
                if affected_paths:
                    placeholders: str = ','.join(['?'] * len(affected_paths))
                    cursor.execute(
                        f"SELECT DISTINCT {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} "
                        f"FROM {DBConstants.DuplicateFile.TABLE_FILES} "
                        f"WHERE {DBConstants.DuplicateFile.COL_FILE_PATH} IN ({placeholders})",
                        tuple(affected_paths)
                    )
                    affected_group_ids: List[int] = [row[0] for row in cursor.fetchall()]
                    if affected_group_ids:
                        group_placeholders: str = ','.join(['?'] * len(affected_group_ids))
                        cursor.execute(
                            f"DELETE FROM {DBConstants.DuplicateFile.TABLE_FILES} "
                            f"WHERE {DBConstants.DuplicateFile.COL_FILE_GROUP_ID} IN ({group_placeholders})",
                            tuple(affected_group_ids)
                        )
                        cursor.execute(
                            f"DELETE FROM {DBConstants.DuplicateGroup.TABLE_GROUPS} "
                            f"WHERE {DBConstants.DuplicateGroup.COL_GRP_ID_PK} IN ({group_placeholders})",
                            tuple(affected_group_ids)
                        )

                # 2. 插入候选分组及其成员详情
                for group in candidates:
                    cursor.execute(
                        f"INSERT INTO {DBConstants.DuplicateGroup.TABLE_GROUPS} "
                        f"({DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME}) VALUES (?)",
                        (group.group_name,)
                    )
                    group_id: int = cursor.lastrowid
                    files_data: List[tuple] = [
                        (group_id, f.file_path, f.similarity_type, f.similarity_rate)
                        for f in group.files
                    ]
                    if files_data:
                        cursor.executemany(
                            f"INSERT INTO {DBConstants.DuplicateFile.TABLE_FILES} "
                            f"({DBConstants.DuplicateFile.COL_FILE_GROUP_ID}, "
                            f"{DBConstants.DuplicateFile.COL_FILE_PATH}, "
                            f"{DBConstants.DuplicateFile.COL_SIMILARITY_TYPE}, "
                            f"{DBConstants.DuplicateFile.COL_SIMILARITY_RATE}) "
                            f"VALUES (?, ?, ?, ?)",
                            files_data
                        )
            return True
        except Exception as e:
            LogUtils.error(t('db_execute_failed', query='save_incremental_results', error=str(e)))
            return False
