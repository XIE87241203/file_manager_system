import os
import sys
import logging

# 1. 优先处理路径，确保后续导入正常
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. 最早初始化日志工具
from backend.common.log_utils import LogUtils
LogUtils.init(level=logging.DEBUG)

# 3. 之后再导入其他业务模块
from flask import Flask, request, jsonify
from flask_cors import CORS
from backend.auth.auth_routes import auth_bp
from backend.setting.setting_routes import setting_bp
from backend.file_repository.file_repository_routes import file_repo_bp
from backend.common.response import error_response

app = Flask(__name__)
# 允许跨域请求，并显式允许 Authorization 头部
CORS(app, resources={r"/api/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"])

@app.before_request
def log_request_info():
    """
    用途：Flask 钩子函数，在每个请求处理前自动记录请求信息
    入参说明：无
    返回值说明：无
    """
    # 尝试从 Header 获取 Token
    token = request.headers.get('Authorization')
    
    data = ""
    if request.is_json:
        data = request.get_json(silent=True)
        # 如果 Header 中没有 Token，尝试从 JSON Body 中获取
        if not token and data:
            token = data.get('token')
    elif request.form:
        data = dict(request.form)
    elif request.args:
        data = dict(request.args)
        
    LogUtils.debug(f"接口请求 -> 方法: {request.method}, 路径: {request.path}, Token: {token}, 参数: {data}")

# --- 全局错误处理，确保始终返回 JSON ---

@app.errorhandler(400)
def bad_request(e):
    """
    用途：处理 400 错误，返回 JSON
    入参说明：e - 错误对象
    返回值说明：JSON 格式的错误响应
    """
    return error_response("请求参数错误或格式非法", 400)

@app.errorhandler(404)
def page_not_found(e):
    """
    用途：处理 404 错误，返回 JSON
    入参说明：e - 错误对象
    返回值说明：JSON 格式的错误响应
    """
    return error_response("请求的接口不存在", 404)

@app.errorhandler(500)
def server_error(e):
    """
    用途：处理 500 错误，返回 JSON
    入参说明：e - 错误对象
    返回值说明：JSON 格式的错误响应
    """
    return error_response("服务器内部错误", 500)

# ------------------------------------

# 4. 注册蓝图 (Blueprints)
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(setting_bp, url_prefix='/api/setting')
app.register_blueprint(file_repo_bp, url_prefix='/api/file_repository')

if __name__ == '__main__':
    LogUtils.info("后端服务正在启动...")
    # 运行在 5000 端口，监听所有接口以支持 Docker 访问
    app.run(host='0.0.0.0', port=5000, debug=False)
