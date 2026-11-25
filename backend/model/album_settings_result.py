from dataclasses import dataclass


@dataclass
class AlbumSettingsResult:
    """
    用途：相册设置项的 API 返回数据类
    """
    thumbnail_dir: str = "thumb"                 # 配置的缩略图存储路径（原样返回）
    thumbnail_dir_effective: str = ""            # 解析后的缩略图目录绝对路径
    thumbnail_size: int = 256                    # 当前仓库缩略图最大边长（像素）