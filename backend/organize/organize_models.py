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
    """
    pending_dirs: List[str] = field(default_factory=list)
    organized_dir: str = ''
    extensions: List[str] = field(default_factory=list)