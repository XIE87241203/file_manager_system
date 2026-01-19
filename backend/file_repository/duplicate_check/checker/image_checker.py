import os
from dataclasses import dataclass
from typing import List, Set

import imagehash
from PIL import Image

from backend.common.log_utils import LogUtils
from backend.file_repository.duplicate_check.checker.base_checker import BaseDuplicateChecker
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModel, DuplicateFileDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel


@dataclass
class ImageData:
    """
    用途：存储图片文件处理所需的数据，包括文件索引和感知哈希值。
    """
    info: FileIndexDBModel
    hash: imagehash.ImageHash

class ImageChecker(BaseDuplicateChecker):
    """
    用途：图片文件查重检查器。通过 MD5 识别完全一致的文件，通过汉明距离识别高度相似的图片，并记录相似率。
    """

    # 常见图片文件后缀名集合
    IMAGE_EXTENSIONS: Set[str] = {
        '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff'
    }

    def __init__(self, threshold: int = 8):
        """
        用途：初始化图片检查器。
        入参说明：
            threshold (int): 汉明距离阈值。小于或等于此值的图片将被视为相似。
        """
        self.threshold: int = threshold
        # 存储待处理的图片数据列表
        self.image_data: List[ImageData] = []

    def add_file(self, file_info: FileIndexDBModel) -> None:
        """
        用途：录入一个图片文件，预计算其感知哈希（pHash）。
        """
        file_path: str = file_info.file_path
        extension: str = os.path.splitext(file_path)[1].lower()

        if self.is_supported(extension):
            try:
                with Image.open(file_path) as img:
                    hash_val = imagehash.phash(img)
                    self.image_data.append(ImageData(info=file_info, hash=hash_val))
            except Exception as e:
                LogUtils.error(f"ImageChecker 处理图片失败: {file_path}, 错误: {str(e)}")

    def get_results(self) -> List[DuplicateGroupDBModel]:
        """
        用途：综合 MD5 和汉明距离进行查重分组，并记录每个文件的相似类型和相似率。
        """
        results: List[DuplicateGroupDBModel] = []
        num_images: int = len(self.image_data)
        if num_images == 0:
            return results

        visited: List[bool] = [False] * num_images

        for i in range(num_images):
            if visited[i]:
                continue

            # 组内的文件列表，存储 DuplicateFileDBModel
            current_group_files: List[DuplicateFileDBModel] = []
            
            # 将当前图片作为代表加入组（相似率 1.0）
            current_group_files.append(DuplicateFileDBModel(
                file_id=self.image_data[i].info.id,
                similarity_type="md5",
                similarity_rate=1.0
            ))
            visited[i] = True

            for j in range(i + 1, num_images):
                if visited[j]:
                    continue

                # 1. MD5 匹配
                if self.image_data[i].info.file_md5 and \
                   self.image_data[i].info.file_md5 == self.image_data[j].info.file_md5:
                    current_group_files.append(DuplicateFileDBModel(
                        file_id=self.image_data[j].info.id,
                        similarity_type="md5",
                        similarity_rate=1.0
                    ))
                    visited[j] = True
                    continue

                # 2. 汉明距离匹配（相似图片）
                distance: int = self.image_data[i].hash - self.image_data[j].hash
                if distance <= self.threshold:
                    # 将汉明距离转换为相似率 (0.0 - 1.0)
                    # pHash 通常为 64 位，因此最大距离为 64
                    similarity_rate: float = 1.0 - (distance / 64.0)
                    current_group_files.append(DuplicateFileDBModel(
                        file_id=self.image_data[j].info.id,
                        similarity_type="hash",
                        similarity_rate=similarity_rate
                    ))
                    visited[j] = True

            if len(current_group_files) > 1:
                results.append(DuplicateGroupDBModel(
                    group_name=f"img_sim_{len(results) + 1}",
                    files=current_group_files
                ))

        LogUtils.info(f"ImageChecker 完成查重，发现 {len(results)} 组重复/相似图片。")
        return results

    def is_supported(self, file_extension: str) -> bool:
        """
        用途：判断该检查器是否支持处理指定的后缀名。
        """
        return file_extension.lower() in self.IMAGE_EXTENSIONS
