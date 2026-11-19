from dataclasses import asdict
from typing import Any, List, Tuple

from flask import Blueprint, request, send_file

from backend.auth.auth_middleware import token_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.response import success_response, error_response
from backend.organize.organize_models import OrganizeSettingResult
from backend.organize.organize_service import organizeService
from backend.organize.organize_task_service import organizeTaskService

# 创建整理模块的蓝图
organize_bp = Blueprint('organize', __name__)


@organize_bp.route('/setting/get', methods=['GET'])
@token_required
def get_organize_setting() -> Tuple[Any, int]:
    """
    用途说明：获取当前仓库的整理设置。
    入参说明：无（仓库 ID 由请求头 X-Repo-Id 注入的上下文决定）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 OrganizeSettingResult 字典
        （pending_dirs: 待整理目录列表, organized_dir: 已整理目录, extensions: 后缀名列表,
        rename_script_path: 文件名整理脚本路径）。
    """
    LogUtils.debug(t('organize_setting_get_log', user=request.username))
    result: OrganizeSettingResult = organizeService.get_settings()
    return success_response(t('organize_setting_get_success'), data=asdict(result))


@organize_bp.route('/setting/update', methods=['POST'])
@token_required
def update_organize_setting() -> Tuple[Any, int]:
    """
    用途说明：更新并保存当前仓库的整理设置。
    入参说明：JSON Body，字段：
        pending_dirs (List[str]): 待整理目录列表；
        organized_dir (str): 已整理目录路径，允许为空；
        extensions (List[str]): 需要整理的后缀名列表；
        rename_script_path (str): 文件名整理脚本路径，允许为空（使用默认脚本）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功时 data 为归一化后的设置字典。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    pending_dirs = data.get('pending_dirs', [])
    organized_dir = data.get('organized_dir', '')
    extensions = data.get('extensions', [])
    rename_script_path = data.get('rename_script_path', '')

    # 参数类型校验：列表字段必须为字符串数组，目录/脚本路径字段必须为字符串
    if (not isinstance(pending_dirs, list) or not all(isinstance(d, str) for d in pending_dirs)
            or not isinstance(extensions, list) or not all(isinstance(e, str) for e in extensions)
            or not isinstance(organized_dir, str) or not isinstance(rename_script_path, str)):
        return error_response(t('request_params_error'), 400)

    LogUtils.info(t('organize_setting_update_log', user=request.username))

    try:
        result: OrganizeSettingResult = organizeService.update_settings(
            pending_dirs, organized_dir, extensions, rename_script_path)
    except ValueError as e:
        # 业务校验失败（如非法后缀名），返回 400 及具体原因
        return error_response(str(e), 400)
    except Exception as e:
        LogUtils.error(t('organize_setting_save_error', error=str(e)))
        return error_response(t('organize_setting_update_failed'), 500)

    LogUtils.info(t('organize_setting_updated_log', user=request.username))
    return success_response(t('organize_setting_update_success'), data=asdict(result))


@organize_bp.route('/task/start', methods=['POST'])
@token_required
def start_organize_task() -> Tuple[Any, int]:
    """
    用途说明：启动当前仓库的整理任务：扫描待整理目录并按后缀筛选，建立内存队列。
    入参说明：无（仓库 ID 由请求头 X-Repo-Id 注入的上下文决定）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 {total, remaining, organized_dir}。
    """
    LogUtils.info(t('organize_task_start_log', user=request.username))
    try:
        result = organizeTaskService.start()
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        LogUtils.error(t('organize_task_start_error', error=str(e)))
        return error_response(t('organize_task_start_failed'), 500)
    return success_response(t('organize_task_start_success'), data=asdict(result))


@organize_bp.route('/task/pending', methods=['GET'])
@token_required
def get_organize_pending() -> Tuple[Any, int]:
    """
    用途说明：分页获取剩余待整理文件列表（含类型/大小/整理脚本建议文件名）。
    入参说明：Query 参数 page（页码，默认 1）、page_size（每页条数，默认 50，夹取 1-200）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 {total, remaining, page, page_size, items}。
    """
    try:
        page: int = max(1, int(request.args.get('page', 1)))
        page_size: int = min(200, max(1, int(request.args.get('page_size', 50))))
    except (TypeError, ValueError):
        return error_response(t('request_params_error'), 400)
    try:
        result = organizeTaskService.pending(page, page_size)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        LogUtils.error(t('organize_task_start_error', error=str(e)))
        return error_response(t('organize_task_start_failed'), 500)
    return success_response(t('organize_task_pending_success'), data=asdict(result))


@organize_bp.route('/task/preview', methods=['GET'])
@token_required
def preview_organize_file() -> Any:
    """
    用途说明：流式返回待整理文件内容供图片/视频预览（仅允许当前任务队列内的文件，支持 Range）。
    入参说明：Query 参数 path - 待预览文件完整路径（须在当前待整理队列中）。
    返回值说明：文件流响应（send_file conditional=True）；校验失败时统一 JSON 错误响应。
    """
    path: str = request.args.get('path', '')
    try:
        validated: str = organizeTaskService.validate_preview(path)
    except ValueError as e:
        return error_response(str(e), 403)
    return send_file(validated, conditional=True)


@organize_bp.route('/task/save', methods=['POST'])
@token_required
def save_organize_file() -> Tuple[Any, int]:
    """
    用途说明：保存当前整理结果：按新文件名移动文件到已整理目录，写入整理历史并推进队列。
    入参说明：JSON Body，字段：
        path (str): 待整理文件完整路径；
        new_name (str): 整理后文件名（包括后缀）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 {remaining, total, organized_path, organized_name}。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))
    path = data.get('path', '')
    new_name = data.get('new_name', '')
    if not isinstance(path, str) or not isinstance(new_name, str):
        return error_response(t('request_params_error'), 400)
    try:
        result = organizeTaskService.save(path, new_name, request.username)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        LogUtils.error(t('organize_task_start_error', error=str(e)))
        return error_response(t('organize_task_start_failed'), 500)
    return success_response(t('organize_task_save_success'), data=asdict(result))