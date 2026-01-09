import hashlib
import json
import os
import sys
from dataclasses import asdict, fields
from typing import Any, Dict

from backend.common.log_utils import LogUtils
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
        "DUPLICATE_CHECK": "duplicate_check"
    }

    def __init__(self) -> None:
        """
        用途：初始化配置服务，使用 AppConfig 数据类管理配置并尝试从本地加载。
        """
        # 1. 初始化默认配置对象
        self._config: AppConfig = AppConfig()
        
        self.password_hash: str = "" # 缓存哈希后的密码
        
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
            LogUtils.info(f"未检测到配置文件，已自动生成默认配置：\n{self.config_path}")
            LogUtils.info("请修改 setting.json 中的配置信息后重新运行。")
            LogUtils.info("--------------------------------------------------")
            sys.exit(0)

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_json = json.load(f)
            
            # 将加载的 JSON 数据映射回数据类
            self._parse_and_merge_config(loaded_json)
            
            # 加载后立即缓存哈希值
            self._cache_password_hash()
            
        except Exception as e:
            LogUtils.error(f"加载配置文件时发生错误: {e}")
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

    def _cache_password_hash(self) -> None:
        """
        用途：计算并缓存当前配置中的密码哈希值。
        """
        # 结构调整：通过 user_data 访问密码
        password_plain = self._config.user_data.password
        self.password_hash = hashlib.sha256(password_plain.encode('utf-8')).hexdigest()

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
            LogUtils.error(f"保存配置文件时发生错误: {e}")

    def update_settings(self, data: Dict[str, Any], operator_name: str) -> bool:
        """
        用途：批量更新配置项并持久化。
        入参：data: 包含更新项的字典，其一级键名应与 AppConfig 字段名一致（如 'user_data', 'file_repository'）。
        入参：operator_name: 执行更新操作的用户。
        返回值：是否更新成功。
        """
        try:
            # 自动遍历 AppConfig 的所有字段进行更新
            for field_info in fields(AppConfig):
                section_name = field_info.name
                section_data = data.get(section_name)
                
                if isinstance(section_data, dict):
                    target_obj = getattr(self._config, section_name)
                    for key, value in section_data.items():
                        if hasattr(target_obj, key):
                            setattr(target_obj, key, value)
            
            self.save_config()
            LogUtils.info(f"用户 {operator_name} 更新了系统配置")
            return True
        except Exception as e:
            LogUtils.error(f"更新配置逻辑执行失败: {e}")
            return False

# 实例化单例
settingService = SettingService()
