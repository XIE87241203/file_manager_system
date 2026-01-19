from typing import Optional

from backend.db.db_constants import DBConstants
from backend.db.db_manager import DBManager
from backend.model.db.file_repo_detail_db_model import FileRepoDetailDBModel


class FileRepoDetailProcessor:
    """
    用途：文件仓库详情数据库处理器，负责 file_repo_detail 表的增删改查
    """
    
    def get_detail(self) -> Optional[FileRepoDetailDBModel]:
        """
        用途说明：获取当前的文件仓库详情。
        返回值说明：FileRepoDetailDBModel 或 None
        """
        conn = DBManager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {DBConstants.FileRepoDetail.TABLE_NAME} ORDER BY {DBConstants.FileRepoDetail.COL_ID} DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return FileRepoDetailDBModel(
                    id=row[0],
                    total_count=row[1],
                    total_size=row[2],
                    update_time=row[3]
                )
            return None
        finally:
            conn.close()

    def update_detail(self, total_count: int, total_size: int, update_time: str) -> bool:
        """
        用途说明：更新或插入文件仓库详情数据（保持单行记录）。
        """
        conn = DBManager.get_connection()
        try:
            cursor = conn.cursor()
            # 检查是否已有记录
            cursor.execute(f"SELECT {DBConstants.FileRepoDetail.COL_ID} FROM {DBConstants.FileRepoDetail.TABLE_NAME} LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                cursor.execute(f"""
                    UPDATE {DBConstants.FileRepoDetail.TABLE_NAME} 
                    SET {DBConstants.FileRepoDetail.COL_TOTAL_COUNT} = ?, 
                        {DBConstants.FileRepoDetail.COL_TOTAL_SIZE} = ?, 
                        {DBConstants.FileRepoDetail.COL_UPDATE_TIME} = ?
                    WHERE {DBConstants.FileRepoDetail.COL_ID} = ?
                """, (total_count, total_size, update_time, row[0]))
            else:
                cursor.execute(f"""
                    INSERT INTO {DBConstants.FileRepoDetail.TABLE_NAME} 
                    ({DBConstants.FileRepoDetail.COL_TOTAL_COUNT}, {DBConstants.FileRepoDetail.COL_TOTAL_SIZE}, {DBConstants.FileRepoDetail.COL_UPDATE_TIME}) 
                    VALUES (?, ?, ?)
                """, (total_count, total_size, update_time))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
