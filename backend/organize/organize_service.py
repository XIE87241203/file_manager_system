import json
import math
import os
from typing import List, Tuple

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.db.processor_manager import processor_manager
from backend.model.db.organize_setting_db_model import OrganizeSettingDBModel
from backend.organize.organize_models import OrganizeSettingResult
from backend.organize.rename_script import get_default_script_path, validate_rename_script

# 默认需要整理的后缀名（常用视频后缀），仅在从未保存过整理设置时作为初始值返回
DEFAULT_EXTENSIONS: List[str] = [
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.ts', '.m2ts', '.rmvb', '.rm', '.mpg', '.mpeg', '.3gp', '.vob'
]


class OrganizeService:
    """
    用途：整理模块业务服务类，负责整理设置的读取、校验与持久化。
    说明：设置按仓库隔离，存储于当前仓库数据库的 organize_settings 表（单行记录）。
    """

    def get_settings(self) -> OrganizeSettingResult:
        """
        用途说明：获取当前仓库的整理设置；尚未保存过设置时返回默认值（后缀名默认为常用视频后缀）。
        入参说明：无（仓库路由由当前请求上下文决定）。
        返回值说明：OrganizeSettingResult - 整理设置结果对象。
        """
        model: OrganizeSettingDBModel = processor_manager.organize_setting_processor.get_setting()
        if model is None:
            return OrganizeSettingResult(extensions=list(DEFAULT_EXTENSIONS),
                                         rename_script_path=get_default_script_path())
        return OrganizeSettingResult(
            pending_dirs=self._parse_json_list(model.pending_dirs),
            organized_dir=model.organized_dir or '',
            extensions=self._parse_json_list(model.extensions),
            rename_script_path=self._display_script_path(model.rename_script_path),
            size_op=model.size_op or '',
            size_value=float(model.size_value or 0.0),
            size_unit=model.size_unit or 'MB'
        )

    def update_settings(self, pending_dirs: List[str], organized_dir: str, extensions: List[str],
                        rename_script_path: str = '', size_op: str = '', size_value: float = 0.0,
                        size_unit: str = 'MB') -> OrganizeSettingResult:
        """
        用途说明：校验并保存当前仓库的整理设置（整表覆盖式更新）。
        入参说明：
            pending_dirs (List[str]): 待整理目录列表（来自 API Body）。
            organized_dir (str): 已整理目录路径（来自 API Body），允许为空。
            extensions (List[str]): 需要整理的后缀名列表（来自 API Body）。
            rename_script_path (str): 文件名整理脚本路径（来自 API Body），允许为空或与默认路径一致（均按默认脚本存储）。
            size_op (str): 文件大小筛选比较符（来自 API Body），gt 大于 / lt 小于，其余值按不启用处理。
            size_value (float): 文件大小筛选数值（来自 API Body），不大于 0 表示不启用。
            size_unit (str): 文件大小筛选单位（来自 API Body），KB / MB / GB，其余值按 MB 处理。
        返回值说明：OrganizeSettingResult - 归一化后实际保存的设置结果（脚本路径为空时展示 default.js 实际路径）。
        异常说明：ValueError - 后缀名、整理脚本或文件大小数值非法时抛出，由路由层转换为 400 响应。
        """
        normalized_dirs: List[str] = self._normalize_dirs(pending_dirs)
        normalized_exts: List[str] = self._normalize_extensions(extensions)
        normalized_target: str = (organized_dir or '').strip()
        normalized_script: str = (rename_script_path or '').strip()
        normalized_op, normalized_value, normalized_unit = self._normalize_size(size_op, size_value, size_unit)
        # 填写的路径与默认脚本一致时归一为空串存储（空串即默认），避免把机器相关的绝对路径固化进数据库
        if normalized_script and os.path.normcase(os.path.normpath(normalized_script)) == \
                os.path.normcase(os.path.normpath(get_default_script_path())):
            normalized_script = ''
        # 脚本校验：须为存在的 .js 文件且提供合法 rename 方法（沙箱执行，防死循环）
        validate_rename_script(normalized_script)

        model: OrganizeSettingDBModel = OrganizeSettingDBModel(
            pending_dirs=json.dumps(normalized_dirs, ensure_ascii=False),
            organized_dir=normalized_target,
            extensions=json.dumps(normalized_exts, ensure_ascii=False),
            rename_script_path=normalized_script,
            size_op=normalized_op,
            size_value=normalized_value,
            size_unit=normalized_unit
        )
        processor_manager.organize_setting_processor.save_setting(model)
        return OrganizeSettingResult(
            pending_dirs=normalized_dirs,
            organized_dir=normalized_target,
            extensions=normalized_exts,
            rename_script_path=self._display_script_path(normalized_script),
            size_op=normalized_op,
            size_value=normalized_value,
            size_unit=normalized_unit
        )

    @staticmethod
    def _normalize_size(size_op: str, size_value: float, size_unit: str) -> Tuple[str, float, str]:
        """
        用途说明：归一化文件大小筛选设置：数值不大于 0 时整体视为不启用（比较符清空、数值归零），
            数值大于 0 时比较符仅允许 gt/lt（其余按 gt 处理），单位仅允许 KB/MB/GB（其余按 MB 处理）。
        入参说明：
            size_op (str): 原始比较符（来自 API Body）。
            size_value (float): 原始数值（来自 API Body，已由路由层转为 float）。
            size_unit (str): 原始单位（来自 API Body）。
        返回值说明：Tuple[str, float, str] - 归一化后的 (比较符, 数值, 单位)。
        异常说明：ValueError - 数值为负数或非有限数（NaN/无穷大）时抛出。
        """
        value: float = float(size_value)
        if not math.isfinite(value) or value < 0:
            raise ValueError(t('organize_setting_size_invalid'))
        unit: str = str(size_unit or '').strip().upper()
        if unit not in ('KB', 'MB', 'GB'):
            unit = 'MB'
        if value <= 0:
            # 数值为 0（含留空）表示不启用大小筛选，比较符一并清空
            return '', 0.0, unit
        op: str = str(size_op or '').strip().lower()
        if op not in ('gt', 'lt'):
            op = 'gt'
        return op, value, unit

    @staticmethod
    def size_threshold_bytes(size_op: str, size_value: float, size_unit: str) -> int:
        """
        用途说明：将文件大小筛选设置换算为字节阈值，供扫描时判断文件是否因大小达标而纳入整理。
        入参说明：
            size_op (str): 比较符，gt 大于 / lt 小于，空串表示不启用。
            size_value (float): 数值，不大于 0 表示不启用。
            size_unit (str): 单位 KB / MB / GB，按 1024 进制换算。
        返回值说明：int - 字节阈值；返回 0 表示大小筛选未启用。
        """
        if not size_op or size_value <= 0:
            return 0
        factors: dict = {'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3}
        factor: int = factors.get(str(size_unit).upper(), 1024 ** 2)
        return int(size_value * factor)

    @staticmethod
    def _display_script_path(stored: str) -> str:
        """
        用途说明：把存储值转换为展示值：空串（默认）时展示 default.js 的实际路径，非空时原样展示。
        入参说明：stored (str) - 数据库存储的脚本路径，空串表示使用默认脚本。
        返回值说明：str - 展示用脚本路径。
        """
        return stored if stored else get_default_script_path()

    @staticmethod
    def _parse_json_list(raw: str) -> List[str]:
        """
        用途说明：将数据库中存储的 JSON 数组文本解析为字符串列表，解析失败时回退为空列表。
        入参说明：raw (str) - 数据库中的 JSON 数组文本。
        返回值说明：List[str] - 解析后的字符串列表。
        """
        try:
            parsed = json.loads(raw) if raw else []
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
            return []
        except Exception as e:
            LogUtils.error(t('organize_setting_parse_error', error=str(e)))
            return []

    @staticmethod
    def _normalize_dirs(dirs: List[str]) -> List[str]:
        """
        用途说明：归一化待整理目录列表：去除首尾空白、过滤空项并按原顺序去重。
        入参说明：dirs (List[str]) - 原始目录列表。
        返回值说明：List[str] - 归一化后的目录列表。
        """
        result: List[str] = []
        for item in dirs:
            path: str = str(item).strip()
            if path and path not in result:
                result.append(path)
        return result

    @staticmethod
    def _normalize_extensions(extensions: List[str]) -> List[str]:
        """
        用途说明：归一化后缀名列表：去空白、统一小写、补齐前导点、过滤空项并去重。
        入参说明：extensions (List[str]) - 原始后缀名列表。
        返回值说明：List[str] - 归一化后的后缀名列表（如 ['.mp4', '.mkv']）。
        异常说明：ValueError - 后缀名包含空白或路径分隔符等非法字符时抛出。
        """
        result: List[str] = []
        for item in extensions:
            ext: str = str(item).strip().lower()
            if not ext:
                continue
            # 后缀名不允许包含空白或路径分隔符，防止误录入路径
            if any(ch.isspace() for ch in ext) or '/' in ext or '\\' in ext:
                raise ValueError(t('organize_setting_ext_invalid', ext=str(item)))
            if not ext.startswith('.'):
                ext = '.' + ext
            if ext not in result:
                result.append(ext)
        return result


# 创建全局唯一的整理服务实例，供路由层统一调用
organizeService: OrganizeService = OrganizeService()