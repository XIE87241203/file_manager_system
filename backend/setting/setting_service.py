import hashlib
import json
import os
import sys
from dataclasses import asdict, fields
from typing import Dict, Any, Callable, List

from backend.common.i18n_utils import I18nUtils, t
from backend.common.log_utils import LogUtils
from backend.common.password_utils import hash_password, is_hashed
from backend.common.utils import Utils
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
        "FILE_NAME_ENTRY": "file_name_entry"
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

            # 旧版明文密码自动升级为加盐哈希存储
            self._migrate_plain_password()

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

    def _migrate_plain_password(self) -> None:
        """
        用途：检测到旧版明文密码时，自动升级为 PBKDF2 加盐哈希存储并持久化。
        说明：前端登录传输的是密码的 SHA-256 哈希，因此迁移时先对明文做 SHA-256，
        再做加盐慢哈希，保证迁移后原有登录方式不受影响。
        入参说明：无
        返回值说明：无
        """
        current: str = self._config.user_data.password
        # 空值（用户凭据已迁移至 users 表）或已是哈希则无需迁移
        if not current or is_hashed(current):
            return
        client_hash: str = hashlib.sha256(current.encode('utf-8')).hexdigest()
        self._config.user_data.password = hash_password(client_hash)
        self.save_config()
        LogUtils.info(t('config_password_migrated'))

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
        入参：data: 包含更新项的字典，其一级键名应与 AppConfig 字段名一致（如 'user_data', 'file_repository'）。
        入参：operator_name: 执行更新操作的用户。
        返回值：是否更新成功。
        """
        try:
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
