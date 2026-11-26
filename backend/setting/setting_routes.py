from dataclasses import asdict

from flask import Blueprint, request

from backend.auth.auth_middleware import token_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import get_current_repo_id
from backend.common.response import success_response, error_response
from backend.db.db_constants import DBConstants
from backend.setting.setting_service import settingService
from backend.user.user_service import userService

# 创建设置模块的蓝图
setting_bp = Blueprint('setting', __name__)

@setting_bp.route('/get', methods=['GET'])
@token_required
def get_setting():
    """
    用途：获取当前的配置信息
    入参说明：无
    返回值说明：包含全局配置信息 (AppConfig) 的 JSON 响应
    """
    LogUtils.debug(t('config_get_log', user=request.username))
    
    # 获取完整的配置对象并转换为字典返回
    config = settingService.get_config()
    data = asdict(config)

    # 安全处理：密码哈希不允许返回给前端，避免敏感信息泄露
    data.get('user_data', {}).pop('password', None)

    return success_response(t('config_get_success'), data=data)

@setting_bp.route('/update', methods=['POST'])
@token_required
def update_setting():
    """
    用途：更新并保存配置信息
    入参说明：JSON 对象，包含需要更新的配置项（user_data、file_repository、duplicate_check 或 album）
    返回值说明：操作结果响应
    """
    # 使用 silent=True 防止解析失败时直接返回 HTML 400 错误
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    # 缩略图尺寸现为全系统相册配置，禁止仓库成员通过通用设置接口绕过相册页的仓库管理员校验。
    album_section = data.get('album')
    if isinstance(album_section, dict) and 'thumbnail_size' in album_section:
        repo_id: int = get_current_repo_id()
        if userService.get_repo_permission(request.username, repo_id) \
                != DBConstants.UserRepositoryPermission.PERMISSION_ADMIN:
            return error_response(t('user_repo_admin_required'), 403)

    LogUtils.info(t('config_update_log', user=request.username))

    # 调用 SettingService 的封装逻辑处理配置更新及相关业务逻辑
    if settingService.update_settings(data, request.username):
        LogUtils.info(t('config_updated_log', user=request.username))
        return success_response(t('config_update_success'))
    else:
        return error_response(t('config_update_failed'), 500)
