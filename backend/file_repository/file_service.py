import os
from typing import List, Tuple, Dict, Any, Optional

from backend.db.db_operations import DBOperations
from backend.db.db_manager import DBManager
from backend.common.log_utils import LogUtils
from backend.file_repository.thumbnail.thumbnail_service import ThumbnailService
from backend.setting.setting import settings

class FileService:
    """
    用途：文件仓库业务服务类，封装文件列表查询、删除、清理等核心操作。
    """

    @staticmethod
    def get_file_list(
        page: int, 
        limit: int, 
        sort_by: str, 
        order: str, 
        search_query: str, 
        search_history: bool
    ) -> Dict[str, Any]:
        """
        用途：分页查询文件索引列表，支持模糊搜索。
        入参说明：
            page (int): 当前页码
            limit (int): 每页记录数
            sort_by (str): 排序字段
            order (str): 排序方向 (ASC/DESC)
            search_query (str): 搜索关键词
            search_history (bool): 是否查询历史表
        返回值说明：
            Dict[str, Any]: 包含 total, list, page, limit 等分页信息的字典
        """
        table_name = DBManager.TABLE_FILE_INDEX if not search_history else DBManager.TABLE_HISTORY_INDEX
        offset = (page - 1) * limit
        
        where_clause = ""
        params = []
        
        if search_query:
            # 获取配置中的替换字符并处理搜索逻辑
            replace_chars = settings.file_repository.get('search_replace_chars', [])
            processed_query = search_query
            for char in replace_chars:
                if char:
                    processed_query = processed_query.replace(char, '.*')
            
            sql_like_query = f"%{processed_query.replace('.*', '%')}%"
            where_clause = " WHERE file_name LIKE ? "
            params.append(sql_like_query)

        # 获取总数
        total = DBOperations.get_file_count(table_name, where_clause, tuple(params))

        # 获取数据
        results = DBOperations.get_file_list_with_pagination(
            table_name, where_clause, tuple(params), sort_by, order, limit, offset
        )
        
        # 数据转换
        file_list = []
        for row in results:
            item = {
                "id": row.id, 
                "file_path": row.file_path, 
                "file_name": row.file_name, 
                "file_md5": row.file_md5, 
                "scan_time": row.scan_time
            }
            if not search_history:
                item["thumbnail_path"] = getattr(row, 'thumbnail_path', None)
            file_list.append(item)
            
        return {
            "total": total, 
            "list": file_list, 
            "page": page, 
            "limit": limit, 
            "sort_by": sort_by, 
            "order": order, 
            "is_history": search_history
        }

    @staticmethod
    def delete_file(file_path: str) -> Tuple[bool, str]:
        """
        用途：物理删除文件，并同步清理关联的缩略图及数据库索引记录。
        入参说明：
            file_path (str): 文件的绝对路径
        返回值说明：
            Tuple[bool, str]: (是否成功, 结果描述)
        """
        try:
            # 1. 查询并物理删除关联的缩略图
            file_info = DBOperations.get_file_by_path(file_path)
            if file_info and file_info.thumbnail_path:
                if os.path.exists(file_info.thumbnail_path):
                    try:
                        os.remove(file_info.thumbnail_path)
                        LogUtils.info(f"缩略图已同步删除: {file_info.thumbnail_path}")
                    except Exception as e:
                        LogUtils.error(f"物理删除缩略图文件失败: {e}")

            # 2. 删除原物理文件
            if os.path.exists(file_path):
                os.remove(file_path)
                LogUtils.info(f"物理文件已删除: {file_path}")
            else:
                LogUtils.warn(f"物理文件不存在，仅清理数据库索引: {file_path}")

            # 3. 清理数据库记录（索引表和查重结果表）
            DBOperations.delete_file_index_by_path(file_path)
            DBOperations.delete_duplicate_file_by_path(file_path)

            return True, "文件及相关缓存、索引已成功删除"
        except Exception as e:
            LogUtils.error(f"删除文件操作异常: {file_path}, 错误: {e}")
            return False, str(e)

    @staticmethod
    def clear_repository(clear_history: bool) -> bool:
        """
        用途：清空文件索引数据库，并强制清理所有缩略图文件。
        入参说明：
            clear_history (bool): 是否同步清空历史索引表。
        返回值说明：
            bool: 是否全部清理成功
        """
        try:
            # 1. 物理删除所有缩略图文件及清空生成器队列
            ThumbnailService.clear_all_thumbnails()

            # 2. 清空当前文件索引表
            if not DBOperations.clear_file_index():
                return False
            
            # 3. 若需要，清空历史索引表
            if clear_history:
                if not DBOperations.clear_history_index():
                    return False
            
            LogUtils.info(f"文件仓库已清空 (包含历史记录: {clear_history})")
            return True
        except Exception as e:
            LogUtils.error(f"清理仓库过程发生异常: {e}")
            return False

    @staticmethod
    def clear_video_features() -> bool:
        """
        用途：清空视频特征指纹库。
        返回值说明：
            bool: 是否成功
        """
        return DBOperations.clear_video_features()
