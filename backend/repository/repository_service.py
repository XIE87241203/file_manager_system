import json
import os
import sqlite3
from dataclasses import asdict, fields
from typing import List, Optional, Dict, Any, Callable

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import get_current_repo_id
from backend.common.utils import Utils
from backend.db.db_constants import DBConstants
from backend.db.db_manager import db_manager
from backend.repository.repository_db_model import RepositoryDBModel
from backend.repository.repository_result import RepositoryResult
from backend.setting.setting_models import FileRepositorySettings
from backend.setting.setting_service import settingService
from backend.user.user_service import userService


class RepositoryService:
    """
    用途：多仓库管理服务，负责仓库元数据与独立配置的增删查改，以及默认仓库初始化。
    每个仓库对应一个独立业务库文件，仓库元数据集中存放于主数据库 repositories.db。
    """

    def __init__(self) -> None:
        """
        用途：初始化仓库服务，建立配置变更与删除回调列表（观察者模式，避免跨模块直接依赖）。
        入参说明：无
        返回值说明：无
        """
        self._config_change_callbacks: List[Callable[[int, Dict[str, Any]], None]] = []
        self._delete_callbacks: List[Callable[[int], None]] = []

    # --- 观察者回调注册 ---

    def register_config_change_callback(self, callback: Callable[[int, Dict[str, Any]], None]) -> None:
        """
        用途：注册仓库配置变更回调。
        入参说明：callback: 回调函数，接收 (repo_id, 本次更新的数据字典)。
        返回值说明：无
        """
        self._config_change_callbacks.append(callback)

    def register_delete_callback(self, callback: Callable[[int], None]) -> None:
        """
        用途：注册仓库删除回调。
        入参说明：callback: 回调函数，接收被删除的 repo_id。
        返回值说明：无
        """
        self._delete_callbacks.append(callback)

    # --- 内部工具方法 ---

    @staticmethod
    def _config_to_json(config: FileRepositorySettings) -> str:
        """
        用途：将仓库配置数据类序列化为 JSON 字符串。
        入参说明：config (FileRepositorySettings): 仓库配置对象。
        返回值说明：str - JSON 字符串。
        """
        return json.dumps(asdict(config), ensure_ascii=False)

    @staticmethod
    def _json_to_config(config_json: str) -> FileRepositorySettings:
        """
        用途：将 JSON 字符串反序列化为仓库配置数据类，忽略未知字段。
        入参说明：config_json (str): 配置 JSON 字符串。
        返回值说明：FileRepositorySettings - 仓库配置对象，解析失败时返回默认配置。
        """
        try:
            data: Dict[str, Any] = json.loads(config_json) if config_json else {}
        except Exception as e:
            LogUtils.error(t('repo_config_parse_failed', error=str(e)))
            data = {}
        valid_fields = {f.name for f in fields(FileRepositorySettings)}
        return FileRepositorySettings(**{k: v for k, v in data.items() if k in valid_fields})

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> RepositoryDBModel:
        """
        用途：将主数据库查询行转换为 RepositoryDBModel。
        入参说明：row (sqlite3.Row): 查询结果行。
        返回值说明：RepositoryDBModel - 仓库数据库模型。
        """
        return RepositoryDBModel(
            id=row[DBConstants.Repository.COL_ID],
            name=row[DBConstants.Repository.COL_NAME],
            config=row[DBConstants.Repository.COL_CONFIG],
            db_file=row[DBConstants.Repository.COL_DB_FILE],
            create_time=row[DBConstants.Repository.COL_CREATE_TIME]
        )

    # --- 默认仓库初始化 ---

    def init_default_repo(self) -> None:
        """
        用途：项目初始化时创建默认仓库。若主表为空，则将现有 file_manager.db 注册为默认仓库，
        并把现有全局 file_repository 配置迁移为其独立配置。
        入参说明：无
        返回值说明：无
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {DBConstants.Repository.TABLE_NAME}")
            count: int = cursor.fetchone()[0]
            if count == 0:
                config: FileRepositorySettings = settingService.get_config().file_repository
                config_json: str = self._config_to_json(config)
                name: str = t('repo_default_name')
                cursor.execute(
                    f"INSERT INTO {DBConstants.Repository.TABLE_NAME} "
                    f"({DBConstants.Repository.COL_NAME}, {DBConstants.Repository.COL_CONFIG}, {DBConstants.Repository.COL_DB_FILE}) "
                    f"VALUES (?, ?, ?)",
                    (name, config_json, db_manager.DB_NAME)
                )
                conn.commit()
                LogUtils.info(t('repo_init_default_log', name=name))
            conn.close()
        except Exception as e:
            LogUtils.error(t('repo_init_default_error', error=str(e)))
        db_manager.clear_repo_path_cache()

    # --- 查询 ---

    def list_repos(self) -> List[RepositoryResult]:
        """
        用途：获取所有仓库的基本信息列表（按 ID 升序）。
        入参说明：无
        返回值说明：List[RepositoryResult] - 仓库信息列表。
        """
        results: List[RepositoryResult] = []
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT {DBConstants.Repository.COL_ID}, {DBConstants.Repository.COL_NAME}, "
                f"{DBConstants.Repository.COL_CREATE_TIME} FROM {DBConstants.Repository.TABLE_NAME} "
                f"ORDER BY {DBConstants.Repository.COL_ID} ASC"
            )
            for row in cursor.fetchall():
                results.append(RepositoryResult(id=row[0], name=row[1], create_time=row[2]))
            conn.close()
        except Exception as e:
            LogUtils.error(t('repo_list_error', error=str(e)))
        return results

    def list_repos_for_user(self, username: str) -> List[RepositoryResult]:
        """
        用途：获取指定用户可见的仓库列表，并附带该用户在仓库中的权限。
        入参说明：username (str): 当前登录名。
        返回值说明：List[RepositoryResult] - 按 ID 升序排列的可见仓库列表，permission 为 admin/member。
        """
        permission_map: Dict[int, str] = userService.get_repo_permissions(username)
        results: List[RepositoryResult] = []
        for repo in self.list_repos():
            permission: Optional[str] = permission_map.get(repo.id)
            if permission:
                repo.permission = permission
                results.append(repo)
        return results

    def get_repo(self, repo_id: int) -> Optional[RepositoryDBModel]:
        """
        用途：根据 ID 获取仓库完整元数据。
        入参说明：repo_id (int): 仓库 ID。
        返回值说明：Optional[RepositoryDBModel] - 仓库模型，不存在返回 None。
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {DBConstants.Repository.TABLE_NAME} WHERE {DBConstants.Repository.COL_ID} = ?",
                (repo_id,)
            )
            row = cursor.fetchone()
            conn.close()
            return self._row_to_model(row) if row else None
        except Exception as e:
            LogUtils.error(t('repo_list_error', error=str(e)))
            return None

    def repo_exists(self, repo_id: int) -> bool:
        """
        用途：判断指定仓库是否存在。
        入参说明：repo_id (int): 仓库 ID。
        返回值说明：bool - 存在返回 True。
        """
        return self.get_repo(repo_id) is not None

    def get_config(self, repo_id: int) -> FileRepositorySettings:
        """
        用途：获取指定仓库的独立配置。
        入参说明：repo_id (int): 仓库 ID。
        返回值说明：FileRepositorySettings - 仓库配置，仓库不存在时返回默认配置。
        """
        repo: Optional[RepositoryDBModel] = self.get_repo(repo_id)
        if not repo:
            return FileRepositorySettings()
        return self._json_to_config(repo.config)

    def get_current_config(self) -> FileRepositorySettings:
        """
        用途：获取当前上下文仓库的独立配置。
        入参说明：无
        返回值说明：FileRepositorySettings - 当前仓库配置。
        """
        return self.get_config(get_current_repo_id())

    # --- 创建 ---

    def create_repo(self, name: str) -> Optional[RepositoryResult]:
        """
        用途：创建新仓库，初始化其独立业务库与默认配置。
        入参说明：name (str): 仓库名称。
        返回值说明：Optional[RepositoryResult] - 创建成功返回仓库信息，失败返回 None。
        """
        name = (name or "").strip()
        if not name:
            LogUtils.error(t('repo_name_required'))
            return None
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT {DBConstants.Repository.COL_ID} FROM {DBConstants.Repository.TABLE_NAME} "
                f"WHERE {DBConstants.Repository.COL_NAME} = ?",
                (name,)
            )
            if cursor.fetchone():
                conn.close()
                LogUtils.error(t('repo_name_duplicate', name=name))
                return None

            config_json: str = self._config_to_json(FileRepositorySettings())
            cursor.execute(
                f"INSERT INTO {DBConstants.Repository.TABLE_NAME} "
                f"({DBConstants.Repository.COL_NAME}, {DBConstants.Repository.COL_CONFIG}, {DBConstants.Repository.COL_DB_FILE}) "
                f"VALUES (?, ?, ?)",
                (name, config_json, "")
            )
            repo_id: int = cursor.lastrowid
            db_file: str = f"repos/repo_{repo_id}.db"
            cursor.execute(
                f"UPDATE {DBConstants.Repository.TABLE_NAME} SET {DBConstants.Repository.COL_DB_FILE} = ? "
                f"WHERE {DBConstants.Repository.COL_ID} = ?",
                (db_file, repo_id)
            )
            conn.commit()
            conn.close()

            # 初始化新仓库业务库
            abs_path: str = os.path.join(Utils.get_runtime_path(), db_file)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            db_manager.init_db(abs_path)
            db_manager.clear_repo_path_cache()

            LogUtils.info(t('repo_create_log', name=name))
            repo: Optional[RepositoryDBModel] = self.get_repo(repo_id)
            return RepositoryResult(id=repo_id, name=name, create_time=repo.create_time if repo else None)
        except Exception as e:
            LogUtils.error(t('repo_create_error', error=str(e)))
            return None

    # --- 删除 ---

    def delete_repo(self, repo_id: int) -> bool:
        """
        用途：删除仓库（同步清理用户仓库授权、元数据、独立配置与业务库文件，保留磁盘物理文件）。禁止删除最后一个仓库。
        入参说明：repo_id (int): 仓库 ID。
        返回值说明：bool - 是否删除成功。
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {DBConstants.Repository.TABLE_NAME}")
            count: int = cursor.fetchone()[0]
            if count <= 1:
                conn.close()
                LogUtils.error(t('repo_cannot_delete_last'))
                return False

            repo: Optional[RepositoryDBModel] = self.get_repo(repo_id)
            if not repo:
                conn.close()
                LogUtils.error(t('repo_not_found', id=repo_id))
                return False

            cursor.execute(
                f"DELETE FROM {DBConstants.Repository.TABLE_NAME} WHERE {DBConstants.Repository.COL_ID} = ?",
                (repo_id,)
            )
            # 仓库删除后同步清理所有用户对该仓库的授权，避免重新使用相同 ID 时继承旧权限
            cursor.execute(
                f"DELETE FROM {DBConstants.UserRepositoryPermission.TABLE_NAME} "
                f"WHERE {DBConstants.UserRepositoryPermission.COL_REPO_ID} = ?",
                (repo_id,)
            )
            conn.commit()
            conn.close()
            db_manager.clear_repo_path_cache()

            # 删除业务库文件（含 WAL/SHM 附属文件），保留磁盘物理文件
            abs_path: str = os.path.join(Utils.get_runtime_path(), repo.db_file)
            for suffix in ("", "-wal", "-shm"):
                target: str = abs_path + suffix
                try:
                    if os.path.exists(target):
                        os.remove(target)
                except Exception as e:
                    LogUtils.error(t('repo_delete_file_failed', error=str(e)))

            for callback in self._delete_callbacks:
                try:
                    callback(repo_id)
                except Exception as e:
                    LogUtils.error(t('repo_callback_error', error=str(e)))

            LogUtils.info(t('repo_delete_log', name=repo.name))
            return True
        except Exception as e:
            LogUtils.error(t('repo_delete_error', error=str(e)))
            return False

    # --- 更新配置 ---

    def update_config(self, repo_id: int, data: Dict[str, Any]) -> bool:
        """
        用途：更新指定仓库的独立配置并持久化，随后通知配置变更观察者。
        入参说明：
            repo_id (int): 仓库 ID。
            data (Dict[str, Any]): 待更新的配置字段字典。
        返回值说明：bool - 是否更新成功。
        """
        repo: Optional[RepositoryDBModel] = self.get_repo(repo_id)
        if not repo:
            LogUtils.error(t('repo_not_found', id=repo_id))
            return False
        try:
            config: FileRepositorySettings = self._json_to_config(repo.config)
            valid_fields = {f.name for f in fields(FileRepositorySettings)}
            for key, value in data.items():
                if key in valid_fields:
                    setattr(config, key, value)
            config_json: str = self._config_to_json(config)

            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {DBConstants.Repository.TABLE_NAME} SET {DBConstants.Repository.COL_CONFIG} = ? "
                f"WHERE {DBConstants.Repository.COL_ID} = ?",
                (config_json, repo_id)
            )
            conn.commit()
            conn.close()

            for callback in self._config_change_callbacks:
                try:
                    callback(repo_id, data)
                except Exception as e:
                    LogUtils.error(t('repo_callback_error', error=str(e)))

            LogUtils.info(t('repo_config_update_log', name=repo.name))
            return True
        except Exception as e:
            LogUtils.error(t('repo_config_update_error', error=str(e)))
            return False


# 实例化单例
repositoryService = RepositoryService()