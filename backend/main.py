import logging
import os
import sys
import traceback
from typing import Any, Tuple

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
from backend.auth.auth_routes import auth_bp
from backend.setting.setting_routes import setting_bp
from backend.file_repository.file_repository_routes import file_repo_bp
from backend.file_name_repository.file_name_repository_routes import file_name_repo_bp
from backend.system.system_routes import system_bp
from backend.common.response import error_response
from backend.common.heartbeat_service import HeartbeatService
from config import GlobalConfig


# 初始化 Flask
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')

# 允许跨域
CORS(app, resources={r"/api/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"])

@app.before_request
def log_request_info() -> None:
    """
    用途：记录接口请求信息
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
        LogUtils.api(t('log_api_request', method=request.method, path=request.path, token=token, data=data))

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

def start_server() -> None:
    db_manager.init_db()
    
    # 启动心跳服务
    HeartbeatService.start()
    
    # 启动后台定时任务调度器
    from backend.file_repository.auto_scan_service import AutoScanService
    AutoScanService.refresh_config()
    
    LogUtils.info(t('sys_starting', port=GlobalConfig.SYSTEM_PORT))
    LogUtils.info(t('sys_address', url=f"http://localhost:{GlobalConfig.SYSTEM_PORT}"))
    serve(app, host='0.0.0.0', port=GlobalConfig.SYSTEM_PORT, threads=8)

if __name__ == '__main__':
    start_server()
