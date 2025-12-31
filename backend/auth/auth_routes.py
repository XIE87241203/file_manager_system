from flask import Blueprint, request
from backend.auth.auth_manager import auth_manager
from backend.common.response import success_response, error_response
from backend.common.log_utils import LogUtils
from backend.common.auth_middleware import token_required

# 创建认证模块的蓝图
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用途：提供登录验证 API 接口，登录成功后返回 Token
    入参说明：JSON 对象，包含 username 和 password_hash
    返回值说明：JSON 格式的成功或失败状态，成功时包含 token
    """
    data = request.json
    if not data:
        LogUtils.error("登录失败：请求数据为空")
        return error_response("请求数据不能为空", 400)

    username = data.get('username')
    password_hash = data.get('password_hash')

    LogUtils.info(f"用户尝试登录: {username}")

    # 调用验证管理器处理业务逻辑
    success, message, token = auth_manager.verify_login(username, password_hash)

    if success:
        LogUtils.info(f"用户登录成功: {username}")
        return success_response(message, data={"token": token})
    else:
        LogUtils.error(f"用户登录失败: {username} - {message}")
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
    
    LogUtils.info(f"用户尝试注销: {request.username}")
    
    success, message = auth_manager.logout(token)
    if success:
        LogUtils.info(f"用户注销成功: {request.username}")
        return success_response(message)
    else:
        LogUtils.error(f"用户注销失败: {request.username} - {message}")
        return error_response(message, 401)
