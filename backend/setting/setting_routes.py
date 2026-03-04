from dataclasses import asdict

from flask import Blueprint, request

from backend.common.auth_middleware import token_required
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.response import success_response, error_response
from backend.setting.setting_service import settingService

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
    
    return success_response(t('config_get_success'), data=data)

@setting_bp.route('/update', methods=['POST'])
@token_required
def update_setting():
    """
    用途：更新并保存配置信息
    入参说明：JSON 对象，包含需要更新的配置项（user_data、file_repository 或 duplicate_check）
    返回值说明：操作结果响应
    """
    # 使用 silent=True 防止解析失败时直接返回 HTML 400 错误
    data = request.get_json(silent=True)
    if not data:
        return error_response(t('request_data_empty'))

    LogUtils.info(t('config_update_log', user=request.username))

    # 调用 SettingService 的封装逻辑处理配置更新及相关业务逻辑
    if settingService.update_settings(data, request.username):
        # 检查是否修改了自动刷新相关的配置
        file_repo_data = data.get('file_repository')
        if isinstance(file_repo_data, dict):
            if 'auto_refresh_time' in file_repo_data or 'auto_refresh_enabled' in file_repo_data:
                # 动态导入以避免循环依赖
                from backend.file_repository.auto_scan_service import AutoScanService
                AutoScanService.refresh_config()
                LogUtils.info(t('repo_auto_scan_updated', time=file_repo_data.get('auto_refresh_time', '')))

        LogUtils.info(t('config_updated_log', user=request.username))
        return success_response(t('config_update_success'))
    else:
        return error_response(t('config_update_failed'), 500)
