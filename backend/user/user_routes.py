from dataclasses import asdict
from typing import Any, List, Optional, Tuple

from flask import Blueprint, request

from backend.auth.auth_middleware import token_required, admin_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import get_current_repo_id
from backend.common.response import success_response, error_response
from backend.user.user_models import (
    CurrentUserResult,
    LoginHistoryPageResult,
    RepositoryPermissionInfo,
    UserRepositoryPermissionResult,
)
from backend.user.user_service import userService

# 创建用户管理模块的蓝图
user_bp = Blueprint('user', __name__)


def _parse_permission_items(data: Any) -> Optional[List[RepositoryPermissionInfo]]:
    """
    用途说明：解析用户仓库权限配置请求体。
    入参说明：data (Any): 请求 JSON 字典，permissions 为 [{repo_id, permission}] 列表。
    返回值说明：Optional[List[RepositoryPermissionInfo]] - 解析后的权限输入列表；格式非法时返回 None。
    """
    raw_items: Any = data.get('permissions', [])
    if not isinstance(raw_items, list):
        return None
    results: List[RepositoryPermissionInfo] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            return None
        repo_id: Any = raw_item.get('repo_id')
        permission: Any = raw_item.get('permission')
        if isinstance(repo_id, bool) or not isinstance(repo_id, int) or repo_id <= 0:
            return None
        if not isinstance(permission, str):
            return None
        results.append(RepositoryPermissionInfo(repo_id=repo_id, permission=permission))
    return results


@user_bp.route('/me', methods=['GET'])
@token_required
def get_current_user() -> Tuple[Any, int]:
    """
    用途说明：获取当前登录用户信息（登录名、系统角色与当前仓库权限），供前端控制菜单和操作入口。
    入参说明：无（用户名由 Token 解析注入 request.username，仓库由请求上下文注入）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 CurrentUserResult 字典（username, is_admin, repo_permission）。
    """
    username: str = request.username
    result = CurrentUserResult(
        username=username,
        is_admin=userService.is_admin(username),
        repo_permission=userService.get_repo_permission(username, get_current_repo_id()) or ''
    )
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
    用途说明：新增系统管理员或系统使用者（仅系统管理员可调用）。
    入参说明：JSON Body，字段：
        username (str): 登录名；
        password_hash (str): 前端传输的密码 SHA-256 哈希；
        is_admin (bool): True 为系统管理员，False 为系统使用者；
        permissions (list): 系统使用者的仓库授权列表，元素为 {repo_id, permission}。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功或失败（重名/缺参/权限非法等）均带提示消息。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    username = data.get('username')
    password_hash = data.get('password_hash')
    is_admin: Any = data.get('is_admin', False)
    if not isinstance(username, str) or not isinstance(password_hash, str) or not isinstance(is_admin, bool):
        return error_response(t('request_params_error'), 400)
    permissions: Optional[List[RepositoryPermissionInfo]] = _parse_permission_items(data)
    if permissions is None:
        return error_response(t('request_params_error'), 400)

    LogUtils.info(t('user_add_request_log', user=request.username))
    success, message = userService.add_user(username, password_hash, is_admin, permissions)
    if success:
        return success_response(message)
    return error_response(message, 400)


@user_bp.route('/permissions', methods=['GET'])
@admin_required
def get_user_permissions() -> Tuple[Any, int]:
    """
    用途说明：获取指定用户的完整仓库权限配置（仅系统管理员）。
    入参说明：Query 参数 id (int): 目标用户 ID，必填。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 UserRepositoryPermissionResult 列表。
    """
    user_id: Optional[int] = request.args.get('id', type=int)
    if user_id is None:
        return error_response(t('request_params_error'), 400)
    permissions: List[UserRepositoryPermissionResult] = userService.list_user_repository_permissions(user_id)
    if not permissions and not userService.get_user_by_id(user_id):
        return error_response(t('user_not_found'), 404)
    return success_response(t('user_repo_permission_get_success'), data=[asdict(item) for item in permissions])


@user_bp.route('/update_permissions', methods=['POST'])
@admin_required
def update_user_permissions() -> Tuple[Any, int]:
    """
    用途说明：整体更新指定系统使用者的仓库可见性与权限（仅系统管理员）。
    入参说明：JSON Body，字段：
        id (int): 目标用户 ID；
        permissions (list): 仓库授权列表，元素为 {repo_id, permission}。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功或失败均带提示消息。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))
    user_id: Any = data.get('id')
    if isinstance(user_id, bool) or not isinstance(user_id, int):
        return error_response(t('request_params_error'), 400)
    permissions: Optional[List[RepositoryPermissionInfo]] = _parse_permission_items(data)
    if permissions is None:
        return error_response(t('request_params_error'), 400)
    LogUtils.info(t('user_repo_permission_update_request_log', user=request.username, target_id=user_id))
    success, message = userService.replace_user_repository_permissions(user_id, permissions)
    if success:
        return success_response(message)
    return error_response(message, 400)


@user_bp.route('/rename', methods=['POST'])
@admin_required
def rename_user() -> Tuple[Any, int]:
    """
    用途说明：重命名用户账号（仅系统管理员），保留原 Token、仓库权限与历史记录。
    入参说明：JSON Body，字段：id (int): 目标用户 ID；username (str): 新登录名。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功或失败均带提示消息。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))
    user_id: Any = data.get('id')
    username: Any = data.get('username')
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0 or not isinstance(username, str):
        return error_response(t('request_params_error'), 400)

    LogUtils.info(t('user_rename_request_log', user=request.username, target_id=user_id))
    success, message = userService.rename_user(user_id, username)
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