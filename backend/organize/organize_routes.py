from dataclasses import asdict
from typing import Any, List, Tuple

from flask import Blueprint, request

from backend.auth.auth_middleware import token_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.response import success_response, error_response
from backend.organize.organize_models import OrganizeSettingResult
from backend.organize.organize_service import organizeService

# 创建整理模块的蓝图
organize_bp = Blueprint('organize', __name__)


@organize_bp.route('/setting/get', methods=['GET'])
@token_required
def get_organize_setting() -> Tuple[Any, int]:
    """
    用途说明：获取当前仓库的整理设置。
    入参说明：无（仓库 ID 由请求头 X-Repo-Id 注入的上下文决定）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data 为 OrganizeSettingResult 字典
        （pending_dirs: 待整理目录列表, organized_dir: 已整理目录, extensions: 后缀名列表）。
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
        extensions (List[str]): 需要整理的后缀名列表。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，成功时 data 为归一化后的设置字典。
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    pending_dirs = data.get('pending_dirs', [])
    organized_dir = data.get('organized_dir', '')
    extensions = data.get('extensions', [])

    # 参数类型校验：列表字段必须为字符串数组，目录字段必须为字符串
    if (not isinstance(pending_dirs, list) or not all(isinstance(d, str) for d in pending_dirs)
            or not isinstance(extensions, list) or not all(isinstance(e, str) for e in extensions)
            or not isinstance(organized_dir, str)):
        return error_response(t('request_params_error'), 400)

    LogUtils.info(t('organize_setting_update_log', user=request.username))

    try:
        result: OrganizeSettingResult = organizeService.update_settings(pending_dirs, organized_dir, extensions)
    except ValueError as e:
        # 业务校验失败（如非法后缀名），返回 400 及具体原因
        return error_response(str(e), 400)
    except Exception as e:
        LogUtils.error(t('organize_setting_save_error', error=str(e)))
        return error_response(t('organize_setting_update_failed'), 500)

    LogUtils.info(t('organize_setting_updated_log', user=request.username))
    return success_response(t('organize_setting_update_success'), data=asdict(result))