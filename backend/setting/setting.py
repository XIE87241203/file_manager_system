import json
import os
import sys
import hashlib
from backend.common.utils import Utils

class Setting:
    """
    用途：配置类，用于读取并存储运行时目录下的 setting.json 中的配置信息，并缓存密码哈希值
    """
    def __init__(self):
        """
        用途：初始化配置类，设置默认值并加载配置文件
        入参说明：无
        返回值说明：无
        """
        # 1. 设有变量默认值
        self.user_data = {
            "username": "admin",
            "password": "admin123" # 明文存储
        }
        # 文件仓库设置
        self.file_repository = {
            "directories": [],          # 仓库目录列表
            "scan_suffixes": ["*"],     # 扫描文件后缀，支持通配符
            "search_replace_chars": []  # 搜索时需要替换为 .* 的字符列表，用于正则表达式匹配
        }
        self.password_hash = "" # 缓存哈希后的密码
        
        # 2. 配置文件现在在运行时根目录下
        runtime_path = Utils.get_runtime_path()
        self.config_path = os.path.join(runtime_path, 'setting.json')
        
        self._load_config()

    def _load_config(self):
        """
        用途：从 setting.json 文件中加载配置。如果文件不存在则生成默认配置并退出。
        入参说明：无
        返回值说明：无
        """
        if not os.path.exists(self.config_path):
            self.save_config()
            # 注意：此处因为 Setting 初始化较早，LogUtils 可能还未 init，故保留 print 用于关键引导
            print("--------------------------------------------------")
            print(f"未检测到配置文件，已自动生成默认配置：\n{self.config_path}")
            print("请修改 setting.json 中的配置信息（如用户名和密码）后重新运行后端。")
            print("--------------------------------------------------")
            sys.exit(0)

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 加载用户配置
                loaded_user_data = config.get('USER_DATA', {})
                # 合并配置，保留默认值中存在但 JSON 中缺失的字段
                for key, value in loaded_user_data.items():
                    self.user_data[key] = value
                
                # 加载文件仓库配置
                loaded_file_repo = config.get('FILE_REPOSITORY', {})
                # 合并配置，确保新添加的字段（如 search_replace_chars）也能被正确加载或保留默认值
                for key, value in loaded_file_repo.items():
                    self.file_repository[key] = value
            
            # 加载后立即缓存哈希值
            self._cache_password_hash()
            
        except Exception as e:
            print(f"加载配置文件时发生错误: {e}")
            sys.exit(1)

    def _cache_password_hash(self):
        """
        用途：将配置中的明文密码计算为 SHA-256 哈希值并缓存
        入参说明：无
        返回值说明：无
        """
        password_plain = self.user_data.get('password', '')
        self.password_hash = hashlib.sha256(password_plain.encode('utf-8')).hexdigest()

    def save_config(self):
        """
        用途：将当前配置序列化并保存到 setting.json 文件中
        入参说明：无
        返回值说明：无
        """
        config = {
            "USER_DATA": self.user_data,
            "FILE_REPOSITORY": self.file_repository
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            # 保存后同步更新哈希缓存
            self._cache_password_hash()
        except Exception as e:
            print(f"保存配置文件时发生错误: {e}")

# 实例化单例
settings = Setting()
