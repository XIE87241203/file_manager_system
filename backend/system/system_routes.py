from flask import Blueprint, request

from backend.common.auth_middleware import token_required
from backend.common.response import success_response
from backend.system.system_service import SystemService
from config import GlobalConfig

# 创建系统管理模块的蓝图
system_bp = Blueprint('system', __name__)

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
    return success_response("获取日志成功", data={"logs": logs}, log=False)

@system_bp.route('/logs/files', methods=['GET'])
@token_required
def get_log_files():
    """
    用途说明：获取所有可用的日志文件列表。
    返回值说明：JSON 响应，data 字段包含文件名列表。
    """
    files: list = SystemService.get_available_log_files()
    return success_response("获取日志文件列表成功", data={"files": files})

@system_bp.route('/version', methods=['GET'])
def get_app_version():
    """
    用途说明：获取当前应用的后端版本号（公开接口）。
    入参说明：无。
    返回值说明：JSON 响应，data 字段包含应用程序版本号。
    """
    app_version: str = GlobalConfig.APP_VERSION
    return success_response("获取应用版本号成功", data={"version": app_version}, log=False)
