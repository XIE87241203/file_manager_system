# -*- coding: utf-8 -*-
"""
@author: MD5校验工具
@time: 2024/05/17
"""
import hashlib
import os
from src.utils.log_utils import logger

class MD5Helper:
    """
    MD5校验工具类，用于计算文件的MD5值或快速指纹。
    """

    @staticmethod
    def calculate_md5(file_path: str) -> str:
        """
        计算文件的全量MD5哈希值。
        适用于需要绝对唯一性的场景，但大文件计算较慢。

        :param file_path: 文件的路径。
        :return: 文件的MD5哈希值。
        :raises FileNotFoundError: 如果文件路径不存在。
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except FileNotFoundError:
            logger.error(f"MD5计算失败，文件未找到: {file_path}", caller="MD5Helper")
            raise FileNotFoundError(f"文件未找到: {file_path}")
