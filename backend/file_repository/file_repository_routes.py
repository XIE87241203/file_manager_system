import os
from dataclasses import asdict
from typing import Optional

from flask import Blueprint, request, send_file

from backend.common.auth_middleware import token_required
from backend.common.i18n_utils import t
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
    LogUtils.info(t('repo_scan_log', user=_get_current_user()))

    # 1. 解析请求参数
    data: dict = request.json or {}
    full_scan: bool = data.get('full_scan', False)
    scan_mode: ScanMode = ScanMode.FULL_SCAN if full_scan else ScanMode.INDEX_SCAN

    # 2. 先检查扫描状态
    status_info: dict = ScanService.get_status()
    if status_info.get("status") == ProgressStatus.PROCESSING.value:
        return error_response(t('repo_scan_running'), 400)

    # 3. 启动异步扫描
    if ScanService.start_scan_task(scan_mode):
        type_str = t('repo_scan_full_mode') if full_scan else t('repo_scan_incremental_mode')
        return success_response(t('repo_scan_started', type=type_str))
    else:
        return error_response(t('repo_scan_running'), 400)


@file_repo_bp.route('/stop', methods=['POST'])
@token_required
def stop_scan():
    """
    用途说明：手动停止正在进行的扫描任务
    """
    LogUtils.info(t('repo_scan_stop_sent'))
    ScanService.stop_task()
    return success_response(t('repo_scan_stop_sent'))


@file_repo_bp.route('/clear', methods=['POST'])
@token_required
def clear_repository():
    """
    用途说明：清空数据库中的文件索引表。
    """
    data: dict = request.json or {}
    clear_history: bool = data.get('clear_history', False)

    LogUtils.info(t('repo_clear_log_full', user=_get_current_user(), clear_history=clear_history))
    if FileService.clear_repository(clear_history):
        return success_response(t('repo_cleanup_success'))
    else:
        return error_response(t('clear_failed'), 500)


@file_repo_bp.route('/clear_history', methods=['POST'])
@token_required
def clear_history_repository():
    """
    用途说明：清空历史文件索引表。
    """
    LogUtils.info(t('repo_clear_history_log', user=_get_current_user()))
    if FileService.clear_history_repository():
        return success_response(t('repo_clear_history_success'))
    else:
        return error_response(t('repo_clear_history_failed', error=''), 500)


@file_repo_bp.route('/clear_recycle_bin', methods=['POST'])
@token_required
def clear_recycle_bin():
    """
    用途说明：批量彻底删除文件（物理删除及索引清理）。
    """
    data: dict = request.json or {}
    file_paths: list = data.get('file_paths')

    if file_paths:
        LogUtils.info(t('repo_batch_delete_log', user=_get_current_user(), count=len(file_paths)))
        msg: str = t('repo_delete_started')
    else:
        LogUtils.info(t('repo_recycle_clear_log', user=_get_current_user()))
        msg: str = t('repo_recycle_clear_started')

    if RecycleBinService.start_batch_delete_task(file_paths):
        return success_response(msg)
    else:
        return error_response(t('repo_delete_start_failed', error=''), 500)


@file_repo_bp.route('/clear_recycle_bin/progress', methods=['GET'])
@token_required
def get_clear_recycle_bin_progress():
    status_info: dict = RecycleBinService.get_status()
    return success_response(t('fn_batch_check_status_ok'), data=status_info)


@file_repo_bp.route('/clear_video_features', methods=['POST'])
@token_required
def clear_video_features():
    LogUtils.info(t('dup_video_feature_clear_log', user=_get_current_user()))
    if FileService.clear_video_features():
        return success_response(t('dup_video_feature_clear_success'))
    else:
        return error_response(t('clear_failed'), 500)


@file_repo_bp.route('/progress', methods=['GET'])
@token_required
def get_scan_progress():
    status_info: dict = ScanService.get_status()
    return success_response(t('fn_batch_check_status_ok'), data=status_info)


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
        return success_response(t('repo_get_list_success'), data=asdict(data))
    else:
        data = FileService.search_file_index_list(page, limit, sort_by, order_asc, search_query, file_type=file_type)
        return success_response(t('repo_get_list_success'), data=asdict(data))


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
    return success_response(t('repo_get_list_success'), data=asdict(data))


@file_repo_bp.route('/move_to_recycle_bin', methods=['POST'])
@token_required
def move_to_recycle_bin():
    data: dict = request.json or {}
    file_paths: list = data.get('file_paths', [])

    if not file_paths:
        return error_response(t('no_selection'), 400)

    LogUtils.info(t('repo_move_to_recycle_log', user=_get_current_user(), count=len(file_paths)))

    if RecycleBinService.batch_move_to_recycle_bin(file_paths):
        return success_response(t('repo_move_to_recycle_success', count=len(file_paths)))
    else:
        return error_response(t('operation_failed', error=''), 500)


@file_repo_bp.route('/restore_from_recycle_bin', methods=['POST'])
@token_required
def restore_from_recycle_bin():
    data: dict = request.json or {}
    file_paths: list = data.get('file_paths', [])

    if not file_paths:
        return error_response(t('no_selection'), 400)

    LogUtils.info(t('repo_restore_from_recycle_log', user=_get_current_user(), count=len(file_paths)))

    if RecycleBinService.batch_restore_from_recycle_bin(file_paths):
        return success_response(t('repo_restore_from_recycle_success', count=len(file_paths)))
    else:
        return error_response(t('operation_failed', error=''), 500)


@file_repo_bp.route('/duplicate/check', methods=['POST'])
@token_required
def start_duplicate_check():
    LogUtils.info(t('dup_start_log', user=_get_current_user()))
    if DuplicateService.start_duplicate_check_task():
        return success_response(t('dup_task_started'))
    else:
        return error_response(t('dup_task_running'), 400)


@file_repo_bp.route('/duplicate/stop', methods=['POST'])
@token_required
def stop_duplicate_check():
    LogUtils.info(t('dup_stop_log', user=_get_current_user()))
    DuplicateService.stop_task()
    return success_response(t('repo_scan_stop_sent'))


@file_repo_bp.route('/duplicate/progress', methods=['GET'])
@token_required
def get_duplicate_progress():
    status_info: dict = DuplicateService.get_status()
    return success_response(t('fn_batch_check_status_ok'), data=status_info)


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
    return success_response(t('dup_get_list_success'), data=asdict(data))


@file_repo_bp.route('/duplicate/latest_check_time', methods=['GET'])
@token_required
def get_latest_duplicate_check_time():
    """
    用途说明：获取最近一次查重的完成时间。
    """
    time_str = DuplicateService.get_latest_check_time()
    return success_response(t('dup_get_last_time_success'), data=time_str)


# --- 缩略图相关路由 ---

@file_repo_bp.route('/thumbnail/start', methods=['POST'])
@token_required
def start_thumbnail_generation():
    data: dict = request.json or {}
    rebuild_all: bool = data.get('rebuild_all', False)

    LogUtils.info(t('thumb_generate_log', user=_get_current_user(), rebuild_all=rebuild_all))
    if ThumbnailService.dispatch_thumbnail_tasks(rebuild_all):
        return success_response(t('thumb_task_started'))
    else:
        return error_response(t('thumb_task_running'), 400)


@file_repo_bp.route('/thumbnail/stop', methods=['POST'])
@token_required
def stop_thumbnail_generation():
    LogUtils.info(t('thumb_stop_all_request'))
    ThumbnailService.stop_thumbnail_generation()
    return success_response(t('repo_scan_stop_sent'))


@file_repo_bp.route('/thumbnail/queue_count', methods=['GET'])
@token_required
def get_thumbnail_queue_count():
    """
    用途说明：获取缩略图生成队列中剩余的任务数量。
    入参说明：无
    返回值说明：JSON 格式响应，data 字段为 int 类型。
    """
    count: int = ThumbnailService.get_thumbnail_queue_count()
    return success_response(t('thumb_get_queue_success'), data=count)


@file_repo_bp.route('/thumbnail/clear', methods=['POST'])
@token_required
def clear_thumbnails():
    LogUtils.info(t('thumb_clear_log', user=_get_current_user()))
    if ThumbnailService.clear_all_thumbnails():
        return success_response(t('thumb_cleanup_success'))
    else:
        return error_response(t('thumb_clear_all_failed', error=''), 500)


@file_repo_bp.route('/thumbnail/sync/start', methods=['POST'])
@token_required
def start_thumbnail_sync():
    """
    用途说明：启动缩略图物理同步任务（清理无效文件）
    """
    LogUtils.info(t('thumb_sync_log', user=_get_current_user()))
    if ThumbnailService.start_thumbnail_sync_task():
        return success_response(t('thumb_sync_started'))
    else:
        return error_response(t('thumb_sync_running'), 400)


@file_repo_bp.route('/thumbnail/sync/stop', methods=['POST'])
@token_required
def stop_thumbnail_sync():
    """
    用途说明：停止正在进行的缩略图物理同步任务
    """
    LogUtils.info(t('thumb_sync_user_stop'))
    ThumbnailService.stop_task()
    return success_response(t('repo_scan_stop_sent'))


@file_repo_bp.route('/thumbnail/sync/progress', methods=['GET'])
@token_required
def get_thumbnail_sync_progress():
    """
    用途说明：获取缩略图物理同步任务的实时进度
    """
    status_info: dict = ThumbnailService.get_status()
    return success_response(t('fn_batch_check_status_ok'), data=status_info)


@file_repo_bp.route('/thumbnail/view', methods=['GET'])
@token_required
def view_thumbnail():
    path: str = request.args.get('path')
    if not path:
        return error_response(t('params_missing'), 400)

    thumbnail_dir: str = os.path.abspath(os.path.join(Utils.get_runtime_path(), "cache", "thumbnail"))
    requested_path: str = os.path.abspath(path)

    if not requested_path.startswith(thumbnail_dir):
        return error_response(t('invalid_path', path=path), 403)

    if not os.path.exists(requested_path):
        return error_response(t('file_not_found'), 404)

    return send_file(requested_path, mimetype='image/jpeg')


# --- 视频播放相关路由 ---

@file_repo_bp.route('/video/stream', methods=['GET'])
@token_required
def stream_video():
    """
    用途说明：提供视频流式传输接口，支持 Range 请求，以便调起第三方播放器。
    入参说明：Query 参数 path 为视频文件的绝对路径。
    返回值说明：视频文件流。
    """
    path: str = request.args.get('path')
    if not path:
        return error_response(t('params_missing'), 400)

    if not os.path.exists(path):
        return error_response(t('video_not_found'), 404)

    # 简单校验是否为视频文件（可选，增加安全性）
    if not Utils.is_video_file(path):
        return error_response(t('invalid_video_format'), 400)

    LogUtils.info(t('repo_play_video_log', user=_get_current_user(), path=path))
    
    # conditional=True 允许 Flask 处理 Range 请求，这对于视频拖动进度条至关重要
    return send_file(path, conditional=True)


# --- 文件仓库详情统计相关路由 ---

@file_repo_bp.route('/detail', methods=['GET'])
@token_required
def get_repo_detail():
    """
    用途说明：获取文件仓库详情统计数据（总文件数、总大小）。
    """
    detail = FileService.get_repo_detail()
    if detail:
        return success_response(t('repo_get_detail_success'), data=asdict(detail))
    else:
        # 如果没有数据，尝试计算一次
        detail = FileService.calculate_repo_detail()
        if detail:
            return success_response(t('repo_calc_detail_success'), data=asdict(detail))
        return error_response(t('repo_no_stats'), 404)


@file_repo_bp.route('/detail/calculate', methods=['POST'])
@token_required
def calculate_repo_detail():
    """
    用途说明：手动触发重新计算文件仓库详情。
    """
    LogUtils.info(t('repo_calc_detail_log', user=_get_current_user()))
    detail = FileService.calculate_repo_detail()
    if detail:
        return success_response(t('repo_calc_detail_success'), data=asdict(detail))
    else:
        return error_response(t('operation_failed', error=''), 500)
