from typing import Tuple

from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations


class BaseFileService:
    """
    用途：文件业务基类，提供跨模块的文件操作基础逻辑。
    """

    @staticmethod
    def delete_file(file_path: str) -> Tuple[bool, str]:
        """
        用途：删除物理文件并从数据库索引及重复结果中移除，同时删除对应的缩略图文件。
        入参说明：
            file_path (str): 文件的绝对路径。
        返回值说明：
            Tuple[bool, str]: (是否成功, 详细描述信息)。
        """
        try:
            # 1. 获取文件索引信息
            file_info = DBOperations.get_file_by_path(file_path)
            
            # 2. 删除缩略图文件
            if file_info and file_info.thumbnail_path:
                Utils.delete_os_file(file_info.thumbnail_path)

            # 3. 删除物理文件
            Utils.delete_os_file(file_path)

            # 4. 清理数据库记录（包括主索引和重复组关联）
            if file_info:
                DBOperations.delete_file_index_by_file_id(file_info.id)

            return True, "文件及其关联索引、缩略图已成功删除"
        except Exception as e:
            LogUtils.error(f"BaseFileService 删除文件失败: {file_path}, 错误: {e}")
            return False, f"删除失败: {str(e)}"
