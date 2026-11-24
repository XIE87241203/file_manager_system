import os
from dataclasses import asdict
from typing import Optional

from flask import Blueprint, request, send_file

from backend.album.album_service import AlbumService
from backend.auth.auth_middleware import token_required
from backend.common.file_type_enum import FileType
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import set_current_repo_id
from backend.common.response import success_response, error_response
from backend.model.album_settings_result import AlbumSettingsResult
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.pagination_result import PaginationResult


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
def list_album_media():
    """
    用途说明：分页获取相册媒体列表（图片/视频），支持文件名搜索与排序。
    入参说明（Query）：
        page (int): 页码，默认 1。
        limit (int): 每页数量，默认 30。
        sort_by (str): 排序字段，默认 album_time（EXIF 优先、文件修改时间兜底，供时间轴分组）。
        order_asc (bool): 是否升序，默认 false。
        search (str): 文件名搜索关键词。
        file_type (str): 媒体类型筛选，空串为全部，可选 image（仅图片）/ video（仅视频）；非法值按全部处理。
    返回值说明：统一 JSON 响应，data 为分页结果。
    """
    page: int = request.args.get('page', default=1, type=int)
    limit: int = request.args.get('limit', default=30, type=int)
    sort_by: str = request.args.get('sort_by', default='album_time')
    order_asc: bool = request.args.get('order_asc', default='false').lower() == 'true'
    search_query: str = request.args.get('search', default='').strip()
    file_type: str = request.args.get('file_type', default='').strip()
    if file_type not in ('', FileType.IMAGE.value, FileType.VIDEO.value):
        file_type = ''

    result: PaginationResult = AlbumService.get_album_list(page, limit, sort_by, order_asc, search_query, file_type)
    return success_response(t('album_list_success'), data=asdict(result))


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


@album_bp.route('/settings', methods=['GET'])
@token_required
def get_album_settings():
    """
    用途说明：获取相册设置（缩略图存储路径）。
    入参说明：无
    返回值说明：统一 JSON 响应，data 为相册设置对象。
    """
    settings: AlbumSettingsResult = AlbumService.get_settings()
    return success_response(t('album_settings_get_success'), data=asdict(settings))


@album_bp.route('/settings', methods=['POST'])
@token_required
def update_album_settings():
    """
    用途说明：更新相册设置中的缩略图存储路径。
    入参说明（JSON）：thumbnail_dir (str) - 新的缩略图存储路径。
    返回值说明：统一 JSON 响应，data 为更新后的相册设置对象。
    """
    data: dict = request.get_json(silent=True) or {}
    thumbnail_dir: str = data.get('thumbnail_dir', '')
    settings: Optional[AlbumSettingsResult] = AlbumService.update_settings(thumbnail_dir, _get_current_user())
    if settings is None:
        return error_response(t('album_settings_update_failed'), 500)
    return success_response(t('album_settings_update_success'), data=asdict(settings))