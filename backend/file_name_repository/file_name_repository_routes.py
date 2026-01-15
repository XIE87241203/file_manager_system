from dataclasses import asdict

from flask import Blueprint, request

from backend.common.auth_middleware import token_required
from backend.common.log_utils import LogUtils
from backend.common.response import success_response, error_response
from backend.file_name_repository.already_entered_file_service import AlreadyEnteredFileService
from backend.file_name_repository.pending_entry_file_service import PendingEntryFileService

# 创建文件名仓库模块的蓝图
file_name_repo_bp = Blueprint('file_name_repository', __name__)


def _get_current_user() -> str:
    """
    用途说明：从当前请求上下文中获取登录用户名
    入参说明：无
    返回值说明：返回当前用户的用户名字符串
    """
    return getattr(request, 'username', 'Unknown')


# --- 曾录入文件名库相关路由 ---

@file_name_repo_bp.route('/already_entered/list', methods=['GET'])
@token_required
def list_already_entered_files():
    """
    用途说明：分页获取曾录入文件名列表。
    入参说明：
        page (int): 当前页码
        limit (int): 每页记录数
        sort_by (str): 排序字段
        order_asc (bool): 是否正序
        search (str): 搜索关键词
    返回值说明：JSON 格式响应，包含分页数据
    """
    page: int = request.args.get('page', default=1, type=int)
    limit: int = request.args.get('limit', default=100, type=int)
    sort_by: str = request.args.get('sort_by', default='add_time')
    order_asc: bool = request.args.get('order_asc', default='false').lower() == 'true'
    search_query: str = request.args.get('search', default='').strip()

    data = AlreadyEnteredFileService.search_already_entered_file_list(page, limit, sort_by, order_asc, search_query)
    return success_response("获取曾录入文件名列表成功", data=asdict(data))


@file_name_repo_bp.route('/already_entered/add', methods=['POST'])
@token_required
def add_already_entered_files():
    """
    用途说明：批量添加曾录入文件名。
    入参说明：JSON 包含 file_names (list)
    返回值说明：JSON 格式响应
    """
    data: dict = request.json or {}
    file_names: list = data.get('file_names', [])
    if not file_names:
        return error_response("未提供文件名", 400)
    
    LogUtils.info(f"用户 {_get_current_user()} 请求添加曾录入文件名: {file_names}")
    if AlreadyEnteredFileService.add_already_entered_files(file_names):
        return success_response("添加成功")
    else:
        return error_response("添加失败", 500)


@file_name_repo_bp.route('/already_entered/batch_delete', methods=['POST'])
@token_required
def batch_delete_already_entered_files():
    """
    用途说明：批量删除指定的曾录入文件名记录。
    入参说明：JSON 包含 ids (list)
    返回值说明：JSON 格式响应
    """
    data: dict = request.json or {}
    file_ids: list = data.get('ids', [])
    if not file_ids:
        return error_response("未选择要删除的记录", 400)
    
    LogUtils.info(f"用户 {_get_current_user()} 请求批量删除曾录入记录，数量: {len(file_ids)}")
    count: int = AlreadyEnteredFileService.batch_delete_already_entered_files(file_ids)
    if count > 0:
        return success_response(f"已成功删除 {count} 条记录")
    else:
        return error_response("批量删除失败", 500)


@file_name_repo_bp.route('/already_entered/clear', methods=['POST'])
@token_required
def clear_already_entered_repository():
    """
    用途说明：清空曾录入文件名库。
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求清空曾录入文件名库")
    if AlreadyEnteredFileService.clear_already_entered_repository():
        return success_response("清空成功")
    else:
        return error_response("清空失败", 500)


# --- 待录入文件名库相关路由 ---

@file_name_repo_bp.route('/pending_entry/list', methods=['GET'])
@token_required
def list_pending_entry_files():
    """
    用途说明：分页获取待录入文件名列表。
    入参说明：
        page (int): 当前页码
        limit (int): 每页记录数
        sort_by (str): 排序字段
        order_asc (bool): 是否正序
        search (str): 搜索关键词
    返回值说明：JSON 格式响应，包含分页数据
    """
    page: int = request.args.get('page', default=1, type=int)
    limit: int = request.args.get('limit', default=100, type=int)
    sort_by: str = request.args.get('sort_by', default='add_time')
    order_asc: bool = request.args.get('order_asc', default='false').lower() == 'true'
    search_query: str = request.args.get('search', default='').strip()
    
    data = PendingEntryFileService.search_pending_entry_file_list(page, limit, sort_by, order_asc, search_query)
    return success_response("获取待录入文件列表成功", data=asdict(data))


@file_name_repo_bp.route('/pending_entry/add', methods=['POST'])
@token_required
def add_pending_entry_files():
    """
    用途说明：批量添加待录入文件名。
    入参说明：JSON 包含 file_names (list)
    返回值说明：JSON 格式响应
    """
    data: dict = request.json or {}
    file_names: list = data.get('file_names', [])
    if not file_names:
        return error_response("未提供文件名", 400)
    
    LogUtils.info(f"用户 {_get_current_user()} 请求添加待录入文件: {file_names}")
    if PendingEntryFileService.add_pending_entry_files(file_names):
        return success_response("添加成功")
    else:
        return error_response("添加失败", 500)


@file_name_repo_bp.route('/pending_entry/batch_delete', methods=['POST'])
@token_required
def batch_delete_pending_entry_files():
    """
    用途说明：批量删除指定的待录入文件名记录。
    入参说明：JSON 包含 ids (list)
    返回值说明：JSON 格式响应
    """
    data: dict = request.json or {}
    file_ids: list = data.get('ids', [])
    if not file_ids:
        return error_response("未选择要删除的记录", 400)
    
    LogUtils.info(f"用户 {_get_current_user()} 请求批量删除待录入记录，数量: {len(file_ids)}")
    count: int = PendingEntryFileService.batch_delete_pending_entry_files(file_ids)
    if count > 0:
        return success_response(f"已成功删除 {count} 条记录")
    else:
        return error_response("批量删除失败", 500)


@file_name_repo_bp.route('/pending_entry/clear', methods=['POST'])
@token_required
def clear_pending_entry_repository():
    """
    用途说明：清空待录入文件名库。
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求清空待录入文件库")
    if PendingEntryFileService.clear_pending_entry_repository():
        return success_response("清空成功")
    else:
        return error_response("清空失败", 500)


@file_name_repo_bp.route('/pending_entry/check_batch', methods=['POST'])
@token_required
def check_batch_files():
    """
    用途说明：批量检测文件名是否存在于全库中。
    入参说明：JSON 包含 file_names (list)
    返回值说明：JSON 格式响应，包含每个文件的检测结果。
    """
    data: dict = request.json or {}
    file_names: list = data.get('file_names', [])
    if not file_names:
        return error_response("未提供文件名清单", 400)
    
    results: dict = PendingEntryFileService.check_batch_files(file_names)
    return success_response("批量检测完成", data=results)
