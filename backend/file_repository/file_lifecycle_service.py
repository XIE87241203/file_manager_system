import os
import shutil
from typing import List, Optional

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.db.file_index_lifecycle_manager import FileIndexLifecycleManager
from backend.db.processor.file_index_processor import FileIndexProcessor
from backend.file_repository.file_info_service import FileInfoService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.file_lifecycle_result import FileLifecycleResult
from backend.model.file_move_info import FileMoveInfo


class FileLifecycleService:
    """
    用途：文件操作编排服务，统一协调物理文件与所有相关索引，避免 API 自行遍历索引表。
    """

    @staticmethod
    def _same_path(first_path: str, second_path: str) -> bool:
        """
        用途说明：按操作系统规则比较两个路径是否指向同一位置。
        入参说明：first_path (str) - 第一个路径；second_path (str) - 第二个路径。
        返回值说明：bool - 标准化后是否相同。
        """
        return os.path.normcase(os.path.normpath(first_path)) == os.path.normcase(os.path.normpath(second_path))

    @staticmethod
    def move_file(old_path: str, new_path: str) -> FileLifecycleResult:
        """
        用途说明：移动或改名物理文件，并在同一数据库事务内更新主索引、查重关系和人脸数据。
        入参说明：old_path (str) - 原文件完整路径；new_path (str) - 移动后的完整路径。
        返回值说明：FileLifecycleResult - 文件数量及各索引影响行数；未入索引文件只移动物理文件。
        异常说明：源文件不存在、目标已存在或索引更新失败时抛出异常。
        """
        if not old_path or not new_path:
            raise RuntimeError(t('file_lifecycle_source_missing', path=old_path))
        if FileLifecycleService._same_path(old_path, new_path):
            return FileLifecycleResult()
        if not os.path.isfile(old_path):
            raise RuntimeError(t('file_lifecycle_source_missing', path=old_path))
        if os.path.exists(new_path):
            raise RuntimeError(t('file_lifecycle_target_exists', path=new_path))

        old_matches: List[FileIndexDBModel] = FileIndexProcessor.get_file_indexes_by_paths(
            [old_path], case_insensitive=os.name == 'nt'
        )
        old_info: Optional[FileIndexDBModel] = old_matches[0] if old_matches else None
        try:
            shutil.move(old_path, new_path)
        except Exception as e:
            LogUtils.error(t('file_lifecycle_move_failed', old_path=old_path, new_path=new_path, error=str(e)))
            raise

        if old_info is None:
            LogUtils.debug(t('repo_update_index_skip_not_indexed', old_path=old_path))
            return FileLifecycleResult()

        try:
            result: FileLifecycleResult = FileIndexLifecycleManager.move([
                FileMoveInfo(old_path=old_info.file_path, new_path=new_path)
            ])
        except Exception as e:
            # 文件系统与数据库无法共享事务，索引失败时尝试把物理文件移回原位。
            try:
                shutil.move(new_path, old_path)
            except Exception as rollback_error:
                LogUtils.error(t(
                    'file_lifecycle_move_rollback_failed',
                    old_path=old_path,
                    new_path=new_path,
                    error=str(rollback_error)
                ))
            raise

        LogUtils.info(t('repo_update_index_log', old_path=old_path, new_path=new_path))
        return result

    @staticmethod
    def delete_file(file_path: str) -> FileLifecycleResult:
        """
        用途说明：永久删除物理文件并清理所有相关索引，仅在缩略图不再被任何索引引用时删除共享缩略图。
        入参说明：file_path (str) - 待永久删除的文件完整路径。
        返回值说明：FileLifecycleResult - 文件数量及各索引影响行数。
        异常说明：物理文件删除或数据库索引清理失败时抛出异常。
        """
        if not file_path:
            raise RuntimeError(t('file_lifecycle_source_missing', path=file_path))
        file_matches: List[FileIndexDBModel] = FileIndexProcessor.get_file_indexes_by_paths(
            [file_path], case_insensitive=os.name == 'nt'
        )
        file_info: Optional[FileIndexDBModel] = file_matches[0] if file_matches else None
        if os.path.exists(file_path):
            Utils.delete_os_file(file_path)

        try:
            result: FileLifecycleResult = FileIndexLifecycleManager.delete([
                file_info.file_path if file_info else file_path
            ])
        except Exception as e:
            LogUtils.error(t('file_lifecycle_delete_failed', path=file_path, error=str(e)))
            raise

        thumbnail_path: Optional[str] = file_info.thumbnail_path if file_info else None
        if thumbnail_path:
            try:
                remaining: int = FileIndexProcessor.count_thumbnail_references(thumbnail_path)
                if remaining == 0:
                    Utils.delete_os_file(thumbnail_path)
            except Exception as e:
                # 缩略图属于可再生成的缓存，清理失败不撤销已经完成的文件和索引删除。
                LogUtils.error(t('file_lifecycle_thumbnail_cleanup_failed', path=thumbnail_path, error=str(e)))
        return result

    @staticmethod
    def recycle_files(file_paths: List[str], index_missing: bool = False) -> FileLifecycleResult:
        """
        用途说明：批量将文件移入回收站，可选为未索引文件补建记录，并统一处理查重可见性和人脸队列。
        入参说明：
            file_paths (List[str]) - 待移入回收站的文件完整路径列表。
            index_missing (bool) - 是否允许为未索引文件补建回收站记录。
        返回值说明：FileLifecycleResult - 实际处理的文件数量及各索引影响行数。
        """
        if not file_paths:
            return FileLifecycleResult()
        missing_items: List[FileIndexDBModel] = []
        if index_missing:
            existing: List[FileIndexDBModel] = FileIndexProcessor.get_file_indexes_by_paths(
                file_paths, case_insensitive=os.name == 'nt'
            )
            existing_keys: set[str] = {
                os.path.normcase(os.path.normpath(item.file_path)) for item in existing
            }
            seen: set[str] = set()
            for path in file_paths:
                key: str = os.path.normcase(os.path.normpath(path))
                if not path or key in existing_keys or key in seen:
                    continue
                seen.add(key)
                info: Optional[FileIndexDBModel] = FileInfoService.get_file_info(path)
                if info is None:
                    raise RuntimeError(t('file_lifecycle_source_missing', path=path))
                missing_items.append(info)
        return FileIndexLifecycleManager.recycle(file_paths, missing_items=missing_items)

    @staticmethod
    def restore_files(file_paths: List[str]) -> FileLifecycleResult:
        """
        用途说明：批量从回收站恢复文件，使相册、文件管理和查重结果重新按有效文件展示。
        入参说明：file_paths (List[str]) - 待恢复的文件完整路径列表。
        返回值说明：FileLifecycleResult - 实际恢复的文件数量及各索引影响行数。
        """
        return FileIndexLifecycleManager.restore(file_paths)
