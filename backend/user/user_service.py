import hashlib
import sqlite3
from typing import List, Optional, Tuple

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.password_utils import hash_password, is_hashed
from backend.db.db_constants import DBConstants
from backend.db.db_manager import db_manager
from backend.model.db.user_db_model import UserDBModel
from backend.setting.setting_service import settingService
from backend.user.user_models import LoginHistoryPageResult, LoginHistoryResult, UserResult


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

    def init_admin_user(self) -> None:
        """
        用途：首次启动时初始化初始管理员。若 users 表为空，则把 setting.json 中的现有用户
        迁移为管理员（密码沿用其加盐哈希），迁移成功后清空配置文件里的密码字段，使数据库成为唯一凭据来源。
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
            # 配置加载阶段已把明文迁移为加盐哈希；此处兜底处理空值或残留明文
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
                    id=row[0], username=row[1], is_admin=bool(row[2]), create_time=row[3], last_login=row[4]
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

    def is_admin(self, username: str) -> bool:
        """
        用途：判断指定登录名是否为管理员。
        入参说明：username (str): 登录名。
        返回值说明：bool - 是管理员返回 True。
        """
        user: Optional[UserDBModel] = self.get_user_by_username(username)
        return bool(user and user.is_admin)

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

    def add_user(self, username: str, client_hash: str) -> Tuple[bool, str]:
        """
        用途：新增普通用户。前端传来密码的 SHA-256 哈希，后端再做 PBKDF2 加盐慢哈希后落库。
        入参说明：
            username (str): 登录名。
            client_hash (str): 前端传输的密码 SHA-256 哈希。
        返回值说明：(bool, str) - 是否成功及提示消息。
        """
        username = (username or '').strip()
        if not username:
            return False, t('user_name_required')
        if not client_hash:
            return False, t('user_password_required')
        if self.get_user_by_username(username):
            return False, t('user_add_duplicate', username=username)
        try:
            password_hash: str = hash_password(client_hash)
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO {DBConstants.User.TABLE_NAME} "
                f"({DBConstants.User.COL_USERNAME}, {DBConstants.User.COL_PASSWORD_HASH}, {DBConstants.User.COL_IS_ADMIN}) "
                f"VALUES (?, ?, 0)",
                (username, password_hash)
            )
            conn.commit()
            conn.close()
            LogUtils.info(t('user_add_log', username=username))
            return True, t('user_add_success')
        except Exception as e:
            LogUtils.error(t('user_add_error', error=str(e)))
            return False, t('user_add_error', error=str(e))

    def delete_user(self, user_id: int, operator_username: str) -> Tuple[bool, str]:
        """
        用途：删除用户。禁止删除自己，禁止删除最后一个管理员；删除成功后使该用户 Token 立即失效，并同步清理其登录历史。
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
        try:
            conn: sqlite3.Connection = db_manager.get_master_connection()
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {DBConstants.User.TABLE_NAME} WHERE {DBConstants.User.COL_ID} = ?",
                (user_id,)
            )
            # 同步清理该用户的登录历史，避免遗留孤儿记录
            cursor.execute(
                f"DELETE FROM {DBConstants.LoginHistory.TABLE_NAME} WHERE {DBConstants.LoginHistory.COL_USER_ID} = ?",
                (user_id,)
            )
            conn.commit()
            conn.close()
            self._invalidate_tokens(user.username)
            LogUtils.info(t('user_delete_log', username=user.username, operator=operator_username))
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
            return True, t('user_password_success')
        except Exception as e:
            LogUtils.error(t('user_password_error', error=str(e)))
            return False, t('user_password_error', error=str(e))

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
                result.list.append(LoginHistoryResult(login_time=row[0], ip=row[1] or ''))
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