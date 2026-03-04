from functools import wraps

from flask import request

from backend.auth.auth_manager import auth_manager
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.response import error_response


def token_required(f):
    """
    用途：装饰器，用于验证请求中是否包含有效的 Token。支持从 Header、JSON Body 或 URL 参数中获取。
    入参说明：f - 被装饰的函数
    返回值说明：返回装饰后的函数，如果验证失败则返回 401 错误响应
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. 优先从 Header 获取 Token
        token = request.headers.get('Authorization')
        
        # 2. 如果 Header 没有，尝试从 JSON Body 获取
        if not token and request.is_json:
            data = request.get_json(silent=True)
            if data:
                token = data.get('token')
        
        # 3. 如果还是没有，尝试从 URL 参数中获取 (用于 <img> 标签预览、视频流等 GET 请求)
        if not token:
            token = request.args.get('token')

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
