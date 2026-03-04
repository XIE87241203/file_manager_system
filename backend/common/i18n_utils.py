import importlib
from typing import Dict, Any

class I18nUtils:
    """
    用途：多语言工具类，负责加载和获取翻译文案
    """
    # 静态常量表示当前语言：'zh' 或 'en'
    LANGUAGE: str = "en"
    
    _translations: Dict[str, str] = {}
    _is_initialized: bool = False

    @classmethod
    def init(cls, language: str = None) -> None:
        """
        用途：根据指定语言初始化翻译文件
        入参说明：
            - language: 指定语言 ('zh' 或 'en')，若为 None 则保持现状
        返回值说明：无
        """
        if language:
            cls.LANGUAGE = language
            cls._is_initialized = False # 强制重新加载
        
        if cls._is_initialized:
            return
        
        try:
            # 动态导入 backend.i18n.zh 或 backend.i18n.en
            module_name: str = f"backend.i18n.{cls.LANGUAGE}"
            # 尝试导入模块
            module: Any = importlib.import_module(module_name)
            # 强制重新加载模块，确保在运行期间切换语言生效
            importlib.reload(module)
            cls._translations = getattr(module, "TRANSLATIONS", {})
        except (ImportError, AttributeError):
            cls._translations = {}
        
        cls._is_initialized = True

    @classmethod
    def reload(cls, language: str = None) -> None:
        """
        用途：刷新语言设置，强制重新加载翻译文案
        入参说明：
            - language: 指定新语言 ('zh' 或 'en')，可选
        返回值说明：无
        """
        if language:
            cls.LANGUAGE = language
        cls._is_initialized = False
        cls.init()

    @classmethod
    def get(cls, key: str, default: str = None, **kwargs) -> str:
        """
        用途：获取对应 key 的翻译文案，并支持格式化
        入参说明：
            - key: 翻译键值
            - default: 如果找不到 key 时返回的默认值
            - kwargs: 用于格式化文案的参数
        返回值说明：str, 翻译后的文案
        """
        if not cls._is_initialized:
            cls.init()
        
        text: str = cls._translations.get(key, default if default is not None else key)
        
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

def t(key: str, default: str = None, **kwargs) -> str:
    """
    用途：简写形式的翻译函数
    入参说明：
        - key: 翻译键值
        - default: 默认值
        - kwargs: 格式化参数
    返回值说明：str, 翻译后的文案
    """
    return I18nUtils.get(key, default, **kwargs)
