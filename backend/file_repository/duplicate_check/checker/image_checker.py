from dataclasses import dataclass
from typing import List, Optional

import imagehash
from PIL import Image

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.utils import Utils
from backend.common.similarity_type import SimilarityType
from backend.db.db_operations import DBOperations
from backend.file_repository.duplicate_check.checker.base_checker import BaseDuplicateChecker
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModel, DuplicateFileDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.image_feature_db_model import ImageFeatureDBModel


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
        用途：录入一个图片文件，优先复用缓存的感知哈希（pHash），未命中时实时计算并写回缓存。
        """
        file_path: str = file_info.file_path
        if not self.is_supported(file_path):
            return

        md5: str = file_info.file_md5
        hash_val: Optional[imagehash.ImageHash] = None

        # 1. 优先从特征库读取缓存，避免重复计算
        if md5:
            cached: Optional[ImageFeatureDBModel] = DBOperations.get_image_feature_by_md5(md5)
            if cached and cached.image_hash:
                try:
                    hash_val = imagehash.hex_to_hash(cached.image_hash)
                except Exception:
                    hash_val = None

        # 2. 未命中则实时计算并持久化
        if hash_val is None:
            try:
                with Image.open(file_path) as img:
                    hash_val = imagehash.phash(img)
            except Exception as e:
                LogUtils.error(t('dup_image_checker_failed', path=file_path, error=str(e)))
                return
            if md5:
                DBOperations.add_image_feature(ImageFeatureDBModel(file_md5=md5, image_hash=str(hash_val)))

        self.image_data.append(ImageData(info=file_info, hash=hash_val))

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
                file_path=self.image_data[i].info.file_path,
                similarity_type=SimilarityType.MD5,
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
                        file_path=self.image_data[j].info.file_path,
                        similarity_type=SimilarityType.MD5,
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
                        file_path=self.image_data[j].info.file_path,
                        similarity_type=SimilarityType.HASH,
                        similarity_rate=similarity_rate
                    ))
                    visited[j] = True

            if len(current_group_files) > 1:
                results.append(DuplicateGroupDBModel(
                    group_name=f"img_sim_{len(results) + 1}",
                    files=current_group_files
                ))

        LogUtils.info(t('dup_image_checker_completed', count=len(results)))
        return results

    def is_supported(self, file_path: str) -> bool:
        """
        用途：判断该检查器是否支持处理指定的路径。
        """
        return Utils.is_image_file(file_path)
