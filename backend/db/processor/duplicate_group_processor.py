from typing import List

from backend.common.log_utils import LogUtils
from backend.db.db_constants import DBConstants
from backend.db.db_manager import DBManager
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModule
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.duplicate_group_result import DuplicateGroupResult
from backend.model.pagination_result import PaginationResult


class DuplicateGroupDBModuleProcessor(BaseDBProcessor):
    """
    用途：重复文件分组数据库处理器，负责 duplicate_groups 和 duplicate_files 表的相关操作
    """

    @staticmethod
    def batch_save_duplicate_groups(groups: List[DuplicateGroupDBModule]) -> bool:
        """
        用途：批量存储重复文件分组及其详情
        入参说明：
            groups (List[DuplicateGroupDBModule]): 重复文件分组模型列表
        返回值说明：
            bool: 是否全部成功存储
        """
        conn = None
        try:
            conn = DBManager.get_connection()
            cursor = conn.cursor()

            for group in groups:
                # 1. 插入分组并获取生成的组 ID
                cursor.execute(
                    f"INSERT INTO {DBConstants.DuplicateGroup.TABLE_GROUPS} ({DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME}) VALUES (?)",
                    (group.group_name,)
                )
                group_id: int = cursor.lastrowid

                # 2. 准备该组的文件详情数据
                files_data: List[tuple] = [(group_id, file_id) for file_id in group.file_ids]

                # 3. 批量插入该组的文件记录
                if files_data:
                    cursor.executemany(
                        f"INSERT INTO {DBConstants.DuplicateFile.TABLE_FILES} "
                        f"({DBConstants.DuplicateFile.COL_FILE_GROUP_ID}, {DBConstants.DuplicateFile.COL_FILE_ID}) "
                        f"VALUES (?, ?)",
                        files_data
                    )

            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            LogUtils.error(f"批量存储重复分组失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def delete_file_by_id(file_id: int) -> bool:
        """
        用途：根据 ID 从重复文件记录中删除，并维护分组完整性
        入参说明：
            file_id (int): 记录的唯一标识 ID
        返回值说明：
            bool: 是否操作成功
        """
        conn = None
        try:
            conn = DBManager.get_connection()
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

            conn.commit()
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            LogUtils.error(f"根据 ID 删除重复记录失败: {e}")
            return False
        finally:
            if conn:
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
            limit: int
    ) -> PaginationResult[DuplicateGroupResult]:
        """
        用途：分页获取重复文件分组数据，并关联查询每组包含的文件详细索引信息。
        入参说明：
            page (int): 当前页码
            limit (int): 每页展示的分组条数
        返回值说明：
            PaginationResult[DuplicateGroupResult]: 包含分组及其文件列表的分页结果对象
        """
        # 1. 查询总分组数
        count_query: str = f"SELECT COUNT(*) as total FROM {DBConstants.DuplicateGroup.TABLE_GROUPS}"
        count_res: Optional[dict] = BaseDBProcessor._execute(count_query, (), is_query=True, fetch_one=True)
        total: int = count_res['total'] if count_res else 0

        # 2. 分页查询分组列表
        offset: int = max(0, (page - 1) * limit)
        group_query: str = f"""
            SELECT * FROM {DBConstants.DuplicateGroup.TABLE_GROUPS}
            LIMIT ? OFFSET ?
        """
        group_rows: List[dict] = BaseDBProcessor._execute(group_query, (limit, offset), is_query=True)

        results: List[DuplicateGroupResult] = []

        # 3. 遍历分组，获取每个分组下的所有文件详情
        for g_row in group_rows:
            group_id: int = g_row[DBConstants.DuplicateGroup.COL_GRP_ID_PK]
            group_name: str = g_row[DBConstants.DuplicateGroup.COL_GRP_GROUP_NAME]

            # 联合查询 duplicate_files 和 file_index 获取文件详情
            file_query: str = f"""
                SELECT fi.* FROM {DBConstants.FileIndex.TABLE_NAME} fi
                JOIN {DBConstants.DuplicateFile.TABLE_FILES} df 
                ON fi.{DBConstants.FileIndex.COL_ID} = df.{DBConstants.DuplicateFile.COL_FILE_ID}
                WHERE df.{DBConstants.DuplicateFile.COL_FILE_GROUP_ID} = ?
            """
            file_rows: List[dict] = BaseDBProcessor._execute(file_query, (group_id,), is_query=True)

            # 将查询结果转换为 FileIndexDBModel 对象列表
            file_models: List[FileIndexDBModel] = [FileIndexDBModel(**f_row) for f_row in file_rows]

            # 封装进 DuplicateGroupResult
            results.append(DuplicateGroupResult(
                id=group_id,
                group_name=group_name,
                file_ids=file_models
            ))

        return PaginationResult(
            total=total,
            list=results,
            page=page,
            limit=limit,
            sort_by="",
            order="ASC"
        )
