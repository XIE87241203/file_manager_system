import re
from flask import Blueprint, request
from backend.common.response import success_response, error_response
from backend.common.log_utils import LogUtils
from backend.common.auth_middleware import token_required
from backend.file_repository.scan_service import ScanService
from backend.common.db_manager import db_manager
from backend.setting.setting import settings

# 创建文件仓库模块的蓝图
file_repo_bp = Blueprint('file_repository', __name__)

@file_repo_bp.route('/scan', methods=['POST'])
@token_required
def start_scan():
    """
    用途说明：异步触发文件仓库扫描任务
    入参说明：无
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {request.username} 触发了文件仓库扫描")
    if ScanService.start_async_scan():
        return success_response("扫描任务已启动")
    else:
        return error_response("扫描任务已在运行中", 400)

@file_repo_bp.route('/stop', methods=['POST'])
@token_required
def stop_scan():
    """
    用途说明：手动停止正在进行的扫描任务
    入参说明：无
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {request.username} 请求停止扫描任务")
    ScanService.stop_scan()
    return success_response("已发送停止指令")

@file_repo_bp.route('/clear', methods=['POST'])
@token_required
def clear_repository():
    """
    用途说明：清空数据库中的文件索引表
    入参说明：无
    返回值说明：JSON 格式响应，包含操作结果
    """
    LogUtils.info(f"用户 {request.username} 请求清空文件数据库")
    try:
        # 执行删除全表数据的 SQL
        db_manager.execute_update("DELETE FROM file_index")
        # 重置自增 ID (可选)
        db_manager.execute_update("DELETE FROM sqlite_sequence WHERE name='file_index'")
        return success_response("文件索引表已成功清空")
    except Exception as e:
        LogUtils.error(f"清空数据库失败: {e}")
        return error_response(f"清空数据库失败: {str(e)}", 500)

@file_repo_bp.route('/progress', methods=['GET'])
@token_required
def get_scan_progress():
    """
    用途说明：获取当前扫描任务的状态和进度信息
    入参说明：无
    返回值说明：包含 status 和 progress 详情的 JSON 响应
    """
    status_info = ScanService.get_status()
    return success_response("获取进度成功", data=status_info)

@file_repo_bp.route('/list', methods=['GET'])
@token_required
def list_files():
    """
    用途说明：分页并支持正则模糊搜索获取数据库中已索引的文件列表。支持选择搜索当前索引表或历史索引表。
    入参说明：page, limit, sort_by, order, search, search_history
    返回值说明：包含数据列表的 JSON 响应
    """
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=100, type=int)
    sort_by = request.args.get('sort_by', default='scan_time')
    order = request.args.get('order', default='DESC').upper()
    search_query = request.args.get('search', default='').strip()
    search_history = request.args.get('search_history', default='false').lower() == 'true'
    
    # 根据参数选择目标表
    table_name = "history_file_index" if search_history else "file_index"
    
    allowed_columns = ['file_name', 'file_path', 'file_md5', 'scan_time']
    if sort_by not in allowed_columns:
        sort_by = 'scan_time'
    if order not in ['ASC', 'DESC']:
        order = 'DESC'
        
    offset = (page - 1) * limit

    try:
        where_clause = ""
        params = []
        
        if search_query:
            # 获取配置中的替换字符
            replace_chars = settings.file_repository.get('search_replace_chars', [])
            
            # 处理搜索词：将需要替换的字符转换为 .*
            processed_query = search_query
            for char in replace_chars:
                if char:
                    processed_query = processed_query.replace(char, '.*')
            
            # 将 .* 转换为 % 以配合 LIKE
            sql_like_query = f"%{processed_query.replace('.*', '%')}%"
            where_clause = " WHERE file_name LIKE ? "
            params.append(sql_like_query)

        # 获取总数
        count_sql = f"SELECT COUNT(*) FROM {table_name}{where_clause}"
        total_res = db_manager.execute_query(count_sql, tuple(params))
        total = total_res[0][0] if total_res else 0

        # 获取分页数据
        query_params = list(params)
        query_params.extend([limit, offset])
        query = f"SELECT id, file_path, file_name, file_md5, scan_time FROM {table_name}{where_clause} ORDER BY {sort_by} {order} LIMIT ? OFFSET ?"
        results = db_manager.execute_query(query, tuple(query_params))
        
        file_list = []
        for row in results:
            file_list.append({
                "id": row[0], "file_path": row[1], "file_name": row[2], "file_md5": row[3], "scan_time": row[4]
            })
            
        return success_response("获取文件列表成功", data={
            "total": total, "list": file_list, "page": page, "limit": limit, "sort_by": sort_by, "order": order, "is_history": search_history
        })
    except Exception as e:
        LogUtils.error(f"获取文件列表失败: {e}")
        return error_response(f"获取文件列表失败: {str(e)}", 500)
