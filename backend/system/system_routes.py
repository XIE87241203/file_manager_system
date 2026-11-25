from dataclasses import asdict
from typing import Any, Tuple

from flask import Blueprint, request

from backend.auth.auth_middleware import token_required
from backend.common.i18n_utils import t
from backend.common.response import error_response, success_response
from backend.db.db_constants import DBConstants
from backend.system.changelog_models import ChangelogResult
from backend.system.changelog_service import ChangelogService
from backend.system.system_service import LogDirectoryInfo, SystemService
from backend.user.user_service import userService
from config import GlobalConfig

# 创建系统管理模块的蓝图
system_bp = Blueprint('system', __name__)


def _can_view_changelog(username: str) -> bool:
    """
    用途说明：判断用户是否有权查看更新日志。
    入参说明：username (str): 已通过 Token 校验的登录名。
    返回值说明：bool: 系统管理员或任一仓库管理员返回 True，普通成员返回 False。
    """
    if userService.is_admin(username):
        return True
    permissions: dict[int, str] = userService.get_repo_permissions(username)
    return any(
        permission == DBConstants.UserRepositoryPermission.PERMISSION_ADMIN
        for permission in permissions.values()
    )


@system_bp.route('/changelog', methods=['GET'])
@token_required
def get_changelog() -> Tuple[Any, int]:
    """
    用途说明：获取首页更新日志，支持全部展示和仅展示未读版本。
    入参说明：Query 参数 scope (str, 可选): all 或 unread，默认 unread；用户名来自 Token。
    返回值说明：Tuple[Any, int]: 统一 JSON 响应，data 包含当前版本、已读版本、自动弹出标识和日志条目。
    """
    if not _can_view_changelog(request.username):
        return error_response(t('sys_changelog_forbidden'), 403)
    scope: str = request.args.get('scope', default='unread', type=str)
    if scope not in ('all', 'unread'):
        return error_response(t('sys_changelog_scope_invalid'), 400)
    try:
        seen_version: str | None = userService.get_changelog_seen_version(request.username)
        result: ChangelogResult = ChangelogService.get_changelog(scope, seen_version)
        return success_response(t('sys_changelog_get_success'), data=asdict(result), log=False)
    except Exception:
        return error_response(t('sys_changelog_load_failed'), 500)


@system_bp.route('/changelog/read', methods=['POST'])
@token_required
def mark_changelog_read() -> Tuple[Any, int]:
    """
    用途说明：记录当前用户已看过指定版本的更新日志。
    入参说明：JSON Body 字段 version (str): 弹窗展示的当前版本号，必须存在于日志文件；用户名来自 Token。
    返回值说明：Tuple[Any, int]: 统一 JSON 响应，成功时不再自动弹出同版本日志。
    """
    if not _can_view_changelog(request.username):
        return error_response(t('sys_changelog_forbidden'), 403)
    data: Any = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('version'), str):
        return error_response(t('sys_changelog_version_invalid'), 400)
    version: str = data['version'].strip()
    if not ChangelogService.is_known_version(version):
        return error_response(t('sys_changelog_version_unknown'), 400)
    if not userService.mark_changelog_seen(request.username, version):
        return error_response(t('sys_changelog_save_failed'), 500)
    return success_response(t('sys_changelog_save_success'), log=False)


@system_bp.route('/logs', methods=['GET'])
@token_required
def get_logs():
    """
    用途说明：获取最新的系统日志，支持关键词、等级筛选以及 API 过滤。
    入参说明：
        Query 参数 lines (int, 可选) - 读取的行数，默认 200。
        Query 参数 keyword (str, 可选) - 搜索关键词，支持 *。
        Query 参数 level (str, 可选) - 日志等级 (INFO/DEBUG/ERROR/ALL)。
        Query 参数 exclude_api (str, 可选) - 是否过滤 API 日志 ("true"/"false")。
    返回值说明：JSON 响应，data 字段包含日志行列表。
    """
    lines: int = request.args.get('lines', default=200, type=int)
    keyword: str = request.args.get('keyword', default=None, type=str)
    level: str = request.args.get('level', default='ALL', type=str)
    exclude_api_str: str = request.args.get('exclude_api', default='false', type=str)
    exclude_api: bool = exclude_api_str.lower() == 'true'
    
    logs: list = SystemService.get_latest_logs(lines, keyword, level, exclude_api)
    return success_response(t('sys_get_logs_success'), data={"logs": logs}, log=False)

@system_bp.route('/logs/files', methods=['GET'])
@token_required
def get_log_files():
    """
    用途说明：获取所有可用的日志文件列表。
    返回值说明：JSON 响应，data 字段包含文件名列表。
    """
    files: list = SystemService.get_available_log_files()
    return success_response(t('sys_get_log_files_success'), data={"files": files})

@system_bp.route('/logs/size', methods=['GET'])
@token_required
def get_log_dir_size():
    """
    用途说明：获取当前日志目录的总大小与文件数量。
    入参说明：无。
    返回值说明：JSON 响应，data 字段包含 size_bytes（字节数）与 file_count（文件数量）。
    """
    info: LogDirectoryInfo = SystemService.get_log_dir_size()
    return success_response(t('sys_get_log_size_success'), data=asdict(info), log=False)

@system_bp.route('/version', methods=['GET'])
def get_app_version():
    """
    用途说明：获取当前应用的后端版本号（公开接口）。
    入参说明：无。
    返回值说明：JSON 响应，data 字段包含应用程序版本号。
    """
    app_version: str = GlobalConfig.APP_VERSION
    return success_response(t('sys_get_version_success'), data={"version": app_version}, log=False)
