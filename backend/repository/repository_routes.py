from dataclasses import asdict
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, request

from backend.auth.auth_middleware import token_required, admin_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import get_current_repo_id
from backend.common.response import success_response, error_response
from backend.db.db_constants import DBConstants
from backend.repository.repository_service import repositoryService
from backend.user.user_service import userService

# 创建仓库管理模块的蓝图
repository_bp = Blueprint('repository', __name__)


@repository_bp.route('/list', methods=['GET'])
@token_required
def list_repos() -> Tuple[Any, int]:
    """
    用途：获取当前用户可见的仓库列表，并附带各仓库权限。
    入参说明：无（当前用户名由 Token 注入）。
    返回值说明：包含仓库列表 (List[RepositoryResult]) 的 JSON 响应。
    """
    repos = repositoryService.list_repos_for_user(request.username)
    return success_response(t('repo_list_success'), data=[asdict(r) for r in repos])


@repository_bp.route('/create', methods=['POST'])
@admin_required
def create_repo() -> Tuple[Any, int]:
    """
    用途：创建新仓库（仅系统管理员）。
    入参说明：JSON 对象，包含 name (str) 仓库名称。
    返回值说明：包含新仓库信息 (RepositoryResult) 的 JSON 响应。
    """
    data: Optional[Dict[str, Any]] = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))
    name: str = data.get('name', '')
    result = repositoryService.create_repo(name)
    if result:
        return success_response(t('repo_create_success'), data=asdict(result))
    return error_response(t('repo_create_failed'))


@repository_bp.route('/delete', methods=['POST'])
@admin_required
def delete_repo() -> Tuple[Any, int]:
    """
    用途：删除指定仓库（仅系统管理员，保留磁盘物理文件）。
    入参说明：JSON 对象，包含 id (int) 仓库 ID。
    返回值说明：操作结果响应。
    """
    data: Optional[Dict[str, Any]] = request.get_json(silent=True)
    if not data or data.get('id') is None:
        return error_response(t('request_params_error'))
    repo_id: int = int(data['id'])
    if repositoryService.delete_repo(repo_id):
        return success_response(t('repo_delete_success'))
    return error_response(t('repo_delete_failed'))


@repository_bp.route('/config', methods=['GET'])
@token_required
def get_config() -> Tuple[Any, int]:
    """
    用途：获取指定仓库的独立配置（仅系统管理员或该仓库管理员），未传 id 时取当前上下文仓库。
    入参说明：Query 参数 id (int, 可选) 仓库 ID。
    返回值说明：包含仓库配置 (FileRepositorySettings) 的 JSON 响应。
    """
    repo_id: Optional[int] = request.args.get('id', type=int)
    if repo_id is None:
        repo_id = get_current_repo_id()
    if userService.get_repo_permission(request.username, repo_id) != DBConstants.UserRepositoryPermission.PERMISSION_ADMIN:
        return error_response(t('user_repo_admin_required'), 403)
    config = repositoryService.get_config(repo_id)
    return success_response(t('repo_config_get_success'), data=asdict(config))


@repository_bp.route('/config/update', methods=['POST'])
@token_required
def update_config() -> Tuple[Any, int]:
    """
    用途：更新指定仓库的独立配置（仅系统管理员或该仓库管理员）。
    入参说明：JSON 对象，包含 id (int) 仓库 ID 及待更新的配置字段。
    返回值说明：操作结果响应。
    """
    data: Optional[Dict[str, Any]] = request.get_json(silent=True)
    if not data or data.get('id') is None:
        return error_response(t('request_params_error'))
    repo_id: int = int(data['id'])
    if userService.get_repo_permission(request.username, repo_id) != DBConstants.UserRepositoryPermission.PERMISSION_ADMIN:
        return error_response(t('user_repo_admin_required'), 403)
    if repositoryService.update_config(repo_id, data):
        return success_response(t('repo_config_update_success'))
    return error_response(t('repo_config_update_failed'))