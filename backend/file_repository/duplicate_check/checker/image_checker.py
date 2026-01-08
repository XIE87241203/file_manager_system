import os
from PIL import Image
import imagehash
from typing import List, Set
from dataclasses import dataclass # 添加dataclass导入
from backend.file_repository.duplicate_check.checker.base_checker import BaseDuplicateChecker
from backend.db.file_index_processor import FileIndexDBModel
from backend.common.log_utils import LogUtils
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModule


@dataclass
class ImageData:
    """
    用途：存储图片文件处理所需的数据，包括文件索引和感知哈希值。
    """
    info: FileIndexDBModel
    hash: imagehash.ImageHash

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
        self.image_data: List[ImageData] = [] # 修改为List[ImageData]

    def add_file(self, file_info: FileIndexDBModel) -> None:
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
                    self.image_data.append(ImageData(info=file_info, hash=hash_val)) # 修改为ImageData对象
            except Exception as e:
                LogUtils.error(f"ImageChecker 处理图片失败: {file_path}, 错误: {str(e)}")

    def get_results(self) -> List[DuplicateGroupDBModule]:
        """
        用途：综合 MD5 和汉明距离进行查重分组。
              首先通过 MD5 值判断是否存在完全相同的文件，然后对 MD5 不同的文件，
              通过计算感知哈希（pHash）的汉明距离来识别内容相似的图片。
        入参说明：无
        返回值说明：
            List[DuplicateGroupDBModule]: 包含重复或相似图片的文件分组列表。
                                  每个 DuplicateGroupDBModule 对象包含一个组的名称和所有重复/相似的 FileIndex 对象。
        """
        results: List[DuplicateGroupDBModule] = []
        num_images = len(self.image_data)
        if num_images == 0:
            LogUtils.info("ImageChecker 没有图片数据需要处理，返回空结果。")
            return results

        # visited 列表用于标记哪些图片已经被分配到某个重复组中，避免重复处理
        visited = [False] * num_images

        # 遍历所有图片数据，尝试为每个未访问的图片寻找其重复或相似项
        for i in range(num_images):
            if visited[i]:
                # 如果当前图片已经被处理过（即已在某个分组中），则跳过
                continue

            # 为当前图片初始化一个潜在的重复组，并将其标记为已访问
            current_group_indices = [i]
            visited[i] = True
            
            # 用于标记当前组是否因为发现了 MD5 完全一致的文件而形成
            # is_exact_md5_match: bool = False # 此变量在此方法中未使用，可以移除

            # 遍历当前图片之后的所有未访问图片，进行比较
            for j in range(i + 1, num_images):
                if visited[j]:
                    # 如果后续图片已被处理，则跳过
                    continue

                # 1. 优先判断 MD5 值是否完全相同。MD5 相同意味着文件内容完全一致。
                # 确保 file_md5 存在，并且两者 MD5 值相同
                if self.image_data[i].info.file_md5 and \
                   self.image_data[i].info.file_md5 == self.image_data[j].info.file_md5:
                    current_group_indices.append(j)
                    visited[j] = True
                    # is_exact_md5_match = True # 此变量在此方法中未使用，可以移除
                    continue # MD5 相同，无需再计算汉明距离，直接处理下一张图片

                # 2. 如果 MD5 值不同，则计算感知哈希（pHash）的汉明距离。
                # 汉明距离衡量两个哈希值之间对应位不同的数量，可用于判断图片相似度。
                # 距离越小，图片越相似。
                distance = self.image_data[i].hash - self.image_data[j].hash
                if distance <= self.threshold:
                    # 如果汉明距离小于或等于设定的阈值，则认为这两张图片是相似的
                    current_group_indices.append(j)
                    visited[j] = True

            # 如果当前分组中包含多于一张图片（即找到了重复或相似的图片），则将其添加至结果列表
            if len(current_group_indices) > 1:
                duplicate_files: List[int] = []
                for idx in current_group_indices:
                    # 从 image_data 中提取 FileIndex 对象，用于创建 DuplicateGroupDBModule
                    item = self.image_data[idx]
                    duplicate_files.append(item.info.id)

                results.append(DuplicateGroupDBModule(
                    group_name=f"img_sim_{len(results) + 1}", # 动态生成组名称
                    file_ids=duplicate_files
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
