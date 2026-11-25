from flask import Blueprint, request

from backend.auth.auth_manager import auth_manager
from backend.auth.auth_middleware import token_required
from backend.common.i18n_utils import I18nUtils, t
from backend.common.log_utils import LogUtils
from backend.common.response import success_response, error_response
from backend.setting.setting_service import settingService

# 创建认证模块的蓝图
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用途：提供登录验证 API 接口，登录成功后返回 Token
    入参说明：JSON 对象，包含 username、password_hash 和可选的 language（zh 或 en）
    返回值说明：JSON 格式的成功或失败状态，成功时包含 token
    """
    data = request.get_json(silent=True)
    if not data:
        LogUtils.error(t('auth_login_data_error'))
        return error_response(t('request_data_empty'), 400)

    username = data.get('username')
    password_hash = data.get('password_hash')
    requested_language = data.get('language')
    language: str = requested_language if requested_language in ('zh', 'en') \
        else settingService.get_config().user_data.language
    # 取请求来源 IP，用于登录失败锁定
    ip: str = request.remote_addr or ''

    LogUtils.info(t('auth_attempt_login', username=username))

    # 先检查该 (IP, 用户名) 是否处于锁定期
    locked, remaining_minutes = auth_manager.check_lock(ip, username or '')
    if locked:
        message = I18nUtils.get_for_language(language, 'auth_login_locked', minutes=remaining_minutes)
        return error_response(message, 403)

    # 调用验证管理器处理业务逻辑，失败提示按登录页当前选择返回
    success, message, token = auth_manager.verify_login(username, password_hash, ip, language)

    if success:
        # 只有身份验证成功后才持久化语言，避免未登录请求修改全站配置
        if settingService.get_config().user_data.language != language:
            settingService.update_settings({'user_data': {'language': language}}, username)
        LogUtils.info(t('auth_login_log_success', username=username))
        return success_response(message, data={"token": token})
    else:
        LogUtils.error(t('auth_login_log_failed', username=username, message=message))
        # 本次失败若刚好触发锁定，返回 403 及锁定提示
        locked, remaining_minutes = auth_manager.check_lock(ip, username or '')
        if locked:
            message = I18nUtils.get_for_language(language, 'auth_login_locked', minutes=remaining_minutes)
            return error_response(message, 403)
        return error_response(message, 401)

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    """
    用途：提供注销登录 API 接口
    入参说明：无（通过 Header 携带 Token）
    返回值说明：JSON 格式的注销状态
    """
    token = request.headers.get('Authorization') or request.json.get('token')
    
    LogUtils.info(t('auth_attempt_logout', username=request.username))
    
    success, message = auth_manager.logout(token)
    if success:
        LogUtils.info(t('auth_logout_log_success', username=request.username))
        return success_response(message)
    else:
        LogUtils.error(t('auth_logout_log_failed', username=request.username, message=message))
        return error_response(message, 401)
