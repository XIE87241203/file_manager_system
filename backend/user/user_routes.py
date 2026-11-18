from dataclasses import asdict
from typing import Any, Tuple

from flask import Blueprint, request

from backend.auth.auth_middleware import token_required, admin_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.response import success_response, error_response
from backend.user.user_models import CurrentUserResult, LoginHistoryPageResult
from backend.user.user_service import userService

# 创建用户管理模块的蓝图
user_bp = Blueprint('user', __name__)


@user_bp.route('/me', methods=['GET'])
@token_required
def get_current_user() -> Tuple[Any, int]:
    """
    用途说明：获取当前登录用户信息（登录名与是否管理员），供前端判断是否展示用户管理入口。
    入参说明：无（用户名由 Token 解析注入 request.username）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 CurrentUserResult 字典（username, is_admin）。
    """
    username: str = request.username
    result = CurrentUserResult(username=username, is_admin=userService.is_admin(username))
    return success_response(t('user_me_success'), data=asdict(result))


@user_bp.route('/list', methods=['GET'])
@admin_required
def list_users() -> Tuple[Any, int]:
    """
    用途说明：获取所有用户列表（仅管理员，不含密码哈希）。
    入参说明：无。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 UserResult 字典列表。
    """
    LogUtils.debug(t('user_list_log', user=request.username))
    users = userService.list_users()
    return success_response(t('user_list_success'), data=[asdict(u) for u in users])


@user_bp.route('/add', methods=['POST'])
@admin_required
def add_user() -> Tuple[Any, int]:
    """
    用途说明：新增普通用户（仅管理员）。
    入参说明：JSON Body，字段：
        username (str): 登录名；
        password_hash (str): 前端传输的密码 SHA-256 哈希。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功或失败（重名/缺参等）均带提示消息。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    username = data.get('username')
    password_hash = data.get('password_hash')
    if not isinstance(username, str) or not isinstance(password_hash, str):
        return error_response(t('request_params_error'), 400)

    LogUtils.info(t('user_add_request_log', user=request.username))
    success, message = userService.add_user(username, password_hash)
    if success:
        return success_response(message)
    return error_response(message, 400)


@user_bp.route('/delete', methods=['POST'])
@admin_required
def delete_user() -> Tuple[Any, int]:
    """
    用途说明：删除用户（仅管理员，禁止删除自己与最后一个管理员）。
    入参说明：JSON Body，字段：id (int): 待删除用户 ID。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功或失败均带提示消息。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    user_id = data.get('id')
    if not isinstance(user_id, int):
        return error_response(t('request_params_error'), 400)

    LogUtils.info(t('user_delete_request_log', user=request.username))
    success, message = userService.delete_user(user_id, request.username)
    if success:
        return success_response(message)
    return error_response(message, 400)


@user_bp.route('/update_password', methods=['POST'])
@admin_required
def update_password() -> Tuple[Any, int]:
    """
    用途说明：修改指定用户密码（仅管理员），修改后该用户现有 Token 立即失效。
    入参说明：JSON Body，字段：
        id (int): 目标用户 ID；
        password_hash (str): 前端传输的新密码 SHA-256 哈希。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功或失败均带提示消息。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    user_id = data.get('id')
    password_hash = data.get('password_hash')
    if not isinstance(user_id, int) or not isinstance(password_hash, str):
        return error_response(t('request_params_error'), 400)

    LogUtils.info(t('user_password_request_log', user=request.username))
    success, message = userService.update_password(user_id, password_hash)
    if success:
        return success_response(message)
    return error_response(message, 400)


@user_bp.route('/login_history', methods=['GET'])
@admin_required
def get_login_history() -> Tuple[Any, int]:
    """
    用途说明：分页查询指定用户的登录历史（仅管理员，按登录时间倒序）。
    入参说明：Query 参数：
        id (int): 目标用户 ID，必填；
        page (int): 页码，默认 1；
        page_size (int): 每页条数，默认 10。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 LoginHistoryPageResult 字典
        （total: 总条数, page: 当前页, page_size: 每页条数, list: [{login_time, ip}]）。
    """
    user_id = request.args.get('id', type=int)
    if user_id is None:
        return error_response(t('request_params_error'), 400)
    page: int = request.args.get('page', default=1, type=int)
    page_size: int = request.args.get('page_size', default=10, type=int)

    LogUtils.debug(t('user_login_history_log', user=request.username, target_id=user_id))
    result: LoginHistoryPageResult = userService.get_login_history(user_id, page, page_size)
    return success_response(t('user_login_history_success'), data=asdict(result))