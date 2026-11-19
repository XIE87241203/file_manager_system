from dataclasses import asdict
from datetime import datetime
from typing import Any, List, Tuple
from urllib.parse import quote

from flask import Blueprint, Response, request, send_file

from backend.auth.auth_middleware import token_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.response import success_response, error_response
from backend.organize.organize_models import OrganizeRecordPageResult, OrganizeSettingResult
from backend.organize.organize_record_service import organizeRecordService
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
        rename_script_path: 文件名整理脚本路径, size_op: 大小筛选比较符,
        size_value: 大小筛选数值, size_unit: 大小筛选单位）。
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
        rename_script_path (str): 文件名整理脚本路径，允许为空（使用默认脚本）；
        size_op (str): 文件大小筛选比较符，gt 大于 / lt 小于，空串表示不启用；
        size_value (float): 文件大小筛选数值，不大于 0 表示不启用；
        size_unit (str): 文件大小筛选单位，KB / MB / GB。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功时 data 为归一化后的设置字典。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    pending_dirs = data.get('pending_dirs', [])
    organized_dir = data.get('organized_dir', '')
    extensions = data.get('extensions', [])
    rename_script_path = data.get('rename_script_path', '')
    size_op = data.get('size_op', '')
    size_unit = data.get('size_unit', 'MB')

    # 参数类型校验：列表字段必须为字符串数组，目录/脚本路径/比较符/单位字段必须为字符串
    if (not isinstance(pending_dirs, list) or not all(isinstance(d, str) for d in pending_dirs)
            or not isinstance(extensions, list) or not all(isinstance(e, str) for e in extensions)
            or not isinstance(organized_dir, str) or not isinstance(rename_script_path, str)
            or not isinstance(size_op, str) or not isinstance(size_unit, str)):
        return error_response(t('request_params_error'), 400)

    # 文件大小数值：允许数字或可解析为数字的字符串（前端输入框），非法值返回 400
    try:
        size_value: float = float(data.get('size_value', 0) or 0)
    except (TypeError, ValueError):
        return error_response(t('organize_setting_size_invalid'), 400)

    LogUtils.info(t('organize_setting_update_log', user=request.username))

    try:
        result: OrganizeSettingResult = organizeService.update_settings(
            pending_dirs, organized_dir, extensions, rename_script_path, size_op, size_value, size_unit)
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
    用途说明：保存当前整理结果：按新文件名（不含后缀，自动保留原后缀）移动文件到已整理目录，写入整理历史并推进队列。
    入参说明：JSON Body，字段：
        path (str): 待整理文件完整路径；
        new_name (str): 整理后文件名（不含后缀，保存时自动拼接原文件后缀）。
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


@organize_bp.route('/records/list', methods=['GET'])
@token_required
def get_organize_records() -> Tuple[Any, int]:
    """
    用途说明：分页获取当前仓库的整理记录，按整理时间倒序（时间越靠后排序越靠前）。
    入参说明：Query 参数 page（页码，默认 1）、page_size（每页条数，默认 50，夹取 1-200）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 OrganizeRecordPageResult 字典
        （total: 总条数, page: 当前页码, page_size: 每页条数,
        items: 记录列表，含 id/original_path/original_name/organized_path/organized_name/organize_time，
        其中 organize_time 已转换为本地时间字符串）。
    """
    try:
        page: int = max(1, int(request.args.get('page', 1)))
        page_size: int = min(200, max(1, int(request.args.get('page_size', 50))))
    except (TypeError, ValueError):
        return error_response(t('request_params_error'), 400)
    try:
        result: OrganizeRecordPageResult = organizeRecordService.get_page(page, page_size)
    except Exception as e:
        LogUtils.error(t('organize_records_list_error', error=str(e)))
        return error_response(t('organize_records_list_failed'), 500)
    return success_response(t('organize_records_list_success'), data=asdict(result))


@organize_bp.route('/records/export', methods=['GET'])
@token_required
def export_organize_records() -> Any:
    """
    用途说明：将当前仓库的全部整理记录流式导出为 CSV 文件（UTF-8 带 BOM，分批生成避免全表载入内存）。
        列顺序：序号、整理后文件名、整理前文件名、整理时间（本地时间），按整理时间倒序，序号从 1 连续编号。
    入参说明：无（仓库 ID 由请求头 X-Repo-Id 注入的上下文决定；Token 支持请求头或 ?token= 查询参数）。
    返回值说明：CSV 文件流响应（text/csv，Content-Disposition attachment，文件名含导出时间戳）；
        生成响应前异常时返回统一 JSON 错误响应。
    """
    LogUtils.info(t('organize_records_export_log', user=request.username))
    try:
        filename: str = t('organize_records_export_filename', time=datetime.now().strftime('%Y%m%d_%H%M%S'))
        chunks = organizeRecordService.iter_csv_chunks()
    except Exception as e:
        LogUtils.error(t('organize_records_export_error', error=str(e)))
        return error_response(t('organize_records_export_failed'), 500)
    # RFC 5987 编码中文文件名，兼容各浏览器下载保存
    headers: dict = {
        'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}",
        'Cache-Control': 'no-store'
    }
    return Response(chunks, mimetype='text/csv; charset=utf-8', headers=headers)