from dataclasses import asdict

from flask import Blueprint, request, send_file
import os
from backend.common.response import success_response, error_response
from backend.common.log_utils import LogUtils
from backend.common.auth_middleware import token_required
from backend.common.progress_manager import ProgressStatus
from backend.common.utils import Utils
from backend.file_repository.scan_service import ScanService
from backend.file_repository.duplicate_check.duplicate_service import DuplicateService
from backend.file_repository.file_service import FileService
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
    用途说明：异步触发文件仓库扫描任务
    入参说明：无
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {_get_current_user()} 触发了文件仓库扫描")

    # 修复点 1：先检查扫描状态，避免正在运行中被 clear 破坏数据
    status_info = ScanService.get_status()
    if status_info.get("status") == ProgressStatus.PROCESSING:
        return error_response("扫描任务已在运行中", 400)

    # 确认没在运行后，再进行清空操作
    if not FileService.clear_repository(False):
        return error_response("清空仓库失败", 500)

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
    LogUtils.info(f"用户 {_get_current_user()} 请求停止扫描任务")
    ScanService.stop_scan()
    return success_response("已发送停止指令")


@file_repo_bp.route('/clear', methods=['POST'])
@token_required
def clear_repository():
    """
    用途说明：清空数据库中的文件索引表，同步清理所有缩略图文件及记录，支持选择是否同时清空历史索引表
    入参说明：JSON 包含 clear_history (bool)
    返回值说明：JSON 格式响应，包含操作结果
    """
    data = request.json or {}
    clear_history = data.get('clear_history', False)

    LogUtils.info(f"用户 {_get_current_user()} 请求清空文件数据库 (clear_history={clear_history})")
    if FileService.clear_repository(clear_history):
        return success_response("文件索引及相关缓存已成功清空")
    else:
        return error_response("清空仓库失败", 500)


@file_repo_bp.route('/clear_video_features', methods=['POST'])
@token_required
def clear_video_features():
    """
    用途说明：清空数据库中的视频特征表
    入参说明：无
    返回值说明：JSON 格式响应，包含操作结果
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求清空视频特征库")
    if FileService.clear_video_features():
        return success_response("视频特征库已成功清空")
    else:
        return error_response("清空视频特征库失败", 500)


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
    用途说明：分页获取文件列表，支持搜索和历史查询。
    入参说明：
        page (int): 当前页码，默认 1。
        limit (int): 每页记录数，默认 100。
        sort_by (str): 排序字段，默认 'scan_time'。
        order_asc (bool): 是否正序排序，默认 false (即倒序)。
        search (str): 搜索关键词。
        search_history (bool): 是否查询历史记录，默认 false。
    返回值说明：
        JSON 格式响应，data 字段包含分页结果 (PaginationResult):
        {
            "total": int,           # 总记录数
            "page": int,            # 当前页码
            "limit": int,           # 每页限制数
            "sort_by": str,         # 排序字段
            "order": str,           # 排序方向 (ASC/DESC)
            "list": [               # 数据对象列表
                {
                    # 当 search_history 为 false 时，为 FileIndex 结构:
                    "id": int, "file_path": str, "file_md5": str, "file_size": int,
                    "is_in_recycle_bin": int, "thumbnail_path": str, "scan_time": str
                    
                    # 当 search_history 为 true 时，为 HistoryFileIndex 结构:
                    "id": int, "file_path": str, "file_md5": str, "file_size": int,
                    "scan_time": str, "delete_time": str
                }, ...
            ]
        }
    """
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=100, type=int)
    sort_by = request.args.get('sort_by', default='scan_time')
    order_asc = request.args.get('order_asc', default='false').lower() == 'true'
    search_query = request.args.get('search', default='').strip()
    search_history = request.args.get('search_history', default='false').lower() == 'true'
    if search_history:
        data = FileService.search_history_file_index_list(page, limit, sort_by, order_asc,
                                                          search_query)
        return success_response("获取文件列表成功", data=asdict(data))
    else:
        data = FileService.search_file_index_list(page, limit, sort_by, order_asc,
                                                  search_query)
        return success_response("获取文件列表成功", data=asdict(data))


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

    LogUtils.info(f"用户 {_get_current_user()} 请求批量删除文件，数量: {len(file_paths)}")

    success_count = 0
    failed_paths = []

    for path in file_paths:
        success, msg = FileService.delete_file(path)
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
    LogUtils.info(f"用户 {_get_current_user()} 触发了文件查重")
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
    LogUtils.info(f"用户 {_get_current_user()} 请求停止查重任务")
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
        LogUtils.info(f"用户 {_get_current_user()} 请求删除文件: {file_path}")
        success, msg = FileService.delete_file(file_path)
        if success:
            return success_response("文件删除成功")
        else:
            return error_response(f"文件删除失败: {msg}", 500)

    if group_md5:
        LogUtils.info(f"用户 {_get_current_user()} 请求删除重复组: {group_md5}")
        count, failed = DuplicateService.delete_group(group_md5)
        if not failed:
            return success_response(f"成功删除组内 {count} 个文件")
        else:
            return error_response(f"部分文件删除失败({len(failed)}个): {', '.join(failed[:3])}...",
                                  500)

    return error_response("无效的请求参数", 400)


# --- 缩略图相关路由 ---

@file_repo_bp.route('/thumbnail/start', methods=['POST'])
@token_required
def start_thumbnail_generation():
    """
    用途说明：异步触发缩略图生成任务
    入参说明：JSON 包含 rebuild_all (bool)
    返回值说明：JSON 格式响应
    """
    data = request.json or {}
    rebuild_all = data.get('rebuild_all', False)

    LogUtils.info(f"用户 {_get_current_user()} 触发了缩略图生成 (rebuild_all={rebuild_all})")
    if ThumbnailService.start_async_generation(rebuild_all):
        return success_response("缩略图生成任务已启动")
    else:
        return error_response("缩略图生成任务已在运行中", 400)


@file_repo_bp.route('/thumbnail/stop', methods=['POST'])
@token_required
def stop_thumbnail_generation():
    """
    用途说明：手动停止正在进行的缩略图生成任务
    入参说明：无
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求停止缩略图生成任务")
    ThumbnailService.stop_generation()
    return success_response("已发送停止指令")


@file_repo_bp.route('/thumbnail/progress', methods=['GET'])
@token_required
def get_thumbnail_progress():
    """
    用途说明：获取当前缩略图生成任务的状态和进度信息
    入参说明：无
    返回值说明：包含 status 和 progress 的 JSON 响应
    """
    status_info = ThumbnailService.get_status()
    return success_response("获取进度成功", data=status_info)


@file_repo_bp.route('/thumbnail/clear', methods=['POST'])
@token_required
def clear_thumbnails():
    """
    用途说明：删除所有缩略图文件并清空数据库中的路径记录
    入参说明：无
    返回值说明：JSON 格式响应
    """
    LogUtils.info(f"用户 {_get_current_user()} 请求清空所有缩略图")
    if ThumbnailService.clear_all_thumbnails():
        return success_response("缩略图已成功清空")
    else:
        return error_response("清空缩略图失败", 500)


@file_repo_bp.route('/thumbnail/view', methods=['GET'])
@token_required
def view_thumbnail():
    """
    用途说明：获取并返回缩略图文件的二进制流
    入参说明：query 参数 path (缩略图物理路径)
    返回值说明：图片文件流或错误响应
    """
    path = request.args.get('path')
    if not path:
        return error_response("参数缺失", 400)

    # 修复点 4：强化安全性检查，防止路径穿越攻击
    thumbnail_dir = os.path.abspath(os.path.join(Utils.get_runtime_path(), "cache", "thumbnail"))
    requested_path = os.path.abspath(path)

    if not requested_path.startswith(thumbnail_dir):
        LogUtils.error(f"非法路径请求尝试: {path}")
        return error_response("非法路径请求", 403)

    if not os.path.exists(requested_path):
        return error_response("缩略图文件不存在", 404)

    return send_file(requested_path, mimetype='image/jpeg')
