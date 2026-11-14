from typing import List

from backend.common.utils import Utils
from backend.setting.setting_service import settingService


class SearchQueryHelper:
    """
    用途：搜索关键词预处理助手，结合系统配置将原始搜索词转换为 SQL LIKE 通配模式。
    配置读取集中于此，避免通用工具层（common）反向依赖业务配置。
    """

    @staticmethod
    def process_search_query(search_query: str) -> str:
        """
        用途说明：对搜索关键词进行预处理，根据配置替换特殊字符并转义为 SQL LIKE 格式。
        入参说明：search_query (str): 原始搜索词。
        返回值说明：str: 处理后可直接用于 LIKE 子句的字符串（如 %keyword%）。
        """
        search_replace_chars: List[str] = settingService.get_config().file_repository.search_replace_chars
        return Utils.build_like_pattern(search_query, search_replace_chars)