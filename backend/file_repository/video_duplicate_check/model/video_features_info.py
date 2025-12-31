# -*- coding: utf-8 -*-
"""
@author: 视频特征信息
@time: 2024/05/17
"""
from typing import Optional, List
import imagehash


class VideoFeaturesInfo:
    """
    存储视频特征信息的类。
    """

    def __init__(self, md5: str, video_hashes: str = "", id: Optional[int] = None):
        """
        初始化视频特征信息对象。

        :param md5: 视频文件的MD5哈希值。
        :param video_hashes: 视频的感知哈希签名（通常是逗号分隔的字符串）。
        :param id: (可选) 数据库中的ID。
        """
        self.id: Optional[int] = id
        self.md5: str = md5
        self.video_hashes: str = video_hashes

    def set_hashes_from_list(self, hashes: List[imagehash.ImageHash]):
        """
        通过 ImageHash 列表设置视频哈希字符串。

        :param hashes: ImageHash 对象列表。
        """
        if not hashes:
            self.video_hashes = ""
            return
        self.video_hashes = ",".join(str(h) for h in hashes)

    def get_hashes_list(self) -> List[imagehash.ImageHash]:
        """
        将存储的字符串转换为 ImageHash 对象列表。

        :return: ImageHash 对象列表。
        """
        if not self.video_hashes:
            return []
        # 过滤掉空字符串，防止 hex_to_hash 报错
        return [imagehash.hex_to_hash(h) for h in self.video_hashes.split(",") if h.strip()]
