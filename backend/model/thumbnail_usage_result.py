from dataclasses import dataclass


@dataclass
class ThumbnailUsageResult:
    """
    用途：表示缩略图目录占用大小的 API 返回数据类。
    入参说明：
        size_bytes (int): 缩略图目录中所有普通文件的总字节数。
    """
    size_bytes: int = 0
