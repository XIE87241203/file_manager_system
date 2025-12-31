import uuid
import time
from backend.setting.setting import settings

class AuthManager:
    """
    用途：负责用户身份验证相关的业务逻辑，包括登录验证、Token 生命周期管理和有效期校验
    """
    def __init__(self):
        """
        用途：初始化验证管理器，定义 Token 存储和有效期
        入参说明：无
        返回值说明：无
        """
        # 存储格式：{username: {"token": token, "expire_at": timestamp}}
        self._tokens = {}
        # 默认有效期为 6 小时 (6 * 3600 = 21600 秒)
        self._expire_seconds = 21600

    def verify_login(self, username, password_hash_received):
        """
        用途：验证用户登录信息，生成带有有效期的 Token
        入参说明：
            - username: 用户输入的用户名
            - password_hash_received: 前端传输的密码 SHA-256 哈希值
        返回值说明：
            - (bool, str, str): 第一个值为是否验证成功，第二个值为提示消息，第三个值为 Token (成功时返回)
        """
        if not username or not password_hash_received:
            return False, "用户名或密码不能为空", None

        stored_username = settings.user_data.get('username')
        # 使用 Setting 类中缓存好的哈希值进行对比
        if username == stored_username and password_hash_received == settings.password_hash:
            # 登录成功，生成新 Token
            new_token = str(uuid.uuid4())
            expire_at = time.time() + self._expire_seconds
            
            # 保存 Token 和过期时间，旧 Token 自动失效（因为会覆盖同名 key）
            self._tokens[username] = {
                "token": new_token,
                "expire_at": expire_at
            }
            return True, "登录成功", new_token
        else:
            return False, "用户名或密码错误", None

    def logout(self, token):
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
                return True, "注销成功"
        return False, "无效的 Token 或已注销"

    def is_authenticated(self, token):
        """
        用途：验证 Token 是否存在且未过期
        入参说明：
            - token: 待验证的 Token
        返回值说明：
            - (bool, str): 是否验证成功及对应的用户名
        """
        current_time = time.time()
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
