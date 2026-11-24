import logging
import os
import sys
import traceback
from typing import Any, Optional, Tuple

# 确保项目根目录在 sys.path 中
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.common.log_utils import LogUtils
from backend.db.db_manager import db_manager
from backend.common.i18n_utils import I18nUtils, t
from backend.setting.setting_service import settingService

# 1. 优先初始化 i18n 环境
# 初始化前默认是 en，此处读取配置中的语言
current_lang = settingService.get_config().user_data.language
I18nUtils.init(language=current_lang)

# 2. 初始化日志
LogUtils.init(level=logging.DEBUG)

from flask import Flask, request, redirect
from flask_cors import CORS
from waitress import serve
from backend.auth.auth_manager import auth_manager
from backend.auth.auth_middleware import get_request_token
from backend.auth.auth_routes import auth_bp
from backend.db.db_constants import DBConstants
from backend.setting.setting_routes import setting_bp
from backend.file_repository.file_repository_routes import file_repo_bp
from backend.file_name_repository.file_name_repository_routes import file_name_repo_bp
from backend.system.system_routes import system_bp
from backend.repository.repository_routes import repository_bp
from backend.repository.repository_service import repositoryService
from backend.organize.organize_routes import organize_bp
from backend.album.album_routes import album_bp
from backend.user.user_routes import user_bp
from backend.user.user_service import userService
from backend.common.repo_context import set_current_repo_id, get_current_repo_id, DEFAULT_REPO_ID
from backend.common.response import error_response
from backend.common.heartbeat_service import HeartbeatService
from config import GlobalConfig


# 初始化 Flask
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')

# 允许跨域
CORS(app, resources={r"/api/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization", "X-Repo-Id"])

@app.before_request
def inject_repo_context() -> None:
    """
    用途说明：从请求头、查询参数或 JSON Body 解析当前仓库 ID 并注入请求上下文，缺省回退到默认仓库。
    入参说明：无
    返回值说明：无
    """
    repo_id: int = DEFAULT_REPO_ID
    raw_repo_id: Optional[str] = request.headers.get('X-Repo-Id') or request.args.get('repo_id')
    if not raw_repo_id and request.is_json:
        data: Any = request.get_json(silent=True)
        if isinstance(data, dict):
            body_repo_id: Any = data.get('repo_id')
            raw_repo_id = str(body_repo_id) if body_repo_id is not None else None
    if raw_repo_id:
        try:
            parsed_repo_id: int = int(raw_repo_id)
            if parsed_repo_id > 0:
                repo_id = parsed_repo_id
        except (ValueError, TypeError):
            repo_id = DEFAULT_REPO_ID
    set_current_repo_id(repo_id)


# 成员仅允许访问相册浏览所需的只读接口；其余仓库能力必须由仓库管理员或系统管理员使用。
_REPO_SCOPED_PREFIXES: tuple[str, ...] = (
    '/api/album/',
    '/api/file_repository/',
    '/api/file_name_repository/',
    '/api/organize/',
)
_MEMBER_ALLOWED_PATHS: set[str] = {
    '/api/album/list',
    '/api/album/media',
    '/api/album/download',
    '/api/file_repository/thumbnail/view',
    '/api/file_repository/thumbnail/ensure',
    '/api/system/version',
}


@app.before_request
def enforce_repo_permissions() -> Optional[Tuple[Any, int]]:
    """
    用途说明：在业务路由前校验当前用户的仓库可见性与成员只读边界。
    入参说明：无（Token、用户名与仓库 ID 均从当前请求上下文获取）。
    返回值说明：Optional[Tuple[Any, int]] - 无权限时返回 403 响应，否则返回 None 交给路由鉴权。
    """
    path: str = request.path
    is_repo_scoped: bool = path.startswith(_REPO_SCOPED_PREFIXES)
    is_member_restricted_global: bool = path.startswith(('/api/setting/', '/api/system/'))
    if not path.startswith('/api/') or not (is_repo_scoped or is_member_restricted_global):
        return None
    token: Optional[str] = get_request_token()
    if not token:
        return None
    is_valid: bool
    username: str
    is_valid, username = auth_manager.is_authenticated(token)
    if not is_valid:
        return None
    permission: Optional[str] = userService.get_repo_permission(username, get_current_repo_id())
    if not permission:
        LogUtils.error(t('user_repo_permission_denied_log', username=username, path=path))
        return error_response(t('user_repo_permission_denied'), 403)
    if permission == DBConstants.UserRepositoryPermission.PERMISSION_MEMBER and path not in _MEMBER_ALLOWED_PATHS:
        LogUtils.error(t('user_repo_member_readonly_log', username=username, path=path))
        return error_response(t('user_repo_member_readonly'), 403)
    return None

# 日志脱敏：命中以下字段名的值一律以掩码代替，防止密码/Token 泄露到日志
_SENSITIVE_LOG_KEYS = {'password', 'password_hash', 'old_password', 'new_password', 'token'}


def _mask_token(token: Any) -> str:
    """
    用途：对日志中的 Token 做脱敏，仅保留前 8 位便于排查，其余以 *** 代替
    入参说明：token: 原始 Token 值（可能为 None 或其他类型）
    返回值说明：脱敏后的字符串，空值返回空字符串
    """
    if not token:
        return ''
    token_str: str = str(token)
    return token_str[:8] + '***'


def _sanitize_log_data(data: Any) -> Any:
    """
    用途：递归复制请求数据并对敏感字段脱敏，不修改原始请求对象
    入参说明：data: 请求体/查询参数字典（或列表、标量）
    返回值说明：脱敏后的同结构数据副本
    """
    if isinstance(data, dict):
        return {
            key: ('******' if key in _SENSITIVE_LOG_KEYS else _sanitize_log_data(value))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_sanitize_log_data(item) for item in data]
    return data


@app.before_request
def log_request_info() -> None:
    """
    用途：记录接口请求信息（Token 与密码类字段脱敏后落日志）
    """
    if request.path.startswith('/api'):
        token = request.headers.get('Authorization')
        data = ""
        if request.is_json:
            data = request.get_json(silent=True)
            if not token and data:
                token = data.get('token')
        elif request.form:
            data = dict(request.form)
        elif request.args:
            data = dict(request.args)
        LogUtils.api(t('log_api_request', method=request.method, path=request.path,
                       token=_mask_token(token), data=_sanitize_log_data(data)))

@app.route('/')
def index() -> Any:
    """
    用途说明：默认跳转到登录页面，并携带系统设置的语言参数。
    返回值说明：Any - Flask 重定向响应。
    """
    # 获取系统当前配置的语言
    lang: str = settingService.get_config().user_data.language
    return redirect(f'/login/login.html?lang={lang}')

# --- 异常处理句柄 ---

@app.errorhandler(400)
def bad_request(e: Any) -> Tuple[Any, int]:
    return error_response(t('request_params_error'), 400)

@app.errorhandler(404)
def page_not_found(e: Any) -> Any:
    if request.path.startswith('/api'):
        return error_response(t('api_not_found'), 404)
    return "404 Not Found", 404

@app.errorhandler(Exception)
def handle_global_exception(e: Exception) -> Tuple[Any, int]:
    """
    用途：【API层统一捕获】拦截所有未处理的异常，记录堆栈日志并返回 500
    入参说明：e (Exception): 异常对象
    返回值说明：Response: 统一格式的错误响应
    """
    # 1. 记录详细的错误堆栈到日志文件，方便排查
    error_stack: str = traceback.format_exc()
    LogUtils.error(t('sys_unhandled_exception', path=request.path, stack=error_stack))
    
    # 2. 返回标准错误格式
    return error_response(t('internal_error', error=str(e)), 500)

# 注册蓝图
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(setting_bp, url_prefix='/api/setting')
app.register_blueprint(file_repo_bp, url_prefix='/api/file_repository')
app.register_blueprint(file_name_repo_bp, url_prefix='/api/file_name_repository')
app.register_blueprint(system_bp, url_prefix='/api/system')
app.register_blueprint(repository_bp, url_prefix='/api/repository')
app.register_blueprint(organize_bp, url_prefix='/api/organize')
app.register_blueprint(album_bp, url_prefix='/api/album')
app.register_blueprint(user_bp, url_prefix='/api/user')

def start_server() -> None:
    # 初始化主数据库（仓库元数据）与默认仓库
    db_manager.init_master()
    repositoryService.init_default_repo()
    # 初始化全局用户账户（首次启动把现有配置用户迁移为初始管理员）
    userService.init_admin_user()
    # 密码恢复通道：setting.json 中的密码被改动时据此重设初始管理员密码（须在用户初始化之后执行）
    settingService.apply_password_reset()
    # 首次运行生成默认文件名整理脚本（整理脚本路径留空时使用；已存在则不覆盖）
    from backend.organize.rename_script import ensure_default_script
    ensure_default_script()
    # 初始化默认仓库业务库
    db_manager.init_db()

    # 启动心跳服务
    HeartbeatService.start()

    # 注册日志自动清理任务（每天 12:00 按系统时区清理过期日志）
    from backend.system.log_cleanup_service import LogCleanupService
    LogCleanupService.start()

    # 启动后台定时任务调度器（按仓库独立调度）
    from backend.file_repository.auto_scan_service import AutoScanService
    AutoScanService.refresh_config()
    # 以观察者方式监听配置变更，使设置模块与文件仓库模块解耦
    settingService.register_change_callback(AutoScanService.on_config_changed)
    repositoryService.register_config_change_callback(AutoScanService.on_repo_config_changed)
    repositoryService.register_delete_callback(AutoScanService.on_repo_deleted)

    LogUtils.info(t('sys_starting', port=GlobalConfig.SYSTEM_PORT))
    LogUtils.info(t('sys_address', url=f"http://localhost:{GlobalConfig.SYSTEM_PORT}"))
    serve(app, host='0.0.0.0', port=GlobalConfig.SYSTEM_PORT, threads=8)

if __name__ == '__main__':
    start_server()
