from dataclasses import asdict
from typing import Any, Tuple

from flask import Blueprint, request

from backend.auth.auth_middleware import token_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.response import error_response, success_response
from backend.task_center.task_center_service import taskCenterService

# 创建当前任务模块的蓝图
task_bp = Blueprint('tasks', __name__)


@task_bp.route('/list', methods=['GET'])
@token_required
def list_tasks() -> Tuple[Any, int]:
    """
    用途说明：返回当前用户可见仓库中的运行或暂停任务，并附带各任务的可用操作权限。
    入参说明：无（用户名通过 Authorization Header 中的 Token 鉴权获得）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应，data.tasks 为任务数组，data.count 为任务数量。
    """
    result: Any = taskCenterService.list_tasks(request.username)
    return success_response(t('task_center_list_success'), data=asdict(result))


@task_bp.route('/control', methods=['POST'])
@token_required
def control_task() -> Tuple[Any, int]:
    """
    用途说明：对指定仓库的任务执行暂停、恢复或停止，权限由任务中心服务按仓库逐项校验。
    入参说明：JSON Body，包含 key（任务类型）、repo_id（正整数仓库 ID）及 action（pause/resume/stop）。
    返回值说明：Tuple[Any, int] - 统一 JSON 响应；参数错误返回 400，无权限返回 403，任务结束返回 409。
    """
    data: Any = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response(t('request_data_empty'), 400)

    key: Any = data.get('key')
    repo_id: Any = data.get('repo_id')
    action: Any = data.get('action')
    if not isinstance(key, str) or not key or isinstance(repo_id, bool) or not isinstance(repo_id, int) \
            or repo_id <= 0 or action not in ('pause', 'resume', 'stop'):
        return error_response(t('request_params_error'), 400)

    try:
        accepted: bool = taskCenterService.control_task(request.username, key, repo_id, action)
    except ValueError as e:
        message: str = str(e)
        code: int = 403 if message == t('task_center_action_denied') else 409
        LogUtils.error(message)
        return error_response(message, code)
    except Exception as e:
        LogUtils.error(t('task_center_control_error', key=key, repo_id=repo_id, action=action, error=str(e)))
        return error_response(t('internal_error', error=str(e)), 500)

    if not accepted:
        return error_response(t('task_center_action_denied'), 403)
    return success_response(t('task_center_control_success'), data={'accepted': True})
