import os
from dataclasses import asdict
from typing import Any, Optional, Tuple

from flask import Blueprint, request, send_file

from backend.album.album_service import AlbumService
from backend.album.face_service import FaceService
from backend.auth.auth_middleware import admin_required, token_required
from backend.common.file_type_enum import FileType
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import get_current_repo_id, set_current_repo_id
from backend.common.response import success_response, error_response
from backend.db.db_constants import DBConstants
from backend.model.album_axis_result import AlbumAxisResult
from backend.model.album_settings_result import AlbumSettingsResult
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.face_index_result import FaceTaskStatusResult
from backend.model.thumbnail_usage_result import ThumbnailUsageResult
from backend.model.cursor_pagination_result import CursorPaginationResult
from backend.user.user_service import userService


# 创建相册模块蓝图
album_bp = Blueprint('album', __name__)


def _get_current_user() -> str:
    """
    用途说明：从当前请求上下文中获取登录用户名。
    入参说明：无
    返回值说明：str - 当前用户名，缺失时返回 Unknown。
    """
    return getattr(request, 'username', 'Unknown')


def _apply_repo_id_from_query() -> None:
    """
    用途说明：为 <img>/<video> 等无法携带请求头的 GET 请求补充仓库上下文（通过 URL 参数 repo_id）。
    入参说明：无（读取 Query 参数 repo_id）
    返回值说明：无
    """
    repo_id_str: str = request.args.get('repo_id', default='')
    if not repo_id_str:
        return
    try:
        set_current_repo_id(int(repo_id_str))
    except (ValueError, TypeError):
        # 非法仓库 ID 时保持中间件注入的默认仓库上下文
        pass


@album_bp.route('/list', methods=['GET'])
@token_required
def list_album_media() -> Tuple[Any, int]:
    """
    用途说明：按媒体路径游标或锚点获取相册媒体列表（图片/视频），支持文件名搜索与排序。
    入参说明（Query）：
        limit (int): 每批数量，默认 50，最大 500。
        last_path (str): 向下游标路径，传入上一条已加载媒体的完整路径；空字符串表示首批数据。
        anchor_path (str): 定位锚点路径，从该媒体开始包含式取数。
        before_path (str): 向上锚点路径，获取该媒体之前最近一批数据。
        sort_by (str): 排序字段，默认 album_time（EXIF 优先、文件修改时间兜底，供时间轴分组）。
        order_asc (bool): 是否升序，默认 false。
        search (str): 文件名搜索关键词。
        file_type (str): 媒体类型筛选，空串为全部，可选 image（仅图片）/ video（仅视频）；非法值按全部处理。
    返回值说明：统一 JSON 响应，data 为游标分页结果。
    """
    limit: int = request.args.get('limit', default=50, type=int)
    last_path: str = request.args.get('last_path', default='').strip()
    anchor_path: str = request.args.get('anchor_path', default='').strip()
    before_path: str = request.args.get('before_path', default='').strip()
    sort_by: str = request.args.get('sort_by', default='album_time')
    order_asc: bool = request.args.get('order_asc', default='false').lower() == 'true'
    search_query: str = request.args.get('search', default='').strip()
    file_type: str = request.args.get('file_type', default='').strip()
    if file_type not in ('', FileType.IMAGE.value, FileType.VIDEO.value):
        file_type = ''

    result: CursorPaginationResult = AlbumService.get_album_list(
        limit, sort_by, order_asc, search_query, file_type,
        last_path, anchor_path, before_path
    )
    return success_response(t('album_list_success'), data=asdict(result))


@album_bp.route('/axis', methods=['GET'])
@token_required
def get_album_axis() -> Tuple[Any, int]:
    """
    用途说明：获取相册年份、月份、日期或文件名首字母轴及每组首条媒体路径。
    入参说明（Query）：
        level (str): 轴层级，可选 year、month、day、initial。
        year (str): 查询月份轴或日期轴时的年份，格式 YYYY。
        month (int): 查询日期轴时的月份，范围 1-12。
        sort_by (str): 媒体排序字段，默认 album_time。
        order_asc (bool): 是否升序，默认 false。
        search (str): 文件名搜索关键词。
        file_type (str): 媒体类型筛选，空串为全部，可选 image/video。
    返回值说明：统一 JSON 响应，data 为 AlbumAxisResult。
    """
    level: str = request.args.get('level', default='').strip()
    if level not in ('year', 'month', 'day', 'initial'):
        return error_response(t('album_axis_invalid_params'), 400)

    year: str = request.args.get('year', default='').strip()
    month: int = request.args.get('month', default=0, type=int)
    if level in ('month', 'day') and (len(year) != 4 or not year.isdigit()):
        return error_response(t('album_axis_invalid_params'), 400)
    if level == 'day' and not 1 <= month <= 12:
        return error_response(t('album_axis_invalid_params'), 400)

    sort_by: str = request.args.get('sort_by', default='album_time')
    order_asc: bool = request.args.get('order_asc', default='false').lower() == 'true'
    search_query: str = request.args.get('search', default='').strip()
    file_type: str = request.args.get('file_type', default='').strip()
    if file_type not in ('', FileType.IMAGE.value, FileType.VIDEO.value):
        file_type = ''

    result: AlbumAxisResult = AlbumService.get_axis(
        level, sort_by, order_asc, search_query, file_type, year, month
    )
    return success_response(t('album_axis_success'), data=asdict(result))


@album_bp.route('/media', methods=['GET'])
@token_required
def view_album_media():
    """
    用途说明：按路径返回原始图片/视频文件流，用于相册预览弹窗（视频支持 Range）。
    入参说明（Query）：path (str) - 媒体文件完整路径；repo_id (int) - 仓库 ID；token (str) - 登录凭证。
    返回值说明：文件流或统一错误响应。
    """
    _apply_repo_id_from_query()
    path: str = request.args.get('path', default='').strip()
    file_info: Optional[FileIndexDBModel] = AlbumService.get_media_file(path)
    if file_info is None:
        return error_response(t('album_media_not_found'), 404)

    return send_file(file_info.file_path, conditional=True)


@album_bp.route('/download', methods=['GET'])
@token_required
def download_album_media():
    """
    用途说明：以附件形式下载原始图片/视频文件。
    入参说明（Query）：path (str) - 媒体文件完整路径；repo_id (int) - 仓库 ID；token (str) - 登录凭证。
    返回值说明：附件文件流或统一错误响应。
    """
    _apply_repo_id_from_query()
    path: str = request.args.get('path', default='').strip()
    file_info: Optional[FileIndexDBModel] = AlbumService.get_media_file(path)
    if file_info is None:
        return error_response(t('album_media_not_found'), 404)

    file_name: str = file_info.file_name or os.path.basename(file_info.file_path)
    LogUtils.info(t('album_download_log', user=_get_current_user(), path=file_info.file_path))
    return send_file(
        file_info.file_path,
        as_attachment=True,
        download_name=file_name or None,
        conditional=False
    )


@album_bp.route('/thumbnail/usage', methods=['GET'])
@token_required
def get_thumbnail_usage() -> Tuple[Any, int]:
    """
    用途说明：获取当前配置的缩略图目录占用大小。
    入参说明：无
    返回值说明：统一 JSON 响应，data 为包含 size_bytes 的结果对象。
    """
    result: ThumbnailUsageResult = AlbumService.get_thumbnail_usage()
    return success_response(t('album_thumbnail_usage_success'), data=asdict(result))


@album_bp.route('/settings', methods=['GET'])
@token_required
def get_album_settings():
    """
    用途说明：获取相册设置（缩略图存储路径与全系统统一的缩略图最大边长）。
    入参说明：无
    返回值说明：统一 JSON 响应，data 为相册设置对象。
    """
    settings: AlbumSettingsResult = AlbumService.get_settings()
    return success_response(t('album_settings_get_success'), data=asdict(settings))


@album_bp.route('/settings', methods=['POST'])
@token_required
def update_album_settings():
    """
    用途说明：更新相册设置中的缩略图存储路径、全系统统一缩略图最大边长与自动人脸识别开关。
    入参说明（JSON）：
        thumbnail_dir (str) - 新的缩略图存储路径。
        thumbnail_size (int, 可选) - 全系统缩略图最大边长（像素），仅当前仓库管理员可修改。
        auto_face_recognition (bool, 可选) - 自动识别新增图片开关，仅系统管理员可修改。
    返回值说明：统一 JSON 响应，data 为更新后的相册设置对象。
    """
    data: dict = request.get_json(silent=True) or {}
    thumbnail_dir: str = data.get('thumbnail_dir', '')
    thumbnail_size: Optional[int] = data.get('thumbnail_size')
    auto_face_recognition: Optional[bool] = data.get('auto_face_recognition')
    if thumbnail_size is not None:
        if isinstance(thumbnail_size, bool) or not isinstance(thumbnail_size, int) or thumbnail_size <= 0:
            return error_response(t('album_thumbnail_size_invalid', value=thumbnail_size), 400)
        repo_id: int = get_current_repo_id()
        if userService.get_repo_permission(request.username, repo_id) \
                != DBConstants.UserRepositoryPermission.PERMISSION_ADMIN:
            return error_response(t('user_repo_admin_required'), 403)
    if auto_face_recognition is not None:
        if not isinstance(auto_face_recognition, bool):
            return error_response(t('album_auto_face_recognition_invalid', value=auto_face_recognition), 400)
        if not userService.is_admin(request.username):
            return error_response(t('user_admin_required'), 403)

    settings: Optional[AlbumSettingsResult] = AlbumService.update_settings(
        thumbnail_dir, _get_current_user(), thumbnail_size, auto_face_recognition
    )
    if settings is None:
        return error_response(t('album_settings_update_failed'), 500)
    return success_response(t('album_settings_update_success'), data=asdict(settings))


@album_bp.route('/face/status', methods=['GET'])
@admin_required
def get_face_recognition_status() -> Tuple[Any, int]:
    """
    用途说明：获取人脸识别任务状态、队列数量、暂停标志和当前仓库已保存的人脸数量。
    入参说明：无（仓库 ID 来自请求上下文）。
    返回值说明：统一 JSON 响应，data 为 FaceTaskStatusResult；仅系统管理员可访问。
    """
    result: FaceTaskStatusResult = FaceService.get_status()
    return success_response(t('face_status_success'), data=asdict(result))


@album_bp.route('/face/start', methods=['POST'])
@admin_required
def start_face_recognition() -> Tuple[Any, int]:
    """
    用途说明：将当前仓库全部未识别图片去重加入队列，并启动或恢复单线程人脸识别任务。
    入参说明：无（仓库 ID 来自请求上下文）。
    返回值说明：统一 JSON 响应，data 为开始后的任务状态；已有任务运行时返回 409；仅系统管理员可访问。
    """
    if not FaceService.start_task():
        status: FaceTaskStatusResult = FaceService.get_status()
        if status.running:
            return error_response(t('face_task_already_running'), 409)
        return error_response(
            status.message or t('face_task_start_failed', error=t('common.error')),
            500
        )
    result: FaceTaskStatusResult = FaceService.get_status()
    return success_response(t('face_task_start_success'), data=asdict(result))


@album_bp.route('/face/pause', methods=['POST'])
@admin_required
def pause_face_recognition() -> Tuple[Any, int]:
    """
    用途说明：暂停当前仓库的人脸识别任务，保留队列和已处理数据，等待开始按钮恢复。
    入参说明：无（仓库 ID 来自请求上下文）。
    返回值说明：统一 JSON 响应，data 为暂停后的任务状态；当前仓库没有运行任务时返回 409。
    """
    if not FaceService.pause_task():
        return error_response(t('face_task_not_running'), 409)
    result: FaceTaskStatusResult = FaceService.get_status()
    return success_response(t('face_task_pause_success'), data=asdict(result))


@album_bp.route('/face/stop', methods=['POST'])
@admin_required
def stop_face_recognition() -> Tuple[Any, int]:
    """
    用途说明：停止当前仓库的人脸识别任务，并在当前图片处理结束后清空整个待识别队列。
    入参说明：无（仓库 ID 来自请求上下文）。
    返回值说明：统一 JSON 响应，data 为最新任务状态；其他仓库运行中或停止超时返回 409。
    """
    if not FaceService.stop_task():
        status: FaceTaskStatusResult = FaceService.get_status()
        if status.running and status.active_repo_id is not None \
                and status.active_repo_id != status.repo_id:
            return error_response(t('face_task_other_repo_running', repo_id=status.active_repo_id), 409)
        if status.running:
            return error_response(t('face_clear_task_stopping'), 409)
        return error_response(t('face_task_stop_failed'), 500)
    result: FaceTaskStatusResult = FaceService.get_status()
    return success_response(t('face_task_stop_success'), data=asdict(result))


@album_bp.route('/face/clear', methods=['POST'])
@admin_required
def clear_face_recognition_data() -> Tuple[Any, int]:
    """
    用途说明：先停止并清空当前仓库队列，再清空该仓库的人脸特征与图片处理状态。
    入参说明：无（仓库 ID 来自请求上下文）。
    返回值说明：统一 JSON 响应，data 为清理后的任务状态；其他仓库运行中或任务未能在 30 秒内停止时返回 409。
    """
    if not FaceService.clear_data():
        status: FaceTaskStatusResult = FaceService.get_status()
        if status.running and status.active_repo_id is not None \
                and status.active_repo_id != status.repo_id:
            return error_response(t('face_task_other_repo_running', repo_id=status.active_repo_id), 409)
        if status.running:
            return error_response(t('face_clear_task_stopping'), 409)
        return error_response(
            t('face_data_clear_failed', error=t('face_data_operation_failed')),
            500
        )
    result: FaceTaskStatusResult = FaceService.get_status()
    return success_response(t('face_data_clear_success'), data=asdict(result))
