import json
import os
import re
from typing import Any, List, Optional, Tuple

from backend.common.i18n_utils import I18nUtils, t
from backend.common.log_utils import LogUtils
from backend.system.changelog_models import ChangelogEntryResult, ChangelogResult
from config import GlobalConfig


class ChangelogService:
    """
    用途说明：读取集中维护的更新日志文件，按语言、已读版本和展示范围生成首页弹窗数据。
    """

    # 更新日志内容文件；每次发布新版本时必须同步新增对应版本条目
    CHANGELOG_PATH: str = os.path.join(os.path.dirname(__file__), 'changelog.json')
    VERSION_PATTERN = re.compile(r'^[vV]?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$')

    @staticmethod
    def version_key(version: str) -> Tuple[int, int, int]:
        """
        用途说明：将语义版本号转换为可比较的数字元组。
        入参说明：version (str): 例如 1.1.0 或 v1.1.0 的版本号。
        返回值说明：Tuple[int, int, int]: 主版本、次版本和修订号；格式非法时抛出 ValueError。
        """
        match: Optional[re.Match] = ChangelogService.VERSION_PATTERN.fullmatch((version or '').strip())
        if not match:
            raise ValueError(t('sys_changelog_invalid_version_format', version=version))
        return int(match.group(1)), int(match.group(2)), int(match.group(3))

    @staticmethod
    def _localized(value: Any) -> str:
        """
        用途说明：从更新日志中的双语对象提取当前系统语言文本。
        入参说明：value (Any): 字符串或 {zh, en} 双语对象。
        返回值说明：str: 当前语言文本，缺失时依次回退中文、英文和空字符串。
        """
        if isinstance(value, str):
            return value.strip()
        if not isinstance(value, dict):
            return ''
        language: str = I18nUtils.LANGUAGE if I18nUtils.LANGUAGE in ('zh', 'en') else 'zh'
        for key in (language, 'zh', 'en'):
            text: Any = value.get(key)
            if isinstance(text, str) and text.strip():
                return text.strip()
        return ''

    @classmethod
    def load_entries(cls) -> List[ChangelogEntryResult]:
        """
        用途说明：读取并校验更新日志文件，转换为按版本倒序排列的数据类列表。
        入参说明：无。
        返回值说明：List[ChangelogEntryResult]: 全部版本更新日志；文件缺失或内容非法时记录日志并抛出异常。
        """
        try:
            with open(cls.CHANGELOG_PATH, 'r', encoding='utf-8') as file:
                raw_data: Any = json.load(file)
            raw_entries: Any = raw_data.get('entries') if isinstance(raw_data, dict) else None
            if not isinstance(raw_entries, list):
                raise ValueError(t('sys_changelog_invalid_root'))

            entries: List[ChangelogEntryResult] = []
            seen_versions: set[str] = set()
            for index, raw_entry in enumerate(raw_entries):
                if not isinstance(raw_entry, dict):
                    raise ValueError(t('sys_changelog_invalid_entry', index=index + 1))
                version: str = str(raw_entry.get('version') or '').strip()
                cls.version_key(version)
                if version in seen_versions:
                    raise ValueError(t('sys_changelog_duplicate_version', version=version))
                seen_versions.add(version)

                raw_highlights: Any = raw_entry.get('highlights')
                if not isinstance(raw_highlights, list):
                    raise ValueError(t('sys_changelog_invalid_entry', index=index + 1))
                highlights: List[str] = [cls._localized(item) for item in raw_highlights]
                highlights = [item for item in highlights if item]
                if not highlights:
                    raise ValueError(t('sys_changelog_invalid_entry', index=index + 1))

                notice: str = cls._localized(raw_entry.get('rebuild_index_notice'))
                entries.append(ChangelogEntryResult(
                    version=version,
                    date=str(raw_entry.get('date') or '').strip(),
                    highlights=highlights,
                    rebuild_index_notice=notice or None
                ))

            entries.sort(key=lambda entry: cls.version_key(entry.version), reverse=True)
            return entries
        except Exception as error:
            LogUtils.error(t('sys_changelog_load_error', error=str(error)))
            raise

    @classmethod
    def get_changelog(cls, scope: str, seen_version: Optional[str]) -> ChangelogResult:
        """
        用途说明：生成指定范围的更新日志数据，并判断当前用户是否需要自动弹出。
        入参说明：
            scope (str): all 表示全部日志，unread 表示仅上次已读版本之后的新版本。
            seen_version (Optional[str]): 当前用户已读版本号，无记录时为 None。
        返回值说明：ChangelogResult: 当前版本、已读版本、自动弹出标识和筛选后的日志列表。
        """
        all_entries: List[ChangelogEntryResult] = cls.load_entries()
        entries: List[ChangelogEntryResult] = all_entries
        if scope == 'unread' and seen_version:
            try:
                seen_key: Tuple[int, int, int] = cls.version_key(seen_version)
                known_keys: set[Tuple[int, int, int]] = {
                    cls.version_key(entry.version) for entry in all_entries
                }
                if seen_key in known_keys:
                    entries = [
                        entry for entry in all_entries
                        if cls.version_key(entry.version) > seen_key
                    ]
            except ValueError:
                # 已读记录来自未知版本时按“没有看过记录”处理，展示全部内容。
                entries = all_entries

        current_version: str = GlobalConfig.APP_VERSION
        auto_show: bool = (
            scope == 'unread'
            and seen_version != current_version
            and bool(entries)
        )
        return ChangelogResult(
            current_version=current_version,
            seen_version=seen_version,
            auto_show=auto_show,
            entries=entries
        )

    @classmethod
    def is_known_version(cls, version: str) -> bool:
        """
        用途说明：判断待记录的版本号是否存在于更新日志文件。
        入参说明：version (str): 待记录的版本号。
        返回值说明：bool: 存在返回 True，不存在或读取失败返回 False。
        """
        try:
            target_key: Tuple[int, int, int] = cls.version_key(version)
            return any(
                cls.version_key(entry.version) == target_key
                for entry in cls.load_entries()
            )
        except Exception as error:
            LogUtils.error(t('sys_changelog_load_error', error=str(error)))
            return False
