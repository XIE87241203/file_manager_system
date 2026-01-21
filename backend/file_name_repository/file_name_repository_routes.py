from dataclasses import asdict

from flask import Blueprint, request

from backend.common.auth_middleware import token_required
from backend.common.log_utils import LogUtils
from backend.common.response import success_response, error_response
from backend.file_name_repository.already_entered_file_service import AlreadyEnteredFileService
from backend.file_name_repository.batch_check_service import BatchCheckService
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
    """
    data: dict = request.json or {}
    file_names: list = data.get('file_names', [])
    if not file_names:
        return error_response("未提供文件名", 400)
    
    LogUtils.info(f"用户 {_get_current_user()} 请求添加待录入文件，待录入数量: {len(file_names)}")
    count: int = PendingEntryFileService.add_pending_entry_files(file_names)
    
    # 修改逻辑：只要没有抛异常，即视为操作成功，返回成功录入的数量（包含 0 条的情况）
    return success_response(f"已成功录入 {count} 条记录", data={"count": count})


@file_name_repo_bp.route('/pending_entry/batch_delete', methods=['POST'])
@token_required
def batch_delete_pending_entry_files():
    """
    用途说明：批量删除指定的待录入文件名记录。
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
    用途说明：清空待录入文件库。
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求清空待录入文件库")
    if PendingEntryFileService.clear_pending_entry_repository():
        return success_response("清空成功")
    else:
        return error_response("清空失败", 500)


# --- 批量检测相关路由 (异步化改造) ---

@file_name_repo_bp.route('/pending_entry/check_batch', methods=['POST'])
@token_required
def check_batch_files():
    """
    用途说明：启动异步批量检测。
    入参说明：JSON 包含 file_names (list)
    """
    data: dict = request.json or {}
    file_names: list = data.get('file_names', [])
    if not file_names:
        return error_response("未提供文件名清单", 400)
    
    if BatchCheckService.start_batch_check_task(file_names):
        return success_response("批量检测任务已启动")
    else:
        return error_response("任务启动失败，可能已有任务在运行", 409)


@file_name_repo_bp.route('/pending_entry/check_status', methods=['GET'])
@token_required
def get_batch_check_status():
    """
    用途说明：获取批量检测进度和状态。
    """
    return success_response("获取状态成功", data=BatchCheckService.get_status())


@file_name_repo_bp.route('/pending_entry/check_results', methods=['GET'])
@token_required
def get_batch_check_results():
    """
    用途说明：获取已保存的批量检测结果。
    """
    results = BatchCheckService.get_all_results()
    return success_response("获取结果成功", data=[asdict(r) for r in results])


@file_name_repo_bp.route('/pending_entry/check_clear', methods=['POST'])
@token_required
def clear_batch_check_task():
    """
    用途说明：清空检测任务结果并重置进度。
    """
    if BatchCheckService.clear_task():
        return success_response("任务已清空并重置")
    else:
        return error_response("清空任务失败", 500)
