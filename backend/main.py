import os
import sys
import logging
from typing import Any

# 确保项目根目录在 sys.path 中，以便正常导入 config 和 backend 模块
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.common.log_utils import LogUtils
from flask import Flask, request, Response, send_from_directory
from flask_cors import CORS
from waitress import serve
from backend.auth.auth_routes import auth_bp
from backend.setting.setting_routes import setting_bp
from backend.file_repository.file_repository_routes import file_repo_bp
from backend.common.response import error_response
from config import GlobalConfig

# 初始化日志
LogUtils.init(level=logging.DEBUG)

# 初始化 Flask，配置静态文件目录为根目录下的 frontend 文件夹
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')

# 允许跨域请求（主要针对开发环境或跨域工具调用）
CORS(app, resources={r"/api/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"])

@app.before_request
def log_request_info() -> None:
    """
    用途说明：Flask 钩子函数，在每个请求处理前自动记录 API 请求信息。
    入参说明：无
    返回值说明：无
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
        LogUtils.debug(f"接口请求 -> 方法: {request.method}, 路径: {request.path}, Token: {token}, 参数: {data}")

@app.route('/')
def index() -> Any:
    """
    用途说明：根路由处理，默认返回登录页面。
    入参说明：无
    返回值说明：登录页面的 HTML 内容。
    """
    return send_from_directory(app.static_folder, 'login/login.html')

@app.errorhandler(400)
def bad_request(e: Any) -> Response:
    """
    用途说明：全局处理 400 错误，返回 JSON 格式。
    入参说明：e (错误对象)
    返回值说明：JSON 格式的错误响应。
    """
    return error_response("请求参数错误或格式非法", 400)

@app.errorhandler(404)
def page_not_found(e: Any) -> Any:
    """
    用途说明：全局处理 404 错误。如果是 API 请求返回 JSON，否则返回 404 提示。
    入参说明：e (错误对象)
    返回值说明：JSON 响应或错误信息字符串。
    """
    if request.path.startswith('/api'):
        return error_response("请求的接口不存在", 404)
    return "404 Not Found", 404

@app.errorhandler(500)
def server_error(e: Any) -> Response:
    """
    用途说明：全局处理 500 错误，记录日志并返回 JSON。
    入参说明：e (错误对象)
    返回值说明：JSON 格式的错误响应。
    """
    LogUtils.error(f"服务器内部错误: {str(e)}")
    return error_response("服务器内部错误", 500)

# 注册功能模块蓝图
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(setting_bp, url_prefix='/api/setting')
app.register_blueprint(file_repo_bp, url_prefix='/api/file_repository')

def start_server() -> None:
    """
    用途说明：启动全栈服务（托管前端静态文件 + 后端 API）。
    入参说明：无
    返回值说明：无
    """
    LogUtils.info(f"系统服务正在启动 (Port: {GlobalConfig.SYSTEM_PORT})...")
    LogUtils.info(f"访问地址: http://localhost:{GlobalConfig.SYSTEM_PORT}")
    
    # 使用 Waitress 作为生产级服务器
    serve(app, host='0.0.0.0', port=GlobalConfig.SYSTEM_PORT, threads=8)

if __name__ == '__main__':
    start_server()
