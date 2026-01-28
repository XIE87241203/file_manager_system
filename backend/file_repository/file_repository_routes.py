import os
from dataclasses import asdict
from typing import Optional

from flask import Blueprint, request, send_file

from backend.common.auth_middleware import token_required
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.common.response import success_response, error_response
from backend.common.utils import Utils
from backend.file_repository.duplicate_check.duplicate_service import DuplicateService
from backend.file_repository.file_service import FileService
from backend.file_repository.recycle_bin_service import RecycleBinService
from backend.file_repository.scan_service import ScanService, ScanMode
from backend.file_repository.thumbnail.thumbnail_service import ThumbnailService

# 创建文件仓库模块的蓝图
file_repo_bp = Blueprint('file_repository', __name__)


def _get_current_user() -> str:
    """
    用途说明：从当前请求上下文中获取登录用户名
    入参说明：无
    返回值说明：返回当前用户的用户名字符串
    """
    return getattr(request, 'username', 'Unknown')


@file_repo_bp.route('/scan', methods=['POST'])
@token_required
def start_scan():
    """
    用途说明：异步触发文件仓库扫描任务，支持增量或全量扫描。
    入参说明：JSON 包含 full_scan (bool)
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {_get_current_user()} 触发了文件仓库扫描")

    # 1. 解析请求参数
    data: dict = request.json or {}
    full_scan: bool = data.get('full_scan', False)
    scan_mode: ScanMode = ScanMode.FULL_SCAN if full_scan else ScanMode.INDEX_SCAN

    # 2. 先检查扫描状态
    status_info: dict = ScanService.get_status()
    if status_info.get("status") == ProgressStatus.PROCESSING.value:
        return error_response("扫描任务已在运行中", 400)

    # 3. 启动异步扫描
    if ScanService.start_scan_task(scan_mode):
        return success_response(f"{'全量' if full_scan else '增量'}扫描任务已启动")
    else:
        return error_response("扫描任务启动失败，可能已在运行中", 400)


@file_repo_bp.route('/stop', methods=['POST'])
@token_required
def stop_scan():
    """
    用途说明：手动停止正在进行的扫描任务
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求停止扫描任务")
    ScanService.stop_task()
    return success_response("已发送停止指令")


@file_repo_bp.route('/clear', methods=['POST'])
@token_required
def clear_repository():
    """
    用途说明：清空数据库中的文件索引表。
    """
    data: dict = request.json or {}
    clear_history: bool = data.get('clear_history', False)

    LogUtils.info(f"用户 {_get_current_user()} 请求清空文件数据库 (clear_history={clear_history})")
    if FileService.clear_repository(clear_history):
        return success_response("文件索引及相关缓存已成功清空")
    else:
        return error_response("清空仓库失败", 500)


@file_repo_bp.route('/clear_history', methods=['POST'])
@token_required
def clear_history_repository():
    """
    用途说明：清空历史文件索引表。
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求清空历史文件数据库")
    if FileService.clear_history_repository():
        return success_response("历史文件索引库已成功清空")
    else:
        return error_response("清空历史仓库失败", 500)


@file_repo_bp.route('/clear_recycle_bin', methods=['POST'])
@token_required
def clear_recycle_bin():
    """
    用途说明：批量彻底删除文件（物理删除及索引清理）。
    """
    data: dict = request.json or {}
    file_paths: list = data.get('file_paths')

    if file_paths:
        LogUtils.info(f"用户 {_get_current_user()} 请求批量删除指定文件，数量: {len(file_paths)}")
        msg: str = "已启动批量删除任务"
    else:
        LogUtils.info(f"用户 {_get_current_user()} 请求清空回收站")
        msg: str = "已启动清空任务"

    if RecycleBinService.start_batch_delete_task(file_paths):
        return success_response(msg)
    else:
        return error_response("启动删除任务失败", 500)


@file_repo_bp.route('/clear_recycle_bin/progress', methods=['GET'])
@token_required
def get_clear_recycle_bin_progress():
    status_info: dict = RecycleBinService.get_status()
    return success_response("获取进度成功", data=status_info)


@file_repo_bp.route('/clear_video_features', methods=['POST'])
@token_required
def clear_video_features():
    LogUtils.info(f"用户 {_get_current_user()} 请求清空视频特征库")
    if FileService.clear_video_features():
        return success_response("视频特征库已成功清空")
    else:
        return error_response("清空视频特征库失败", 500)


@file_repo_bp.route('/progress', methods=['GET'])
@token_required
def get_scan_progress():
    status_info: dict = ScanService.get_status()
    return success_response("获取进度成功", data=status_info)


@file_repo_bp.route('/list', methods=['GET'])
@token_required
def list_files():
    """
    用途说明：分页获取文件列表，支持按类型筛选和历史记录查询。
    入参说明：
        page (int): 当前页码
        limit (int): 每页数量
        sort_by (str): 排序字段
        order_asc (bool): 是否升序
        search (str): 搜索关键词
        search_history (bool): 是否搜索历史记录
        file_type (str): 文件类型 (video/image/other)
    """
    page: int = request.args.get('page', default=1, type=int)
    limit: int = request.args.get('limit', default=100, type=int)
    sort_by: str = request.args.get('sort_by', default='scan_time')
    order_asc: bool = request.args.get('order_asc', default='false').lower() == 'true'
    search_query: str = request.args.get('search', default='').strip()
    search_history: bool = request.args.get('search_history', default='false').lower() == 'true'
    file_type: Optional[str] = request.args.get('file_type', default=None)

    if search_history:
        data = FileService.search_history_file_index_list(page, limit, sort_by, order_asc, search_query, file_type=file_type)
        return success_response("获取文件列表成功", data=asdict(data))
    else:
        data = FileService.search_file_index_list(page, limit, sort_by, order_asc, search_query, file_type=file_type)
        return success_response("获取文件列表成功", data=asdict(data))


@file_repo_bp.route('/recycle_bin/list', methods=['GET'])
@token_required
def list_recycle_bin_files():
    """
    用途说明：获取回收站中的文件列表。
    入参说明：
        page (int): 当前页码
        limit (int): 每页数量
        sort_by (str): 排序字段
        order_asc (bool): 是否升序
        search (str): 搜索关键词
    """
    page: int = request.args.get('page', default=1, type=int)
    limit: int = request.args.get('limit', default=100, type=int)
    sort_by: str = request.args.get('sort_by', default='recycle_bin_time')
    order_asc: bool = request.args.get('order_asc', default='false').lower() == 'true'
    search_query: str = request.args.get('search', default='').strip()

    data = RecycleBinService.get_recycle_bin_list(page, limit, sort_by, order_asc, search_query)
    return success_response("获取回收站列表成功", data=asdict(data))


@file_repo_bp.route('/move_to_recycle_bin', methods=['POST'])
@token_required
def move_to_recycle_bin():
    data: dict = request.json or {}
    file_paths: list = data.get('file_paths', [])

    if not file_paths:
        return error_response("未选择要移动的文件", 400)

    LogUtils.info(f"用户 {_get_current_user()} 请求批量移入回收站，数量: {len(file_paths)}")

    if RecycleBinService.batch_move_to_recycle_bin(file_paths):
        return success_response(f"已成功将 {len(file_paths)} 个文件移入回收站")
    else:
        return error_response("移入回收站失败", 500)


@file_repo_bp.route('/restore_from_recycle_bin', methods=['POST'])
@token_required
def restore_from_recycle_bin():
    data: dict = request.json or {}
    file_paths: list = data.get('file_paths', [])

    if not file_paths:
        return error_response("未选择要恢复的文件", 400)

    LogUtils.info(f"用户 {_get_current_user()} 请求批量移出回收站，数量: {len(file_paths)}")

    if RecycleBinService.batch_restore_from_recycle_bin(file_paths):
        return success_response(f"已成功将 {len(file_paths)} 个文件移出回收站")
    else:
        return error_response("移出回收站失败", 500)


@file_repo_bp.route('/duplicate/check', methods=['POST'])
@token_required
def start_duplicate_check():
    LogUtils.info(f"用户 {_get_current_user()} 触发了文件查重")
    if DuplicateService.start_duplicate_check_task():
        return success_response("查重任务已启动")
    else:
        return error_response("查重任务已在运行中", 400)


@file_repo_bp.route('/duplicate/stop', methods=['POST'])
@token_required
def stop_duplicate_check():
    LogUtils.info(f"用户 {_get_current_user()} 请求停止查重任务")
    DuplicateService.stop_task()
    return success_response("已发送停止指令")


@file_repo_bp.route('/duplicate/progress', methods=['GET'])
@token_required
def get_duplicate_progress():
    status_info: dict = DuplicateService.get_status()
    return success_response("获取进度成功", data=status_info)


@file_repo_bp.route('/duplicate/list', methods=['GET'])
@token_required
def list_duplicate_results():
    """
    用途说明：分页获取查重结果数据，支持相似类型筛选。
    """
    page: int = request.args.get('page', default=1, type=int)
    limit: int = request.args.get('limit', default=100, type=int)
    similarity_type: str = request.args.get('similarity_type', default=None)
    data = DuplicateService.get_all_duplicate_results(page, limit, similarity_type)
    return success_response("获取重复文件列表成功", data=asdict(data))


@file_repo_bp.route('/duplicate/latest_check_time', methods=['GET'])
@token_required
def get_latest_duplicate_check_time():
    """
    用途说明：获取最近一次查重的完成时间。
    """
    time_str = DuplicateService.get_latest_check_time()
    return success_response("获取最近查重时间成功", data=time_str)


# --- 缩略图相关路由 ---

@file_repo_bp.route('/thumbnail/start', methods=['POST'])
@token_required
def start_thumbnail_generation():
    data: dict = request.json or {}
    rebuild_all: bool = data.get('rebuild_all', False)

    LogUtils.info(f"用户 {_get_current_user()} 触发了缩略图生成 (rebuild_all={rebuild_all})")
    if ThumbnailService.dispatch_thumbnail_tasks(rebuild_all):
        return success_response("缩略图生成任务已启动")
    else:
        return error_response("缩略图生成任务已在运行中", 400)


@file_repo_bp.route('/thumbnail/stop', methods=['POST'])
@token_required
def stop_thumbnail_generation():
    LogUtils.info(f"用户 {_get_current_user()} 请求停止缩略图生成任务")
    ThumbnailService.stop_thumbnail_generation()
    return success_response("已发送停止指令")


@file_repo_bp.route('/thumbnail/queue_count', methods=['GET'])
@token_required
def get_thumbnail_queue_count():
    """
    用途说明：获取缩略图生成队列中剩余的任务数量。
    入参说明：无
    返回值说明：JSON 格式响应，data 字段为 int 类型。
    """
    count: int = ThumbnailService.get_thumbnail_queue_count()
    return success_response("获取队列数量成功", data=count)


@file_repo_bp.route('/thumbnail/clear', methods=['POST'])
@token_required
def clear_thumbnails():
    LogUtils.info(f"用户 {_get_current_user()} 请求清空所有缩略图")
    if ThumbnailService.clear_all_thumbnails():
        return success_response("缩略图已成功清空")
    else:
        return error_response("清空缩略图失败", 500)


@file_repo_bp.route('/thumbnail/sync/start', methods=['POST'])
@token_required
def start_thumbnail_sync():
    """
    用途说明：启动缩略图物理同步任务（清理无效文件）
    """
    LogUtils.info(f"用户 {_get_current_user()} 触发了缩略图物理同步")
    if ThumbnailService.start_thumbnail_sync_task():
        return success_response("缩略图同步任务已启动")
    else:
        return error_response("同步任务已在运行中", 400)


@file_repo_bp.route('/thumbnail/sync/stop', methods=['POST'])
@token_required
def stop_thumbnail_sync():
    """
    用途说明：停止正在进行的缩略图物理同步任务
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求停止缩略图同步任务")
    ThumbnailService.stop_task()
    return success_response("已发送停止指令")


@file_repo_bp.route('/thumbnail/sync/progress', methods=['GET'])
@token_required
def get_thumbnail_sync_progress():
    """
    用途说明：获取缩略图物理同步任务的实时进度
    """
    status_info: dict = ThumbnailService.get_status()
    return success_response("获取同步进度成功", data=status_info)


@file_repo_bp.route('/thumbnail/view', methods=['GET'])
@token_required
def view_thumbnail():
    path: str = request.args.get('path')
    if not path:
        return error_response("参数缺失", 400)

    thumbnail_dir: str = os.path.abspath(os.path.join(Utils.get_runtime_path(), "cache", "thumbnail"))
    requested_path: str = os.path.abspath(path)

    if not requested_path.startswith(thumbnail_dir):
        return error_response(f"非法路径请求: {path}", 403)

    if not os.path.exists(requested_path):
        return error_response("缩略图文件不存在", 404)

    return send_file(requested_path, mimetype='image/jpeg')


# --- 文件仓库详情统计相关路由 ---

@file_repo_bp.route('/detail', methods=['GET'])
@token_required
def get_repo_detail():
    """
    用途说明：获取文件仓库详情统计数据（总文件数、总大小）。
    """
    detail = FileService.get_repo_detail()
    if detail:
        return success_response("获取仓库详情成功", data=asdict(detail))
    else:
        # 如果没有数据，尝试计算一次
        detail = FileService.calculate_repo_detail()
        if detail:
            return success_response("计算仓库详情成功", data=asdict(detail))
        return error_response("暂无统计数据", 404)


@file_repo_bp.route('/detail/calculate', methods=['POST'])
@token_required
def calculate_repo_detail():
    """
    用途说明：手动触发重新计算文件仓库详情。
    """
    LogUtils.info(f"用户 {_get_current_user()} 手动触发了仓库详情计算")
    detail = FileService.calculate_repo_detail()
    if detail:
        return success_response("详情计算完成", data=asdict(detail))
    else:
        return error_response("详情计算失败", 500)
