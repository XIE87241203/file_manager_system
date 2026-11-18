import math
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.password_utils import verify_password
from backend.setting.setting_service import settingService


@dataclass
class LoginAttemptInfo:
    """
    用途：记录某个 (IP, 用户名) 组合的连续登录失败次数与锁定截止时间
    """
    fails: int = 0  # 连续失败次数（登录成功后清零）
    locked_until: float = 0.0  # 锁定截止时间戳，0 表示未锁定


class AuthManager:
    """
    用途：负责用户身份验证相关的业务逻辑，包括登录验证、失败锁定、Token 生命周期管理和有效期校验
    """
    def __init__(self) -> None:
        """
        用途：初始化验证管理器，定义 Token 存储、有效期和登录失败记录表
        入参说明：无
        返回值说明：无
        """
        # 存储格式：{username: {"token": token, "expire_at": timestamp}}
        self._tokens: Dict[str, Dict] = {}
        # 默认有效期为 6 小时 (6 * 3600 = 21600 秒)
        self._expire_seconds: int = 21600
        # 登录失败记录：{(ip, username): LoginAttemptInfo}
        self._login_attempts: Dict[Tuple[str, str], LoginAttemptInfo] = {}

    def check_lock(self, ip: str, username: str) -> Tuple[bool, int]:
        """
        用途：检查指定 (IP, 用户名) 是否处于登录锁定期，并顺带清理已过期的锁定记录
        入参说明：
            - ip: 请求来源 IP 地址
            - username: 尝试登录的用户名
        返回值说明：
            - (bool, int): 第一个值为是否被锁定，第二个值为剩余锁定分钟数（未锁定时为 0）
        """
        key: Tuple[str, str] = (ip, username)
        attempt: Optional[LoginAttemptInfo] = self._login_attempts.get(key)
        if attempt is None:
            return False, 0

        current_time: float = time.time()
        if attempt.locked_until > current_time:
            remaining_minutes: int = max(1, math.ceil((attempt.locked_until - current_time) / 60))
            return True, remaining_minutes

        # 锁定已到期，重置该组合的失败记录，允许重新尝试
        if attempt.locked_until > 0:
            del self._login_attempts[key]
        return False, 0

    def verify_login(self, username: str, password_hash_received: str, ip: str) -> Tuple[bool, str, Optional[str]]:
        """
        用途：验证用户登录信息，成功时生成带有有效期的 Token；失败时累计次数并按配置触发锁定
        入参说明：
            - username: 用户输入的用户名
            - password_hash_received: 前端传输的密码 SHA-256 哈希值
            - ip: 请求来源 IP 地址，用于失败锁定记录
        返回值说明：
            - (bool, str, str): 第一个值为是否验证成功，第二个值为提示消息，第三个值为 Token (成功时返回)
        """
        if not username or not password_hash_received:
            return False, t('auth_user_pass_required'), None

        # 多用户支持：按登录名从全局 users 表查找用户，用加盐慢哈希校验前端传来的 SHA-256 哈希
        # 延迟导入避免与用户服务模块形成循环依赖
        from backend.user.user_service import userService
        user = userService.get_user_by_username(username)
        if user and verify_password(password_hash_received, user.password_hash):
            # 登录成功，清除该组合的失败记录
            self._login_attempts.pop((ip, username), None)

            # 生成新 Token
            new_token: str = str(uuid.uuid4())
            expire_at: float = time.time() + self._expire_seconds

            # 保存 Token 和过期时间，旧 Token 自动失效（因为会覆盖同名 key）
            self._tokens[username] = {
                "token": new_token,
                "expire_at": expire_at
            }
            return True, t('auth_login_success'), new_token

        # 登录失败，累计失败次数并按配置判断是否触发锁定
        self._record_login_failure(ip, username)
        return False, t('auth_login_failed'), None

    def _record_login_failure(self, ip: str, username: str) -> None:
        """
        用途：记录一次登录失败，达到配置的最大失败次数后锁定该 (IP, 用户名) 组合一段时间
        入参说明：
            - ip: 请求来源 IP 地址
            - username: 尝试登录的用户名
        返回值说明：无
        """
        user_data = settingService.get_config().user_data
        max_attempts: int = user_data.login_max_attempts
        lockout_minutes: int = user_data.login_lockout_minutes
        # 任一参数 <=0 表示不启用失败锁定
        if max_attempts <= 0 or lockout_minutes <= 0:
            return

        key: Tuple[str, str] = (ip, username)
        attempt: LoginAttemptInfo = self._login_attempts.get(key) or LoginAttemptInfo()
        attempt.fails += 1
        self._login_attempts[key] = attempt
        LogUtils.info(t('auth_login_fail_count_log', username=username, ip=ip,
                        count=attempt.fails, max_attempts=max_attempts))

        if attempt.fails >= max_attempts:
            attempt.locked_until = time.time() + lockout_minutes * 60
            LogUtils.error(t('auth_login_locked_log', username=username, ip=ip, minutes=lockout_minutes))

    def invalidate_user(self, username: str) -> None:
        """
        用途：使指定用户的现有登录 Token 立即失效（删除用户或修改其密码后调用，强制重新登录）
        入参说明：
            - username: 目标用户登录名
        返回值说明：无
        """
        self._tokens.pop(username, None)

    def logout(self, token: str) -> Tuple[bool, str]:
        """
        用途：注销登录，使 Token 立即过期并从内存中移除
        入参说明：
            - token: 需要注销的 Token
        返回值说明：
            - (bool, str): 是否注销成功及提示信息
        """
        for user, info in list(self._tokens.items()):
            if info["token"] == token:
                del self._tokens[user]
                return True, t('auth_logout_success')
        return False, t('auth_invalid_token')

    def is_authenticated(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        用途：验证 Token 是否存在且未过期
        入参说明：
            - token: 待验证的 Token
        返回值说明：
            - (bool, str): 是否验证成功及对应的用户名
        """
        current_time: float = time.time()
        for user, info in list(self._tokens.items()):
            if info["token"] == token:
                # 检查是否过期
                if current_time > info["expire_at"]:
                    # 已过期，主动从内存清除
                    del self._tokens[user]
                    return False, None
                return True, user
        return False, None

# 实例化单例
auth_manager = AuthManager()