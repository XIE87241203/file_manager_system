from dataclasses import dataclass, field
from typing import List


@dataclass
class OrganizeSettingResult:
    """
    用途：整理模块设置的 API 返回数据类。
    字段说明：
        pending_dirs (List[str]): 待整理目录列表，整理流程将扫描这些目录（含子目录）。
        organized_dir (str): 已整理目录，整理完成的文件将被转移至此；空字符串表示未配置。
        extensions (List[str]): 需要整理的后缀名列表（统一小写、以 . 开头），
            待整理目录内匹配这些后缀名的文件都会进入整理流程。
        rename_script_path (str): 文件名整理脚本（.js）路径；未自定义时展示默认脚本 default.js 的实际路径。
        size_op (str): 文件大小筛选比较符，gt 表示大于、lt 表示小于；空串表示不启用大小筛选。
        size_value (float): 文件大小筛选数值；不大于 0 表示不启用大小筛选。
        size_unit (str): 文件大小筛选单位，KB / MB / GB（按 1024 进制换算）。
    """
    pending_dirs: List[str] = field(default_factory=list)
    organized_dir: str = ''
    extensions: List[str] = field(default_factory=list)
    rename_script_path: str = ''
    size_op: str = ''
    size_value: float = 0.0
    size_unit: str = 'MB'


@dataclass
class OrganizePendingFileInfo:
    """
    用途：待整理文件信息数据类（整理任务列表条目）。
    字段说明：
        path (str): 文件完整路径。
        name (str): 文件名（包括后缀）。
        file_type (str): 文件类型，image / video / other，决定预览方式。
        size (int): 文件字节数，读取失败时为 0。
        suggestion (str): 整理脚本 rename 方法给出的建议文件名（脚本失败时回退为原文件名）。
    """
    path: str = ''
    name: str = ''
    file_type: str = 'other'
    size: int = 0
    suggestion: str = ''


@dataclass
class OrganizeTaskStartResult:
    """
    用途：整理任务启动结果数据类。
    字段说明：
        total (int): 本次扫描到的待整理文件总数。
        remaining (int): 剩余待整理数量（启动时等于 total）。
        organized_dir (str): 已整理目录路径（保存时文件移入此处）。
    """
    total: int = 0
    remaining: int = 0
    organized_dir: str = ''


@dataclass
class OrganizePendingResult:
    """
    用途：待整理文件分页查询结果数据类。
    字段说明：
        total (int): 本次任务待整理文件总数。
        remaining (int): 当前剩余待整理数量。
        page (int): 当前页码（从 1 开始）。
        page_size (int): 每页条数。
        items (List[OrganizePendingFileInfo]): 当前页的待整理文件信息列表。
    """
    total: int = 0
    remaining: int = 0
    page: int = 1
    page_size: int = 50
    items: List[OrganizePendingFileInfo] = field(default_factory=list)


@dataclass
class OrganizeSaveResult:
    """
    用途：整理保存结果数据类。
    字段说明：
        remaining (int): 保存后剩余待整理数量。
        total (int): 本次任务待整理文件总数。
        organized_path (str): 整理后文件完整路径。
        organized_name (str): 整理后文件名（包括后缀）。
    """
    remaining: int = 0
    total: int = 0
    organized_path: str = ''
    organized_name: str = ''