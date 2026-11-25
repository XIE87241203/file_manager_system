from functools import wraps
from typing import Optional

from flask import request

from backend.auth.auth_manager import auth_manager
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.response import error_response
from backend.user.user_service import userService


def get_request_token() -> Optional[str]:
    """
    用途：从当前请求中提取 Token，供鉴权装饰器与仓库权限前置校验共用。
    入参说明：无。
    返回值说明：Optional[str] - 请求 Token；未提供时返回 None。
    """
    token: Optional[str] = request.headers.get('Authorization')
    if not token and request.is_json:
        data = request.get_json(silent=True)
        if data:
            token = data.get('token')
    if not token:
        token = request.args.get('token')
    return token


def token_required(f):
    """
    用途：装饰器，用于验证请求中是否包含有效的 Token。支持从 Header、JSON Body 或 URL 参数中获取。
    入参说明：f - 被装饰的函数
    返回值说明：返回装饰后的函数，如果验证失败则返回 401 错误响应
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token: Optional[str] = get_request_token()
        if not token:
            LogUtils.error(t('auth_token_missing_log', path=request.path))
            return error_response(t('auth_token_missing'), 401)
        
        # 验证 Token 有效性
        is_valid, username = auth_manager.is_authenticated(token)
        if not is_valid:
            LogUtils.error(t('auth_token_invalid_log', token=token, path=request.path))
            return error_response(t('auth_token_expired'), 401)
        
        # 将解析出的用户名存入 request 对象，方便后续业务逻辑使用
        request.username = username
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """
    用途：装饰器，在 Token 验证的基础上进一步校验当前用户是否为管理员，非管理员返回 403。
    入参说明：f - 被装饰的函数
    返回值说明：返回装饰后的函数，验证失败返回 401（未登录）或 403（非管理员）错误响应
    """
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if not userService.is_admin(request.username):
            LogUtils.error(t('user_admin_required_log', username=request.username, path=request.path))
            return error_response(t('user_admin_required'), 403)
        return f(*args, **kwargs)
    return decorated