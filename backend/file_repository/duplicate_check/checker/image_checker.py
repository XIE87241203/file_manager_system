import os
from PIL import Image
import imagehash
from typing import List, Dict, Set
from backend.file_repository.duplicate_check.checker.base_checker import BaseDuplicateChecker
from backend.db.model.file_index import FileIndex
from backend.common.log_utils import LogUtils
from backend.file_repository.duplicate_check.checker.models.duplicate_models import DuplicateGroup, DuplicateFile

class ImageChecker(BaseDuplicateChecker):
    """
    用途：图片文件查重检查器。先通过 MD5 判断完全一致的文件，再通过汉明距离（基于感知哈希）识别内容高度相似的图片。
    """

    # 常见图片文件后缀名集合
    IMAGE_EXTENSIONS: Set[str] = {
        '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff'
    }

    def __init__(self, threshold: int = 8):
        """
        用途：初始化图片检查器。
        入参说明：
            threshold (int): 汉明距离阈值。小于或等于此值的图片将被视为相似。默认为 8。
        """
        self.threshold: int = threshold
        # 存储待处理的图片数据列表
        self.image_data: List[Dict] = []

    def add_file(self, file_info: FileIndex) -> None:
        """
        用途：录入一个图片文件，预计算其感知哈希（pHash）并存入待处理列表。
        入参说明：
            file_info (FileIndex): 包含路径和 MD5 等信息的文件索引对象。
        返回值说明：
            None
        """
        file_path = file_info.file_path
        extension = os.path.splitext(file_path)[1].lower()

        if self.is_supported(extension):
            try:
                # 使用 PIL 打开图片并计算感知哈希 (pHash)
                with Image.open(file_path) as img:
                    # pHash 对旋转、缩放、亮度调整具有较好的鲁棒性
                    hash_val = imagehash.phash(img)
                    self.image_data.append({
                        "info": file_info,
                        "hash": hash_val
                    })
            except Exception as e:
                LogUtils.error(f"ImageChecker 处理图片失败: {file_path}, 错误: {str(e)}")

    def get_results(self) -> List[DuplicateGroup]:
        """
        用途：综合 MD5 和汉明距离进行查重分组。
        入参说明：无
        返回值说明：
            List[DuplicateGroup]: 包含重复或相似图片的分组列表。
        """
        results: List[DuplicateGroup] = []
        num_images = len(self.image_data)
        if num_images == 0:
            return results

        # 记录已分配到组的图片索引
        visited = [False] * num_images

        for i in range(num_images):
            if visited[i]:
                continue

            current_group_indices = [i]
            visited[i] = True
            
            # 用于标记当前组是否是因为 MD5 完全一致而形成的
            is_exact_md5_match = False

            # 遍历剩余图片
            for j in range(i + 1, num_images):
                if visited[j]:
                    continue

                # 1. 先判断 MD5 是否完全相同
                if self.image_data[i]["info"].file_md5 and \
                   self.image_data[i]["info"].file_md5 == self.image_data[j]["info"].file_md5:
                    current_group_indices.append(j)
                    visited[j] = True
                    is_exact_md5_match = True
                    continue

                # 2. 如果 MD5 不同，则判断汉明距离
                distance = self.image_data[i]["hash"] - self.image_data[j]["hash"]
                if distance <= self.threshold:
                    current_group_indices.append(j)
                    visited[j] = True

            # 如果找到至少一张相似或重复图片，则创建分组
            if len(current_group_indices) > 1:
                duplicate_files = []
                for idx in current_group_indices:
                    item = self.image_data[idx]
                    duplicate_files.append(DuplicateFile(
                        file_name=item["info"].file_name,
                        file_path=item["info"].file_path,
                        file_md5=item["info"].file_md5,
                        extra_info={
                            "hash": str(item["hash"]),
                            "match_type": "exact_md5" if is_exact_md5_match else "phash_similarity"
                        }
                    ))

                results.append(DuplicateGroup(
                    group_id=f"img_sim_{len(results) + 1}",
                    checker_type="image_similarity",
                    files=duplicate_files
                ))

        LogUtils.info(f"ImageChecker 完成查重，发现 {len(results)} 组重复/相似图片。")
        return results

    def is_supported(self, file_extension: str) -> bool:
        """
        用途：判断该检查器是否支持处理指定的后缀名。
        入参说明：
            file_extension (str): 文件后缀名（如 '.jpg'）。
        返回值说明：
            bool: 支持返回 True，否则返回 False。
        """
        return file_extension.lower() in self.IMAGE_EXTENSIONS
