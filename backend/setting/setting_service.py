import hashlib
import json
import os
import sys
from dataclasses import asdict, fields
from typing import Dict, Any, Callable, List, Optional

from backend.common.i18n_utils import I18nUtils, t
from backend.common.log_utils import LogUtils
from backend.common.password_utils import ALGORITHM, hash_password, is_hashed
from backend.common.utils import Utils
from backend.model.db.user_db_model import UserDBModel
from backend.setting.setting_models import AppConfig


class SettingService:
    """
    用途：配置服务类，负责管理系统配置的加载、保存、更新以及敏感信息的处理。
    """

    # 内部映射：JSON 键名 (大写) -> AppConfig 属性名 (小写)
    _SECTION_MAPPING = {
        "USER_DATA": "user_data",
        "FILE_REPOSITORY": "file_repository",
        "DUPLICATE_CHECK": "duplicate_check",
        "FILE_NAME_ENTRY": "file_name_entry",
        "ALBUM": "album"
    }

    def __init__(self) -> None:
        """
        用途：初始化配置服务，使用 AppConfig 数据类管理配置并尝试从本地加载。
        """
        # 1. 初始化默认配置对象
        self._config: AppConfig = AppConfig()
        
        self.password_hash: str = "" # 缓存哈希后的密码

        # 配置变更观察者回调列表，供其他模块以观察者方式监听配置更新
        self._change_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # 2. 配置文件路径
        runtime_path = Utils.get_runtime_path()
        self.config_path: str = os.path.join(runtime_path, 'setting.json')
        
        self._load_config()

    def get_config(self) -> AppConfig:
        """
        用途：获取当前的配置对象。
        返回值：AppConfig 实例。
        """
        return self._config

    def _load_config(self) -> None:
        """
        用途：从本地 JSON 文件中加载配置信息。
        """
        if not os.path.exists(self.config_path):
            self.save_config()
            LogUtils.info("--------------------------------------------------")
            LogUtils.info(t('config_not_found_auto_gen', path=self.config_path))
            LogUtils.info(t('config_please_modify_and_restart'))
            LogUtils.info("--------------------------------------------------")
            sys.exit(0)

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_json = json.load(f)
            
            # 将加载的 JSON 数据映射回数据类
            self._parse_and_merge_config(loaded_json)

            # 校正登录锁定参数，保证最小值为 1（旧版本曾允许 <=0 表示禁用）
            self._normalize_security_params()

            # 加载后立即缓存哈希值
            self._cache_password_hash()
            
        except Exception as e:
            LogUtils.error(t('config_load_error', error=str(e)))
            sys.exit(1)

    def _parse_and_merge_config(self, loaded_json: Dict[str, Any]) -> None:
        """
        用途：将从 JSON 解析出的字典数据合并到 AppConfig 数据类中。
        入参：loaded_json: 从文件读取的配置字典。
        """
        if not isinstance(loaded_json, dict):
            return

        for json_key, attr_name in self._SECTION_MAPPING.items():
            section_data = loaded_json.get(json_key)
            if isinstance(section_data, dict):
                target_obj = getattr(self._config, attr_name)
                # 使用字典数据更新对应的 dataclass 字段
                for key, value in section_data.items():
                    if hasattr(target_obj, key):
                        setattr(target_obj, key, value)

    def _normalize_security_params(self) -> None:
        """
        用途：加载配置后校正登录锁定参数，保证锁定次数与锁定时长最小为 1。
        说明：旧版本允许以 <=0 表示禁用锁定，现已不允许；发现非法值时自动调整为 1 并持久化。
        入参说明：无
        返回值说明：无
        """
        user_data = self._config.user_data
        changed: bool = False
        for attr_name in ('login_max_attempts', 'login_lockout_minutes'):
            value = getattr(user_data, attr_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                setattr(user_data, attr_name, 1)
                changed = True
        if changed:
            self.save_config()
            LogUtils.info(t('config_security_params_normalized',
                            attempts=user_data.login_max_attempts,
                            minutes=user_data.login_lockout_minutes))

    @staticmethod
    def _is_valid_security_param(value: Any) -> bool:
        """
        用途：判断单个登录锁定参数是否合法（必须为不小于 1 的整数，布尔值视为非法）。
        入参说明：value: 待校验的参数值，来自更新请求的 user_data 段。
        返回值说明：bool，合法返回 True，否则返回 False。
        """
        return isinstance(value, int) and not isinstance(value, bool) and value >= 1

    @staticmethod
    def _is_valid_stored_hash(stored: str) -> bool:
        """
        用途：校验密码密文是否为合法的存储格式（pbkdf2_sha256$迭代次数$盐hex$哈希hex）。
        入参说明：stored: 从 setting.json 读到的密码字段值。
        返回值说明：bool - 格式合法返回 True，否则返回 False。
        """
        parts: List[str] = stored.split('$')
        if len(parts) != 4 or parts[0] != ALGORITHM or not parts[1].isdigit():
            return False
        hex_chars: str = '0123456789abcdefABCDEF'
        salt_hex: str = parts[2]
        dk_hex: str = parts[3]
        if not salt_hex or not dk_hex or len(salt_hex) % 2 != 0 or len(dk_hex) % 2 != 0:
            return False
        return all(c in hex_chars for c in salt_hex + dk_hex)

    def apply_password_reset(self) -> None:
        """
        用途：密码恢复通道——setting.json 中的密码字段发生变化时，据此重设初始管理员的密码。
        说明：须在userService.init_admin_user() 之后调用（启动阶段），规则如下：
            - 空值：不处理（凭据由 users 表管理）；
            - 明文：先 SHA-256 再加盐慢哈希，重设初始管理员密码，并把文件中的明文替换为密文；
            - 密文且与管理员当前密码不同：视为重设的新密码，直接应用；
            - 密文且与管理员当前密码相同：不处理；
            - 密文格式非法：记录错误并忽略，不应用；
            - 尚无管理员（首次运行）：沿用旧迁移行为，把明文哈希化留存供初始管理员种子使用。
        入参说明：无
        返回值说明：无
        """
        value: str = self._config.user_data.password
        if not value:
            return

        # 确定目标密文：明文转为加盐慢哈希；密文校验格式后直接使用
        if is_hashed(value):
            if not self._is_valid_stored_hash(value):
                LogUtils.error(t('config_password_reset_invalid'))
                return
            target_hash: str = value
        else:
            client_hash: str = hashlib.sha256(value.encode('utf-8')).hexdigest()
            target_hash = hash_password(client_hash)

        # 延迟导入避免与用户服务模块形成循环依赖
        from backend.user.user_service import userService
        admin: Optional[UserDBModel] = userService.get_first_admin()
        if admin is None:
            # 尚无管理员（首次运行）：把明文哈希化留存，供后续初始管理员种子使用
            if not is_hashed(value):
                self._config.user_data.password = target_hash
                self.save_config()
                LogUtils.info(t('config_password_migrated'))
            return

        if admin.password_hash == target_hash:
            # 密文与管理员当前密码一致，无需重设
            return

        if userService.reset_password_hash(admin.id, target_hash):
            # 重设成功后把文件中的密码替换为密文，避免明文遗留磁盘
            self._config.user_data.password = target_hash
            self.save_config()
            LogUtils.info(t('config_password_reset_applied', username=admin.username))

    def _cache_password_hash(self) -> None:
        """
        用途：缓存当前配置中的密码哈希值（存储字段本身即加盐哈希，直接缓存供登录校验使用）。
        入参说明：无
        返回值说明：无
        """
        self.password_hash = self._config.user_data.password

    def save_config(self) -> None:
        """
        用途：将当前内存中的配置持久化到磁盘，保持大写键名结构。
        """
        config_to_save = {}
        for json_key, attr_name in self._SECTION_MAPPING.items():
            # 获取对应的子配置对象并转为字典
            section_obj = getattr(self._config, attr_name)
            config_to_save[json_key] = asdict(section_obj)

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)
            self._cache_password_hash()
        except Exception as e:
            LogUtils.error(t('config_save_error', error=str(e)))

    def update_settings(self, data: Dict[str, Any], operator_name: str) -> bool:
        """
        用途：批量更新配置项并持久化。
        说明：登录锁定参数（login_max_attempts / login_lockout_minutes）必须为不小于 1 的整数，
        任一非法则拒绝本次更新并返回 False。
        入参：data: 包含更新项的字典，其一级键名应与 AppConfig 字段名一致（如 'user_data', 'file_repository'）。
        入参：operator_name: 执行更新操作的用户。
        返回值：是否更新成功。
        """
        try:
            # 登录锁定参数校验：次数与时长必须为不小于 1 的整数，非法则整体拒绝更新
            user_section = data.get('user_data')
            if isinstance(user_section, dict):
                for param_key in ('login_max_attempts', 'login_lockout_minutes'):
                    if param_key in user_section and not self._is_valid_security_param(user_section[param_key]):
                        LogUtils.error(t('config_security_params_invalid',
                                         key=param_key, value=user_section[param_key]))
                        return False

            old_language: str = self._config.user_data.language
            
            # 自动遍历 AppConfig 的所有字段进行更新
            for field_info in fields(AppConfig):
                section_name = field_info.name
                section_data = data.get(section_name)
                
                if isinstance(section_data, dict):
                    target_obj = getattr(self._config, section_name)
                    for key, value in section_data.items():
                        # 用户凭据已统一由 users 表管理，设置接口不再接受用户名/密码变更
                        if section_name == 'user_data' and key in ('username', 'password'):
                            continue
                        if hasattr(target_obj, key):
                            setattr(target_obj, key, value)

            new_language: str = self._config.user_data.language
            if old_language != new_language:
                I18nUtils.reload(new_language)
                LogUtils.info(f"Language changed from {old_language} to {new_language}, i18n reloaded.")

            self.save_config()
            LogUtils.info(t('config_updated_log', user=operator_name))
            self._notify_change(data)
            return True
        except Exception as e:
            LogUtils.error(t('config_update_logic_error', error=str(e)))
            return False

    def register_change_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        用途：注册配置变更回调，供其他模块以观察者方式监听配置更新，避免设置模块反向依赖业务模块。
        入参：callback: 回调函数，接收本次更新的配置字典 data。
        返回值：无。
        """
        self._change_callbacks.append(callback)

    def _notify_change(self, data: Dict[str, Any]) -> None:
        """
        用途：通知所有已注册的配置变更回调。单个回调异常不影响其他回调及主流程。
        入参：data: 本次更新的配置字典。
        返回值：无。
        """
        for callback in self._change_callbacks:
            try:
                callback(data)
            except Exception as e:
                LogUtils.error(t('config_change_callback_error', error=str(e)))

# 实例化单例
settingService = SettingService()
