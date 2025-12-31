from flask import Blueprint, request
from backend.common.response import success_response, error_response
from backend.common.log_utils import LogUtils
from backend.common.auth_middleware import token_required
from backend.file_repository.scan_service import ScanService
from backend.file_repository.duplicate_service import DuplicateService
from backend.db.db_operations import DBOperations
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
    用途说明：清空数据库中的文件索引表，支持选择是否同时清空历史索引表
    入参说明：JSON 包含 clear_history (bool)
    返回值说明：JSON 格式响应，包含操作结果
    """
    data = request.json or {}
    clear_history = data.get('clear_history', False)
    
    LogUtils.info(f"用户 {request.username} 请求清空文件数据库 (clear_history={clear_history})")
    try:
        if DBOperations.clear_file_index():
            msg = "文件索引表已成功清空"
            if clear_history:
                if DBOperations.clear_history_index():
                    msg = "文件索引表及历史索引表已成功清空"
                else:
                    return error_response("清空历史索引表失败", 500)
            return success_response(msg)
        else:
            return error_response("清空文件索引表失败", 500)
    except Exception as e:
        LogUtils.error(f"清空数据库操作异常: {e}")
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
        total = DBOperations.get_file_count(table_name, where_clause, tuple(params))

        # 获取分页数据，返回值类型为 List[Union[FileIndex, HistoryFileIndex]]
        results = DBOperations.get_file_list_with_pagination(
            table_name, where_clause, tuple(params), sort_by, order, limit, offset
        )
        
        file_list = []
        for row in results:
            file_list.append({
                "id": row.id, 
                "file_path": row.file_path, 
                "file_name": row.file_name, 
                "file_md5": row.file_md5, 
                "scan_time": row.scan_time
            })
            
        return success_response("获取文件列表成功", data={
            "total": total, "list": file_list, "page": page, "limit": limit, "sort_by": sort_by, "order": order, "is_history": search_history
        })
    except Exception as e:
        LogUtils.error(f"获取文件列表失败: {e}")
        return error_response(f"获取文件列表失败: {str(e)}", 500)

@file_repo_bp.route('/delete', methods=['POST'])
@token_required
def delete_files():
    """
    用途说明：批量删除文件（物理文件及索引记录）
    入参说明：JSON 包含 file_paths (list)
    返回值说明：JSON 格式响应
    """
    data = request.json or {}
    file_paths = data.get('file_paths', [])
    
    if not file_paths:
        return error_response("未选择要删除的文件", 400)
    
    LogUtils.info(f"用户 {request.username} 请求批量删除文件，数量: {len(file_paths)}")
    
    success_count = 0
    failed_paths = []
    
    for path in file_paths:
        success, msg = DuplicateService.delete_file(path)
        if success:
            success_count += 1
        else:
            failed_paths.append(path)
            
    if success_count == len(file_paths):
        return success_response(f"成功删除 {success_count} 个文件")
    else:
        return success_response(f"删除完成。成功: {success_count}, 失败: {len(failed_paths)}", 
                               data={"failed": failed_paths})

@file_repo_bp.route('/duplicate/check', methods=['POST'])
@token_required
def start_duplicate_check():
    """
    用途说明：异步触发文件查重任务
    入参说明：无
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {request.username} 触发了文件查重")
    if DuplicateService.start_async_check():
        return success_response("查重任务已启动")
    else:
        return error_response("查重任务已在运行中", 400)

@file_repo_bp.route('/duplicate/stop', methods=['POST'])
@token_required
def stop_duplicate_check():
    """
    用途说明：手动停止正在进行的查重任务
    入参说明：无
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {request.username} 请求停止查重任务")
    DuplicateService.stop_check()
    return success_response("已发送停止指令")

@file_repo_bp.route('/duplicate/progress', methods=['GET'])
@token_required
def get_duplicate_progress():
    """
    用途说明：获取当前查重任务的状态、进度和结果信息
    入参说明：无
    返回值说明：包含 status, progress 和 results 的 JSON 响应
    """
    status_info = DuplicateService.get_status()
    return success_response("获取进度成功", data=status_info)

@file_repo_bp.route('/duplicate/delete', methods=['POST'])
@token_required
def delete_duplicate_file():
    """
    用途说明：删除指定的重复文件（包含物理文件和索引记录）
    入参说明：JSON 包含 file_path 或 group_md5
    返回值说明：JSON 格式响应
    """
    data = request.json
    file_path = data.get('file_path')
    group_md5 = data.get('group_md5')
    
    if file_path:
        LogUtils.info(f"用户 {request.username} 请求删除文件: {file_path}")
        success, msg = DuplicateService.delete_file(file_path)
        if success:
            return success_response("文件删除成功")
        else:
            return error_response(f"文件删除失败: {msg}", 500)
    
    if group_md5:
        LogUtils.info(f"用户 {request.username} 请求删除重复组: {group_md5}")
        count, failed = DuplicateService.delete_group(group_md5)
        if not failed:
            return success_response(f"成功删除组内 {count} 个文件")
        else:
            return error_response(f"部分文件删除失败({len(failed)}个): {', '.join(failed[:3])}...", 500)

    return error_response("无效的请求参数", 400)
