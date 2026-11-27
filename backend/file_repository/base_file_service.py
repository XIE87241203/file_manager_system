from typing import Tuple

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.file_repository.file_lifecycle_service import FileLifecycleService


class BaseFileService:
    """
    用途：文件业务基类，提供跨模块的文件操作基础逻辑。
    """

    @staticmethod
    def delete_file(file_path: str) -> Tuple[bool, str]:
        """
        用途：永久删除物理文件并清理所有相关索引，统一委托文件生命周期服务处理。
        入参说明：
            file_path (str): 文件的绝对路径。
        返回值说明：
            Tuple[bool, str]: (是否成功, 详细描述信息)。
        """
        try:
            FileLifecycleService.delete_file(file_path)
            return True, t('repo_cleanup_success')
        except Exception as e:
            LogUtils.error(t('repo_delete_crash', error=str(e)))
            return False, t('operation_failed', error=str(e))
