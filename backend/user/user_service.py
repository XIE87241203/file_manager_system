import hashlib
import sqlite3
from typing import Dict, List, Optional, Tuple

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.password_utils import hash_password, is_hashed
from backend.common.timezone_utils import TimezoneUtils
from backend.db.db_constants import DBConstants
from backend.db.db_manager import db_manager
from backend.model.db.user_db_model import UserDBModel
from backend.setting.setting_service import settingService
from backend.user.user_models import (
    LoginHistoryPageResult,
    LoginHistoryResult,
    RepositoryPermissionInfo,
    UserRepositoryPermissionResult,
    UserResult,
)
from config import GlobalConfig


class UserService:
    """
    用途：全局用户账户服务类，负责用户的初始化种子、查询、新增、删除与改密码。
    说明：用户是全局数据（登录不分仓库），故存于主数据库 repositories.db，
    沿用仓库元数据的 get_master_connection 直连模式；密码统一以 PBKDF2 加盐慢哈希存储。
    """

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> UserDBModel:
        """
        用途：将主库 users 表查询行转换为 UserDBModel。
        入参说明：row (sqlite3.Row): 查询结果行。
        返回值说明：UserDBModel - 用户数据库模型。
        """
        return UserDBModel(
            id=row[DBConstants.User.COL_ID],
            username=row[DBConstants.User.COL_USERNAME],
            password_hash=row[DBConstants.User.COL_PASSWORD_HASH],
            is_admin=row[DBConstants.User.COL_IS_ADMIN],
            create_time=row[DBConstants.User.COL_CREATE_TIME],
            update_time=row[DBConstants.User.COL_UPDATE_TIME]
        )

    @staticmethod
    def _write_changelog_seen(cursor: sqlite3.Cursor, user_id: int, version: str) -> None:
        """
        用途：在指定主库事务中写入或更新用户的更新日志已读版本。
        入参说明：
            cursor (sqlite3.Cursor): 主库事务游标。
            user_id (int): 全局用户 ID。
            version (str): 已读版本号。
        返回值说明：无；写入失败由上层事务捕获并回滚。
        """
        cursor.execute(f'''
            INSERT INTO {DBConstants.UserChangelogRead.TABLE_NAME}
                ({DBConstants.UserChangelogRead.COL_USER_ID}, {DBConstants.UserChangelogRead.COL_VERSION})
            VALUES (?, ?)
            ON CONFLICT({DBConstants.UserChangelogRead.COL_USER_ID}) DO UPDATE SET
                {DBConstants.UserChangelogRead.COL_VERSION} = excluded.{DBConstants.UserChangelogRead.COL_VERSION},
                {DBConstants.UserChangelogRead.COL_READ_TIME} = CURRENT_TIMESTAMP
        ''', (user_id, version))

    def get_changelog_seen_version(self, username: str) -> Optional[str]:
        """
        用途：查询指定用户最后看过的更新日志版本。
        入参说明：username (str): 登录名。
        返回值说明：Optional[str]: 已读版本号；用户不存在、没有记录或查询失败时返回 None。
        """
        user: Optional[UserDBModel] = self.get_user_by_username(username)
        if not user:
            return None
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT {DBConstants.UserChangelogRead.COL_VERSION} "
                f"FROM {DBConstants.UserChangelogRead.TABLE_NAME} "
                f"WHERE {DBConstants.UserChangelogRead.COL_USER_ID} = ?",
                (user.id,)
            )
            row: Optional[sqlite3.Row] = cursor.fetchone()
            return str(row[0]) if row else None
        except Exception as e:
            LogUtils.error(t('user_changelog_seen_query_error', error=str(e)))
            return None
        finally:
            if conn is not None:
                conn.close()

    def mark_changelog_seen(self, username: str, version: str) -> bool:
        """
        用途：保存指定用户最后看过的更新日志版本。
        入参说明：
            username (str): 登录名。
            version (str): 已读版本号。
        返回值说明：bool: 保存成功返回 True，用户不存在或写入失败返回 False。
        """
        user: Optional[UserDBModel] = self.get_user_by_username(username)
        if not user:
            return False
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            self._write_changelog_seen(cursor, user.id, version)
            conn.commit()
            return True
        except Exception as e:
            if conn is not None:
                conn.rollback()
            LogUtils.error(t('user_changelog_seen_save_error', error=str(e)))
            return False
        finally:
            if conn is not None:
                conn.close()

    def init_admin_user(self) -> None:
        """
        用途：首次启动时初始化初始管理员。若 users 表为空，则把 setting.json 中的现有用户
        迁移为管理员（密码沿用其加盐哈希），同时记录其已读当前版本，迁移成功后清空配置文件里的密码字段，使数据库成为唯一凭据来源。
        入参说明：无
        返回值说明：无
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {DBConstants.User.TABLE_NAME}")
            count: int = cursor.fetchone()[0]
            if count > 0:
                conn.close()
                return

            user_data = settingService.get_config().user_data
            username: str = (user_data.username or 'admin').strip() or 'admin'
            stored: str = user_data.password or ''
            # 兜底处理空值或残留明文（密码恢复通道在种子初始化之后才执行）
            if is_hashed(stored):
                password_hash: str = stored
            else:
                client_hash: str = hashlib.sha256((stored or 'admin123').encode('utf-8')).hexdigest()
                password_hash = hash_password(client_hash)

            cursor.execute(
                f"INSERT INTO {DBConstants.User.TABLE_NAME} "
                f"({DBConstants.User.COL_USERNAME}, {DBConstants.User.COL_PASSWORD_HASH}, {DBConstants.User.COL_IS_ADMIN}) "
                f"VALUES (?, ?, 1)",
                (username, password_hash)
            )
            # 首次部署的新用户默认已读当前版本，避免升级前没有升级日志的误提示。
            self._write_changelog_seen(cursor, int(cursor.lastrowid), GlobalConfig.APP_VERSION)
            conn.commit()
            conn.close()
            LogUtils.info(t('user_seed_admin_log', username=username))

            # 迁移成功后清空配置文件中的密码，避免遗留旧凭据（用户名保留作历史记录，非敏感）
            user_data.password = ''
            settingService.save_config()
        except Exception as e:
            LogUtils.error(t('user_seed_admin_error', error=str(e)))

    def list_users(self) -> List[UserResult]:
        """
        用途：获取所有用户列表（按 ID 升序，不含密码哈希，附带各用户最后一次登录时间）。
        入参说明：无
        返回值说明：List[UserResult] - 用户信息列表。
        """
        results: List[UserResult] = []
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT {DBConstants.User.COL_ID}, {DBConstants.User.COL_USERNAME}, "
                f"{DBConstants.User.COL_IS_ADMIN}, {DBConstants.User.COL_CREATE_TIME}, "
                f"(SELECT MAX(h.{DBConstants.LoginHistory.COL_LOGIN_TIME}) "
                f"FROM {DBConstants.LoginHistory.TABLE_NAME} h "
                f"WHERE h.{DBConstants.LoginHistory.COL_USER_ID} = {DBConstants.User.TABLE_NAME}.{DBConstants.User.COL_ID}) AS last_login "
                f"FROM {DBConstants.User.TABLE_NAME} ORDER BY {DBConstants.User.COL_ID} ASC"
            )
            for row in cursor.fetchall():
                results.append(UserResult(
                    id=row[0], username=row[1], is_admin=bool(row[2]),
                    create_time=TimezoneUtils.utc_to_target(row[3]) or None,
                    last_login=TimezoneUtils.utc_to_target(row[4]) or None
                ))
            conn.close()
        except Exception as e:
            LogUtils.error(t('user_list_error', error=str(e)))
        return results

    def get_user_by_username(self, username: str) -> Optional[UserDBModel]:
        """
        用途：按登录名查询用户完整记录（含密码哈希，供登录校验使用）。
        入参说明：username (str): 登录名。
        返回值说明：Optional[UserDBModel] - 用户模型，不存在返回 None。
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {DBConstants.User.TABLE_NAME} WHERE {DBConstants.User.COL_USERNAME} = ?",
                (username,)
            )
            row = cursor.fetchone()
            conn.close()
            return self._row_to_model(row) if row else None
        except Exception as e:
            LogUtils.error(t('user_query_error', error=str(e)))
            return None

    def get_user_by_id(self, user_id: int) -> Optional[UserDBModel]:
        """
        用途：按 ID 查询用户完整记录。
        入参说明：user_id (int): 用户 ID。
        返回值说明：Optional[UserDBModel] - 用户模型，不存在返回 None。
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {DBConstants.User.TABLE_NAME} WHERE {DBConstants.User.COL_ID} = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            conn.close()
            return self._row_to_model(row) if row else None
        except Exception as e:
            LogUtils.error(t('user_query_error', error=str(e)))
            return None

    def get_first_admin(self) -> Optional[UserDBModel]:
        """
        用途：查询最早创建的管理员（ID 最小的管理员），作为 setting.json 密码恢复通道的重设目标。
        说明：配置加载阶段可能早于主库建表，查询异常（如表不存在）时返回 None，由调用方兜底处理。
        入参说明：无
        返回值说明：Optional[UserDBModel] - 初始管理员模型，无管理员或查询失败返回 None。
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {DBConstants.User.TABLE_NAME} "
                f"WHERE {DBConstants.User.COL_IS_ADMIN} = 1 "
                f"ORDER BY {DBConstants.User.COL_ID} ASC LIMIT 1"
            )
            row = cursor.fetchone()
            conn.close()
            return self._row_to_model(row) if row else None
        except Exception as e:
            LogUtils.error(t('user_query_error', error=str(e)))
            return None

    def is_admin(self, username: str) -> bool:
        """
        用途：判断指定登录名是否为管理员。
        入参说明：username (str): 登录名。
        返回值说明：bool - 是管理员返回 True。
        """
        user: Optional[UserDBModel] = self.get_user_by_username(username)
        return bool(user and user.is_admin)

    def get_repo_permission(self, username: str, repo_id: int) -> Optional[str]:
        """
        用途：获取指定用户在指定仓库中的权限。
        入参说明：
            username (str): 登录名。
            repo_id (int): 仓库 ID。
        返回值说明：Optional[str] - admin/member；用户不存在或仓库未授权时返回 None。
        """
        user: Optional[UserDBModel] = self.get_user_by_username(username)
        if not user:
            return None
        if user.is_admin:
            return DBConstants.UserRepositoryPermission.PERMISSION_ADMIN
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT {DBConstants.UserRepositoryPermission.COL_PERMISSION} "
                f"FROM {DBConstants.UserRepositoryPermission.TABLE_NAME} "
                f"WHERE {DBConstants.UserRepositoryPermission.COL_USER_ID} = ? "
                f"AND {DBConstants.UserRepositoryPermission.COL_REPO_ID} = ?",
                (user.id, repo_id)
            )
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            LogUtils.error(t('user_repo_permission_query_error', error=str(e)))
            return None

    def get_repo_permissions(self, username: str) -> Dict[int, str]:
        """
        用途：获取指定用户可见的全部仓库权限映射，供仓库列表过滤使用。
        入参说明：username (str): 登录名。
        返回值说明：Dict[int, str] - 仓库 ID 到 admin/member 权限的映射；系统管理员包含全部仓库。
        """
        permissions: Dict[int, str] = {}
        user: Optional[UserDBModel] = self.get_user_by_username(username)
        if not user:
            return permissions
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            if user.is_admin:
                cursor.execute(
                    f"SELECT {DBConstants.Repository.COL_ID}, ? FROM {DBConstants.Repository.TABLE_NAME}",
                    (DBConstants.UserRepositoryPermission.PERMISSION_ADMIN,)
                )
            else:
                cursor.execute(
                    f"SELECT p.{DBConstants.UserRepositoryPermission.COL_REPO_ID}, "
                    f"p.{DBConstants.UserRepositoryPermission.COL_PERMISSION} "
                    f"FROM {DBConstants.UserRepositoryPermission.TABLE_NAME} p "
                    f"WHERE p.{DBConstants.UserRepositoryPermission.COL_USER_ID} = ?",
                    (user.id,)
                )
            for row in cursor.fetchall():
                permissions[int(row[0])] = str(row[1])
            conn.close()
        except Exception as e:
            LogUtils.error(t('user_repo_permission_query_error', error=str(e)))
        return permissions

    def list_user_repository_permissions(self, user_id: int) -> List[UserRepositoryPermissionResult]:
        """
        用途：获取某用户的完整仓库权限配置，包含不可见仓库，供系统管理员编辑弹窗使用。
        入参说明：user_id (int): 目标用户 ID。
        返回值说明：List[UserRepositoryPermissionResult] - 按仓库 ID 升序排列的权限配置列表。
        """
        results: List[UserRepositoryPermissionResult] = []
        user: Optional[UserDBModel] = self.get_user_by_id(user_id)
        if not user:
            return results
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT r.{DBConstants.Repository.COL_ID}, r.{DBConstants.Repository.COL_NAME}, "
                f"p.{DBConstants.UserRepositoryPermission.COL_PERMISSION} "
                f"FROM {DBConstants.Repository.TABLE_NAME} r "
                f"LEFT JOIN {DBConstants.UserRepositoryPermission.TABLE_NAME} p "
                f"ON p.{DBConstants.UserRepositoryPermission.COL_REPO_ID} = r.{DBConstants.Repository.COL_ID} "
                f"AND p.{DBConstants.UserRepositoryPermission.COL_USER_ID} = ? "
                f"ORDER BY r.{DBConstants.Repository.COL_ID} ASC",
                (user_id,)
            )
            for row in cursor.fetchall():
                stored_permission: str = str(row[2] or '')
                permission: str = DBConstants.UserRepositoryPermission.PERMISSION_ADMIN if user.is_admin else stored_permission
                results.append(UserRepositoryPermissionResult(
                    repo_id=int(row[0]),
                    repo_name=str(row[1]),
                    visible=bool(permission),
                    permission=permission
                ))
            conn.close()
        except Exception as e:
            LogUtils.error(t('user_repo_permission_query_error', error=str(e)))
        return results

    @staticmethod
    def _insert_permission_rows(
        cursor: sqlite3.Cursor,
        user_id: int,
        permissions: List[RepositoryPermissionInfo],
        is_admin: bool
    ) -> Tuple[bool, str]:
        """
        用途：在用户新增或权限替换事务中校验并写入仓库授权记录。
        入参说明：
            cursor (sqlite3.Cursor): 主库事务游标。
            user_id (int): 目标用户 ID。
            permissions (List[RepositoryPermissionInfo]): 仓库授权列表。
            is_admin (bool): 是否系统管理员；系统管理员无需逐仓库记录。
        返回值说明：Tuple[bool, str] - 是否成功及错误提示。
        """
        if is_admin:
            return True, ''
        valid_repo_ids: set[int] = {
            int(row[0]) for row in cursor.execute(
                f"SELECT {DBConstants.Repository.COL_ID} FROM {DBConstants.Repository.TABLE_NAME}"
            ).fetchall()
        }
        seen_repo_ids: set[int] = set()
        for item in permissions:
            if item.repo_id not in valid_repo_ids:
                return False, t('user_repo_permission_invalid_repo')
            if item.repo_id in seen_repo_ids:
                return False, t('user_repo_permission_duplicate')
            if item.permission not in (
                DBConstants.UserRepositoryPermission.PERMISSION_ADMIN,
                DBConstants.UserRepositoryPermission.PERMISSION_MEMBER
            ):
                return False, t('user_repo_permission_invalid')
            seen_repo_ids.add(item.repo_id)
            cursor.execute(
                f"INSERT INTO {DBConstants.UserRepositoryPermission.TABLE_NAME} "
                f"({DBConstants.UserRepositoryPermission.COL_USER_ID}, "
                f"{DBConstants.UserRepositoryPermission.COL_REPO_ID}, "
                f"{DBConstants.UserRepositoryPermission.COL_PERMISSION}) VALUES (?, ?, ?)",
                (user_id, item.repo_id, item.permission)
            )
        return True, ''

    def replace_user_repository_permissions(
        self,
        user_id: int,
        permissions: List[RepositoryPermissionInfo]
    ) -> Tuple[bool, str]:
        """
        用途：整体替换某系统使用者的仓库可见性与权限配置。
        入参说明：
            user_id (int): 目标用户 ID。
            permissions (List[RepositoryPermissionInfo]): 新的仓库授权列表，未包含的仓库设为不可见。
        返回值说明：Tuple[bool, str] - 是否成功及提示消息。
        """
        user: Optional[UserDBModel] = self.get_user_by_id(user_id)
        if not user:
            return False, t('user_not_found')
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {DBConstants.UserRepositoryPermission.TABLE_NAME} "
                f"WHERE {DBConstants.UserRepositoryPermission.COL_USER_ID} = ?",
                (user_id,)
            )
            valid, message = self._insert_permission_rows(cursor, user_id, permissions, bool(user.is_admin))
            if not valid:
                conn.rollback()
                conn.close()
                return False, message
            conn.commit()
            conn.close()
            LogUtils.info(t('user_repo_permission_update_log', username=user.username))
            return True, t('user_repo_permission_update_success')
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            LogUtils.error(t('user_repo_permission_update_error', error=str(e)))
            return False, t('user_repo_permission_update_error', error=str(e))

    def count_admins(self) -> int:
        """
        用途：统计管理员数量，用于保护最后一个管理员不被删除。
        入参说明：无
        返回值说明：int - 管理员数量。
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {DBConstants.User.TABLE_NAME} WHERE {DBConstants.User.COL_IS_ADMIN} = 1"
            )
            count: int = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            LogUtils.error(t('user_query_error', error=str(e)))
            return 0

    def add_user(
        self,
        username: str,
        client_hash: str,
        is_admin: bool = False,
        permissions: Optional[List[RepositoryPermissionInfo]] = None
    ) -> Tuple[bool, str]:
        """
        用途：新增系统管理员或系统使用者，并在同一事务中写入仓库授权和当前版本已读记录。
        入参说明：
            username (str): 登录名。
            client_hash (str): 前端传输的密码 SHA-256 哈希。
            is_admin (bool): True 为系统管理员，False 为系统使用者。
            permissions (Optional[List[RepositoryPermissionInfo]]): 系统使用者的仓库授权列表。
        返回值说明：(bool, str) - 是否成功及提示消息。
        """
        username = (username or '').strip()
        if not username:
            return False, t('user_name_required')
        if not client_hash:
            return False, t('user_password_required')
        if self.get_user_by_username(username):
            return False, t('user_add_duplicate', username=username)
        permission_rows: List[RepositoryPermissionInfo] = permissions or []
        conn: Optional[sqlite3.Connection] = None
        try:
            password_hash: str = hash_password(client_hash)
            conn = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO {DBConstants.User.TABLE_NAME} "
                f"({DBConstants.User.COL_USERNAME}, {DBConstants.User.COL_PASSWORD_HASH}, {DBConstants.User.COL_IS_ADMIN}) "
                f"VALUES (?, ?, ?)",
                (username, password_hash, 1 if is_admin else 0)
            )
            user_id: int = int(cursor.lastrowid)
            valid, message = self._insert_permission_rows(cursor, user_id, permission_rows, is_admin)
            if not valid:
                conn.rollback()
                conn.close()
                return False, message
            # 新建用户默认已读当前最新版本。
            self._write_changelog_seen(cursor, user_id, GlobalConfig.APP_VERSION)
            conn.commit()
            conn.close()
            LogUtils.info(t('user_add_log', username=username))
            return True, t('user_add_success')
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            LogUtils.error(t('user_add_error', error=str(e)))
            return False, t('user_add_error', error=str(e))

    def delete_user(self, user_id: int, operator_username: str) -> Tuple[bool, str]:
        """
        用途：删除用户。禁止删除自己，禁止删除最后一个管理员；删除成功后使该用户 Token 立即失效，并同步清理其仓库授权、登录历史和更新日志已读记录。
        入参说明：
            user_id (int): 待删除用户 ID。
            operator_username (str): 执行操作的管理员登录名。
        返回值说明：(bool, str) - 是否成功及提示消息。
        """
        user: Optional[UserDBModel] = self.get_user_by_id(user_id)
        if not user:
            return False, t('user_not_found')
        if user.username == operator_username:
            return False, t('user_delete_self')
        if user.is_admin and self.count_admins() <= 1:
            return False, t('user_delete_last_admin')
        # 记录删除前的初始管理员，用于判断是否需要同步清空 setting.json 中的密码密文镜像
        first_admin: Optional[UserDBModel] = self.get_first_admin()
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {DBConstants.User.TABLE_NAME} WHERE {DBConstants.User.COL_ID} = ?",
                (user_id,)
            )
            # 同步清理该用户的仓库授权与登录历史，避免遗留孤儿记录
            cursor.execute(
                f"DELETE FROM {DBConstants.UserRepositoryPermission.TABLE_NAME} "
                f"WHERE {DBConstants.UserRepositoryPermission.COL_USER_ID} = ?",
                (user_id,)
            )
            cursor.execute(
                f"DELETE FROM {DBConstants.LoginHistory.TABLE_NAME} WHERE {DBConstants.LoginHistory.COL_USER_ID} = ?",
                (user_id,)
            )
            cursor.execute(
                f"DELETE FROM {DBConstants.UserChangelogRead.TABLE_NAME} "
                f"WHERE {DBConstants.UserChangelogRead.COL_USER_ID} = ?",
                (user_id,)
            )
            conn.commit()
            conn.close()
            self._invalidate_tokens(user.username)
            LogUtils.info(t('user_delete_log', username=user.username, operator=operator_username))
            # 被删除的是初始管理员时，清空 setting.json 中的密码密文镜像，
            # 避免重启时把旧管理员的密码误重设到新的初始管理员身上
            if first_admin and first_admin.id == user_id:
                settingService.get_config().user_data.password = ''
                settingService.save_config()
                LogUtils.info(t('user_password_mirror_cleared', username=user.username))
            return True, t('user_delete_success')
        except Exception as e:
            LogUtils.error(t('user_delete_error', error=str(e)))
            return False, t('user_delete_error', error=str(e))

    def update_password(self, user_id: int, client_hash: str) -> Tuple[bool, str]:
        """
        用途：修改指定用户密码。前端传来新密码的 SHA-256 哈希，后端再做 PBKDF2 加盐慢哈希后落库，
        修改成功后使该用户现有 Token 立即失效（需重新登录）。
        入参说明：
            user_id (int): 目标用户 ID。
            client_hash (str): 前端传输的新密码 SHA-256 哈希。
        返回值说明：(bool, str) - 是否成功及提示消息。
        """
        if not client_hash:
            return False, t('user_password_required')
        user: Optional[UserDBModel] = self.get_user_by_id(user_id)
        if not user:
            return False, t('user_not_found')
        try:
            password_hash: str = hash_password(client_hash)
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {DBConstants.User.TABLE_NAME} "
                f"SET {DBConstants.User.COL_PASSWORD_HASH} = ?, {DBConstants.User.COL_UPDATE_TIME} = CURRENT_TIMESTAMP "
                f"WHERE {DBConstants.User.COL_ID} = ?",
                (password_hash, user_id)
            )
            conn.commit()
            conn.close()
            self._invalidate_tokens(user.username)
            LogUtils.info(t('user_password_log', username=user.username))
            # 初始管理员的密码密文在 setting.json 中留有镜像（密码恢复通道），改密后同步更新，
            # 避免重启时旧密文被误判为"用户重设密码"而回滚
            first_admin: Optional[UserDBModel] = self.get_first_admin()
            if first_admin and first_admin.id == user_id:
                settingService.get_config().user_data.password = password_hash
                settingService.save_config()
                LogUtils.debug(t('user_password_config_synced', username=user.username))
            return True, t('user_password_success')
        except Exception as e:
            LogUtils.error(t('user_password_error', error=str(e)))
            return False, t('user_password_error', error=str(e))

    def reset_password_hash(self, user_id: int, stored_hash: str) -> bool:
        """
        用途：密码恢复通道专用——把指定用户的密码直接重设为给定的存储哈希（PBKDF2 加盐格式），
        并使该用户现有 Token 立即失效。与 update_password 的区别：入参已是存储哈希，不再二次哈希。
        入参说明：
            user_id (int): 目标用户 ID。
            stored_hash (str): 存储格式的密码哈希（pbkdf2_sha256$迭代次数$盐hex$哈希hex）。
        返回值说明：bool - 重设成功返回 True，用户不存在或异常返回 False。
        """
        user: Optional[UserDBModel] = self.get_user_by_id(user_id)
        if not user:
            return False
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"UPDATE {DBConstants.User.TABLE_NAME} "
                f"SET {DBConstants.User.COL_PASSWORD_HASH} = ?, {DBConstants.User.COL_UPDATE_TIME} = CURRENT_TIMESTAMP "
                f"WHERE {DBConstants.User.COL_ID} = ?",
                (stored_hash, user_id)
            )
            conn.commit()
            conn.close()
            self._invalidate_tokens(user.username)
            return True
        except Exception as e:
            LogUtils.error(t('user_password_error', error=str(e)))
            return False

    def record_login(self, user_id: int, username: str, ip: str) -> None:
        """
        用途：记录一次成功登录的历史（登录时间由数据库自动生成，同时记录来源 IP）。
        入参说明：
            user_id (int): 登录用户 ID。
            username (str): 登录用户登录名。
            ip (str): 登录请求来源 IP。
        返回值说明：无
        """
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO {DBConstants.LoginHistory.TABLE_NAME} "
                f"({DBConstants.LoginHistory.COL_USER_ID}, {DBConstants.LoginHistory.COL_USERNAME}, {DBConstants.LoginHistory.COL_IP}) "
                f"VALUES (?, ?, ?)",
                (user_id, username, ip or '')
            )
            conn.commit()
            conn.close()
            LogUtils.debug(t('user_login_record_log', username=username))
        except Exception as e:
            LogUtils.error(t('user_login_record_error', error=str(e)))

    def get_login_history(self, user_id: int, page: int, page_size: int) -> LoginHistoryPageResult:
        """
        用途：分页查询某用户的登录历史（按登录时间倒序）。仅读取当前页数据，避免一次性载入全表导致 OOM。
        入参说明：
            user_id (int): 目标用户 ID。
            page (int): 页码（从 1 开始，小于 1 按 1 处理）。
            page_size (int): 每页条数（限制在 1-100 之间）。
        返回值说明：LoginHistoryPageResult - 含 total、page、page_size、list 的分页结果。
        """
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        result = LoginHistoryPageResult(page=page, page_size=page_size)
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {DBConstants.LoginHistory.TABLE_NAME} "
                f"WHERE {DBConstants.LoginHistory.COL_USER_ID} = ?",
                (user_id,)
            )
            result.total = cursor.fetchone()[0]
            offset: int = (page - 1) * page_size
            cursor.execute(
                f"SELECT {DBConstants.LoginHistory.COL_LOGIN_TIME}, {DBConstants.LoginHistory.COL_IP} "
                f"FROM {DBConstants.LoginHistory.TABLE_NAME} "
                f"WHERE {DBConstants.LoginHistory.COL_USER_ID} = ? "
                f"ORDER BY {DBConstants.LoginHistory.COL_LOGIN_TIME} DESC, {DBConstants.LoginHistory.COL_ID} DESC "
                f"LIMIT ? OFFSET ?",
                (user_id, page_size, offset)
            )
            for row in cursor.fetchall():
                result.list.append(LoginHistoryResult(
                    login_time=TimezoneUtils.utc_to_target(row[0]) or None,
                    ip=row[1] or ''
                ))
            conn.close()
        except Exception as e:
            LogUtils.error(t('user_login_history_error', error=str(e)))
        return result

    @staticmethod
    def _invalidate_tokens(username: str) -> None:
        """
        用途：使指定用户的现有登录 Token 立即失效（删除或改密码后调用）。
        入参说明：username (str): 目标用户登录名。
        返回值说明：无
        """
        # 延迟导入避免与认证模块形成循环依赖
        from backend.auth.auth_manager import auth_manager
        auth_manager.invalidate_user(username)


# 实例化单例
userService = UserService()