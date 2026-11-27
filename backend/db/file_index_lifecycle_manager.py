import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Tuple

from backend.common.i18n_utils import t
from backend.db.db_constants import DBConstants
from backend.db.db_manager import db_manager
from backend.db.file_index_lifecycle_adapter import FileIndexLifecycleAdapter
from backend.db.processor.duplicate_group_processor import DuplicateGroupProcessor
from backend.db.processor.face_data_processor import FaceDataProcessor
from backend.db.processor.file_index_processor import FileIndexProcessor
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.file_lifecycle_result import FileIndexChangeResult, FileLifecycleResult
from backend.model.file_move_info import FileMoveInfo


class _FileIndexAdapter(FileIndexLifecycleAdapter):
    """
    用途：主文件索引适配器，负责路径、回收站状态和永久删除。
    """

    index_name: str = DBConstants.FileIndex.TABLE_NAME

    @staticmethod
    def move(changes: List[FileMoveInfo], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：批量更新主索引路径和文件名。
        入参说明：changes (List[FileMoveInfo]) - 路径变更列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 主索引更新行数。
        """
        affected_rows: int = 0
        for change in changes:
            affected_rows += FileIndexProcessor.update_file_path(change.old_path, change.new_path, conn=conn)
        return FileIndexChangeResult(index_name=_FileIndexAdapter.index_name, affected_rows=affected_rows)

    @staticmethod
    def delete(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：批量删除主文件索引。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 主索引删除行数。
        """
        affected_rows: int = FileIndexProcessor.delete_by_paths(file_paths, conn=conn)
        return FileIndexChangeResult(index_name=_FileIndexAdapter.index_name, affected_rows=affected_rows)

    @staticmethod
    def recycle(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：批量写入主索引回收站时间。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 主索引状态更新行数。
        """
        recycle_time: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        affected_rows: int = FileIndexProcessor.move_to_recycle_bin(file_paths, recycle_time, conn=conn)
        return FileIndexChangeResult(index_name=_FileIndexAdapter.index_name, affected_rows=affected_rows)

    @staticmethod
    def restore(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：批量清除主索引回收站时间。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 主索引状态更新行数。
        """
        affected_rows: int = FileIndexProcessor.restore_from_recycle_bin(file_paths, conn=conn)
        return FileIndexChangeResult(index_name=_FileIndexAdapter.index_name, affected_rows=affected_rows)


class _DuplicateIndexAdapter(FileIndexLifecycleAdapter):
    """
    用途：查重结果索引适配器，移动时保留分组，回收站查询按主索引有效性过滤。
    """

    index_name: str = DBConstants.DuplicateFile.TABLE_FILES

    @staticmethod
    def move(changes: List[FileMoveInfo], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：批量更新查重成员路径并保留相似度信息。
        入参说明：changes (List[FileMoveInfo]) - 路径变更列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 查重成员更新行数。
        """
        affected_rows: int = DuplicateGroupProcessor.update_file_paths(changes, conn=conn)
        return FileIndexChangeResult(index_name=_DuplicateIndexAdapter.index_name, affected_rows=affected_rows)

    @staticmethod
    def delete(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：永久删除时移除查重成员并维护分组完整性。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 查重成员删除行数。
        """
        affected_rows: int = DuplicateGroupProcessor.count_files_by_paths(file_paths, conn=conn)
        if not DuplicateGroupProcessor.delete_files_by_paths(file_paths, conn=conn):
            raise RuntimeError(t('file_lifecycle_duplicate_delete_failed'))
        return FileIndexChangeResult(index_name=_DuplicateIndexAdapter.index_name, affected_rows=affected_rows)

    @staticmethod
    def recycle(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：移入回收站时保留查重关系，展示层统一按主索引有效性过滤。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 影响行数为 0。
        """
        return FileIndexChangeResult(index_name=_DuplicateIndexAdapter.index_name, affected_rows=0)

    @staticmethod
    def restore(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：恢复时保留原查重关系，无需额外写入。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 影响行数为 0。
        """
        return FileIndexChangeResult(index_name=_DuplicateIndexAdapter.index_name, affected_rows=0)


class _FaceIndexAdapter(FileIndexLifecycleAdapter):
    """
    用途：人脸索引适配器，负责特征、处理状态和待识别队列的路径联动。
    """

    index_name: str = DBConstants.FaceIndexState.TABLE_NAME

    @staticmethod
    def move(changes: List[FileMoveInfo], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：移动时迁移人脸相关路径，避免内容未变的图片重复识别。
        入参说明：changes (List[FileMoveInfo]) - 路径变更列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 人脸相关记录更新行数。
        """
        affected_rows: int = FaceDataProcessor.update_file_paths(changes, conn=conn)
        return FileIndexChangeResult(index_name=_FaceIndexAdapter.index_name, affected_rows=affected_rows)

    @staticmethod
    def delete(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：永久删除时清理人脸特征、处理状态和队列。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 人脸相关记录删除行数。
        """
        affected_rows: int = FaceDataProcessor.delete_by_paths(file_paths, conn=conn)
        return FileIndexChangeResult(index_name=_FaceIndexAdapter.index_name, affected_rows=affected_rows)

    @staticmethod
    def recycle(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：移入回收站时仅移除待识别队列，保留已有人脸特征和处理状态。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 队列删除行数。
        """
        affected_rows: int = FaceDataProcessor.delete_queue_by_paths_count(file_paths, conn=conn)
        return FileIndexChangeResult(index_name=_FaceIndexAdapter.index_name, affected_rows=affected_rows)

    @staticmethod
    def restore(file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：恢复时保留人脸特征和处理状态；未识别图片由用户重新开始识别时入队。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：FileIndexChangeResult - 影响行数为 0。
        """
        return FileIndexChangeResult(index_name=_FaceIndexAdapter.index_name, affected_rows=0)


# 固定注册顺序：先主索引，再查重关系，最后人脸相关数据；避免运行时动态注册造成顺序不确定。
FILE_INDEX_LIFECYCLE_ADAPTERS: Tuple[FileIndexLifecycleAdapter, ...] = (
    _FileIndexAdapter(),
    _DuplicateIndexAdapter(),
    _FaceIndexAdapter()
)


class FileIndexLifecycleManager:
    """
    用途：统一编排文件相关索引的生命周期操作，并为每次操作提供单一数据库事务。
    """

    @staticmethod
    def _path_key(path: str) -> str:
        """
        用途说明：生成用于路径比较和去重的标准化键，兼容 Windows 大小写与分隔符差异。
        入参说明：path (str) - 文件完整路径。
        返回值说明：str - 标准化后的路径键。
        """
        return os.path.normcase(os.path.normpath(path))

    @staticmethod
    def _unique_paths(file_paths: List[str]) -> List[str]:
        """
        用途说明：按标准化路径去重，同时保留原始路径用于数据库查询。
        入参说明：file_paths (List[str]) - 输入文件路径列表。
        返回值说明：List[str] - 去重后的文件路径列表。
        """
        seen: set[str] = set()
        result: List[str] = []
        for path in file_paths:
            if not path:
                continue
            key: str = FileIndexLifecycleManager._path_key(path)
            if key in seen:
                continue
            seen.add(key)
            result.append(path)
        return result

    @staticmethod
    def _canonical_paths(file_paths: List[str], conn: sqlite3.Connection) -> List[str]:
        """
        用途说明：将输入路径映射为主索引中保存的实际路径，兼容 Windows 大小写差异。
        入参说明：file_paths (List[str]) - 输入文件路径；conn (sqlite3.Connection) - 事务连接。
        返回值说明：List[str] - 与数据库现有记录大小写一致的路径列表，未索引路径保持原样。
        """
        existing: List[FileIndexDBModel] = FileIndexProcessor.get_file_indexes_by_paths(
            file_paths, conn=conn, case_insensitive=os.name == 'nt'
        )
        actual_paths: dict[str, str] = {
            FileIndexLifecycleManager._path_key(item.file_path): item.file_path
            for item in existing
        }
        return [
            actual_paths.get(FileIndexLifecycleManager._path_key(path), path)
            for path in file_paths
        ]

    @staticmethod
    def _canonical_changes(changes: List[FileMoveInfo], conn: sqlite3.Connection) -> List[FileMoveInfo]:
        """
        用途说明：将移动源路径映射为主索引实际路径，避免大小写差异导致附属索引漏更新。
        入参说明：changes (List[FileMoveInfo]) - 路径变更列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：List[FileMoveInfo] - 源路径已与数据库记录对齐的变更列表。
        """
        source_paths: List[str] = [change.old_path for change in changes]
        canonical_sources: List[str] = FileIndexLifecycleManager._canonical_paths(source_paths, conn)
        return [
            FileMoveInfo(old_path=source_path, new_path=change.new_path)
            for change, source_path in zip(changes, canonical_sources)
        ]

    @staticmethod
    def _validate_moves(changes: List[FileMoveInfo], conn: sqlite3.Connection) -> None:
        """
        用途说明：在事务内校验移动源、目标冲突和路径交叉，避免部分索引更新。
        入参说明：changes (List[FileMoveInfo]) - 路径变更列表；conn (sqlite3.Connection) - 事务连接。
        返回值说明：无；校验失败时抛出异常。
        """
        old_keys: set[str] = {FileIndexLifecycleManager._path_key(change.old_path) for change in changes}
        new_keys: set[str] = {FileIndexLifecycleManager._path_key(change.new_path) for change in changes}
        if old_keys & new_keys:
            raise RuntimeError(t('repo_update_index_conflict', old_path='multiple', new_path='multiple'))

        old_paths: List[str] = [change.old_path for change in changes]
        new_paths: List[str] = [change.new_path for change in changes]
        existing: List[FileIndexDBModel] = FileIndexProcessor.get_file_indexes_by_paths(
            old_paths, conn=conn, case_insensitive=os.name == 'nt'
        )
        existing_keys: set[str] = {FileIndexLifecycleManager._path_key(item.file_path) for item in existing}
        if existing_keys != old_keys:
            raise RuntimeError(t('repo_update_index_skip_not_indexed', old_path='multiple'))

        conflicts: List[FileIndexDBModel] = FileIndexProcessor.get_file_indexes_by_paths(
            new_paths, conn=conn, case_insensitive=os.name == 'nt'
        )
        if conflicts:
            raise RuntimeError(t('repo_update_index_conflict', old_path='multiple', new_path=conflicts[0].file_path))

    @staticmethod
    def move(changes: List[FileMoveInfo]) -> FileLifecycleResult:
        """
        用途说明：在单一事务内更新所有文件相关索引的路径。
        入参说明：changes (List[FileMoveInfo]) - 文件移动或改名路径变更列表。
        返回值说明：FileLifecycleResult - 文件数量及各索引影响行数。
        """
        valid_changes: List[FileMoveInfo] = [
            change for change in changes
            if change.old_path and change.new_path
            and FileIndexLifecycleManager._path_key(change.old_path) != FileIndexLifecycleManager._path_key(change.new_path)
        ]
        if not valid_changes:
            return FileLifecycleResult()
        with db_manager.transaction() as conn:
            valid_changes = FileIndexLifecycleManager._canonical_changes(valid_changes, conn)
            FileIndexLifecycleManager._validate_moves(valid_changes, conn)
            results: List[FileIndexChangeResult] = [
                adapter.move(valid_changes, conn) for adapter in FILE_INDEX_LIFECYCLE_ADAPTERS
            ]
        return FileLifecycleResult(affected_files=results[0].affected_rows, index_changes=results)

    @staticmethod
    def delete(file_paths: List[str]) -> FileLifecycleResult:
        """
        用途说明：在单一事务内从所有文件相关索引中永久删除指定文件。
        入参说明：file_paths (List[str]) - 待永久删除的文件路径列表。
        返回值说明：FileLifecycleResult - 文件数量及各索引影响行数。
        """
        paths: List[str] = FileIndexLifecycleManager._unique_paths(file_paths)
        if not paths:
            return FileLifecycleResult()
        with db_manager.transaction() as conn:
            paths = FileIndexLifecycleManager._canonical_paths(paths, conn)
            results: List[FileIndexChangeResult] = [
                adapter.delete(paths, conn) for adapter in FILE_INDEX_LIFECYCLE_ADAPTERS
            ]
        return FileLifecycleResult(affected_files=results[0].affected_rows, index_changes=results)

    @staticmethod
    def recycle(file_paths: List[str], missing_items: Optional[List[FileIndexDBModel]] = None) -> FileLifecycleResult:
        """
        用途说明：在单一事务内写入回收站状态，并可补建未索引文件的回收站记录。
        入参说明：
            file_paths (List[str]) - 待移入回收站的文件路径列表。
            missing_items (Optional[List[FileIndexDBModel]]) - 未索引文件已提取好的索引模型。
        返回值说明：FileLifecycleResult - 文件数量及各索引影响行数。
        """
        paths: List[str] = FileIndexLifecycleManager._unique_paths(file_paths)
        if not paths:
            return FileLifecycleResult()
        with db_manager.transaction() as conn:
            if missing_items:
                FileIndexProcessor.batch_insert_data(missing_items, conn=conn)
            paths = FileIndexLifecycleManager._canonical_paths(paths, conn)
            results: List[FileIndexChangeResult] = [
                adapter.recycle(paths, conn) for adapter in FILE_INDEX_LIFECYCLE_ADAPTERS
            ]
        return FileLifecycleResult(affected_files=results[0].affected_rows, index_changes=results)

    @staticmethod
    def restore(file_paths: List[str]) -> FileLifecycleResult:
        """
        用途说明：在单一事务内清除回收站状态，使文件重新出现在有效文件列表中。
        入参说明：file_paths (List[str]) - 待恢复的文件路径列表。
        返回值说明：FileLifecycleResult - 文件数量及各索引影响行数。
        """
        paths: List[str] = FileIndexLifecycleManager._unique_paths(file_paths)
        if not paths:
            return FileLifecycleResult()
        with db_manager.transaction() as conn:
            paths = FileIndexLifecycleManager._canonical_paths(paths, conn)
            results: List[FileIndexChangeResult] = [
                adapter.restore(paths, conn) for adapter in FILE_INDEX_LIFECYCLE_ADAPTERS
            ]
        return FileLifecycleResult(affected_files=results[0].affected_rows, index_changes=results)
