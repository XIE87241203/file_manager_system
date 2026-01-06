import json
import os
import sys
import hashlib
from typing import Any, Dict, Optional
from backend.common.utils import Utils
from backend.common.log_utils import LogUtils

class SettingService:
    """
    用途：配置服务类，负责管理系统配置的加载、保存、更新以及敏感信息的处理。
    """
    def __init__(self) -> None:
        """
        用途：初始化配置服务，设置默认配置项并尝试从本地加载。
        入参说明：无
        返回值说明：无
        """
        # 1. 设有变量默认值
        self.user_data: Dict[str, str] = {
            "username": "admin",
            "password": "admin123" # 明文存储
        }
        # 文件仓库设置
        self.file_repository: Dict[str, Any] = {
            "directories": [],          # 仓库目录列表
            "scan_suffixes": ["*"],     # 扫描文件后缀，支持通配符
            "search_replace_chars": [],  # 搜索时需要替换为 .* 的字符列表
            "ignore_filenames": [],     # 忽略文件名列表
            "ignore_filenames_case_insensitive": True, # 忽略文件名时是否忽略大小写
            "ignore_paths": [],          # 忽略路径列表
            "ignore_paths_case_insensitive": True,     # 忽略路径时是否忽略大小写
            "thumbnail_size": 256,       # 缩略图最大尺寸（清晰度）
            "quick_view_thumbnail": False # 是否启用鼠标悬停快速查看缩略图
        }
        # 查重设置
        self.duplicate_check: Dict[str, Any] = {
            "image_threshold": 8,                   # 图片汉明距离阈值
            "video_frame_similar_distance": 5,      # 视频帧相似判定阈值
            "video_frame_similarity_rate": 0.7,     # 视频帧匹配成功的占比阈值
            "video_interval_seconds": 30,           # 视频采样间隔（秒）
            "video_max_duration_diff_ratio": 0.6    # 视频最大时长比例阈值
        }
        self.password_hash: str = "" # 缓存哈希后的密码
        
        # 2. 配置文件现在在运行时根目录下
        runtime_path = Utils.get_runtime_path()
        self.config_path: str = os.path.join(runtime_path, 'setting.json')
        
        self._load_config()

    def _load_config(self) -> None:
        """
        用途：从本地 JSON 文件中加载配置信息。
        入参说明：无
        返回值说明：无
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
                config = json.load(f)
            
            # 补全配置文件缺少的部分，并将有效值合并到内存
            self._check_and_complete_config(config)
            
            # 加载后立即缓存哈希值
            self._cache_password_hash()
            
        except Exception as e:
            LogUtils.error(f"加载配置文件时发生错误: {e}")
            sys.exit(1)

    def _check_and_complete_config(self, loaded_config: Dict[str, Any]) -> None:
        """
        用途：检查并补全配置项，确保内存中的配置结构完整。
        入参说明：
            - loaded_config: 从文件中加载的配置字典。
        返回值说明：无
        """
        if not isinstance(loaded_config, dict):
            LogUtils.error("配置文件格式错误，应为 JSON 对象。")
            return

        needs_save = False
        # 配置映射关系：JSON中的键 -> 类中的属性名
        mapping = {
            "USER_DATA": "user_data",
            "FILE_REPOSITORY": "file_repository",
            "DUPLICATE_CHECK": "duplicate_check"
        }

        for json_key, attr_name in mapping.items():
            default_section = getattr(self, attr_name)
            loaded_section = loaded_config.get(json_key)

            if not isinstance(loaded_section, dict):
                needs_save = True
            else:
                for key in default_section.keys():
                    if key not in loaded_section:
                        needs_save = True
                    else:
                        default_section[key] = loaded_section[key]

        if needs_save:
            self.save_config()
            LogUtils.info(f"配置文件 {self.config_path} 已自动同步默认值。")

    def _cache_password_hash(self) -> None:
        """
        用途：计算并缓存当前配置中的密码哈希值。
        入参说明：无
        返回值说明：无
        """
        password_plain = self.user_data.get('password', '')
        self.password_hash = hashlib.sha256(password_plain.encode('utf-8')).hexdigest()

    def save_config(self) -> None:
        """
        用途：将当前内存中的配置持久化到磁盘。
        入参说明：无
        返回值说明：无
        """
        config = {
            "USER_DATA": self.user_data,
            "FILE_REPOSITORY": self.file_repository,
            "DUPLICATE_CHECK": self.duplicate_check
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self._cache_password_hash()
        except Exception as e:
            LogUtils.error(f"保存配置文件时发生错误: {e}")

    def update_settings(self, data: Dict[str, Any], operator_name: str) -> bool:
        """
        用途：批量更新配置项并持久化。
        入参说明：
            - data: 包含待更新配置项的字典。
            - operator_name: 执行更新操作的用户。
        返回值说明：
            - bool: 更新并保存是否成功。
        """
        # 1. 更新内存属性
        if 'user_data' in data:
            for key, value in data['user_data'].items():
                self.user_data[key] = value
        
        if 'file_repository' in data:
            self.file_repository = data['file_repository']

        if 'duplicate_check' in data:
            self.duplicate_check = data['duplicate_check']
        
        # 2. 持久化
        try:
            self.save_config()
            LogUtils.info(f"用户 {operator_name} 更新了系统配置")
            return True
        except Exception as e:
            LogUtils.error(f"更新配置逻辑执行失败: {e}")
            return False

# 实例化单例
settings = SettingService()
