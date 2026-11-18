import hashlib
import hmac
import os

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils

# 存储格式：pbkdf2_sha256$迭代次数$盐(hex)$哈希(hex)
# 说明：前端传输的是密码的 SHA-256 哈希（client_hash），后端对其再做 PBKDF2 加盐慢哈希后存储，
# 数据库中不落任何明文；校验时用存储的盐与迭代次数重算并做常量时间比较。
ALGORITHM: str = 'pbkdf2_sha256'
ITERATIONS: int = 200000
_SALT_BYTES: int = 16
_DK_BYTES: int = 32


def is_hashed(stored: str) -> bool:
    """
    用途说明：判断密码字段是否已为加盐哈希格式（用于识别旧版明文密码）。
    入参说明：stored (str) - 配置中存储的密码字段值。
    返回值说明：bool - 已为 pbkdf2_sha256$... 格式返回 True，否则 False。
    """
    return isinstance(stored, str) and stored.startswith(ALGORITHM + '$')


def hash_password(client_hash: str) -> str:
    """
    用途说明：对前端传来的密码 SHA-256 哈希做 PBKDF2-HMAC-SHA256 加盐慢哈希，生成可存储字符串。
    入参说明：client_hash (str) - 前端传输的密码 SHA-256 哈希值。
    返回值说明：str - 形如 pbkdf2_sha256$200000$盐hex$哈希hex 的存储字符串。
    """
    salt: bytes = os.urandom(_SALT_BYTES)
    dk: bytes = hashlib.pbkdf2_hmac('sha256', client_hash.encode('utf-8'), salt, ITERATIONS, dklen=_DK_BYTES)
    return f'{ALGORITHM}${ITERATIONS}${salt.hex()}${dk.hex()}'


def verify_password(client_hash: str, stored: str) -> bool:
    """
    用途说明：校验前端传来的密码哈希与存储的加盐哈希是否匹配（常量时间比较，防时序攻击）。
    入参说明：
        client_hash (str) - 前端传输的密码 SHA-256 哈希值。
        stored (str) - 配置中存储的加盐哈希字符串。
    返回值说明：bool - 匹配返回 True；格式非法或不匹配返回 False。
    """
    try:
        parts = stored.split('$')
        if len(parts) != 4 or parts[0] != ALGORITHM:
            return False
        iterations: int = int(parts[1])
        salt: bytes = bytes.fromhex(parts[2])
        expected: bytes = bytes.fromhex(parts[3])
        dk: bytes = hashlib.pbkdf2_hmac('sha256', client_hash.encode('utf-8'), salt, iterations, dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except Exception as e:
        LogUtils.error(t('password_verify_error', error=str(e)))
        return False