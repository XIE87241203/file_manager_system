from dataclasses import dataclass
from typing import Dict, List, Optional

import imagehash
import numpy as np
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


# 字节级 popcount 查找表（0-255 每个字节值对应的二进制 1 的个数），
# 用于向量化统计汉明距离，避免逐对调用 imagehash 的减法运算
_POPCOUNT_TABLE: np.ndarray = np.array([bin(v).count('1') for v in range(256)], dtype=np.uint8)


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
        # 特征缓存：MD5 -> 感知哈希十六进制字符串（None 表示特征库中不存在），避免逐文件查库
        self._feature_cache: Dict[str, Optional[str]] = {}
        # 待写回特征库的新计算特征（攒批提交，减少连接与事务开销）
        self._pending_features: List[ImageFeatureDBModel] = []
        # 批量预取/写回的单批大小
        self._batch_size: int = 500

    def preload_features(self, file_infos: List[FileIndexDBModel]) -> None:
        """
        用途：按批预取图片感知哈希特征到内存缓存（单次连接查询一批 MD5），
        供 add_file 直接命中，消除逐文件新建数据库连接的开销。
        入参说明：
            file_infos (List[FileIndexDBModel]): 本批待录入的文件索引列表（可含非图片，内部自动过滤）。
        返回值说明：无
        """
        # 1. 收集本批中尚未缓存的图片 MD5（去重）
        pending_md5s: List[str] = []
        seen: set = set()
        for file_info in file_infos:
            md5: str = file_info.file_md5
            if md5 and md5 not in self._feature_cache and md5 not in seen \
                    and self.is_supported(file_info.file_path):
                seen.add(md5)
                pending_md5s.append(md5)

        # 2. 分批查询特征库并写入缓存（未命中的 MD5 记为 None，避免重复查库）
        for start in range(0, len(pending_md5s), self._batch_size):
            chunk: List[str] = pending_md5s[start:start + self._batch_size]
            features: List[ImageFeatureDBModel] = DBOperations.get_image_features_by_md5s(chunk)
            found_map: Dict[str, str] = {f.file_md5: f.image_hash for f in features}
            for md5 in chunk:
                self._feature_cache[md5] = found_map.get(md5)

    def flush_pending_features(self) -> None:
        """
        用途：将攒批的新计算特征批量写回特征库（单事务提交）。
        在攒批达到阈值时自动调用，报告生成前也会强制调用以保证特征持久化。
        入参说明：无
        返回值说明：无
        """
        if not self._pending_features:
            return
        for start in range(0, len(self._pending_features), self._batch_size):
            chunk: List[ImageFeatureDBModel] = self._pending_features[start:start + self._batch_size]
            DBOperations.add_image_features_batch(chunk)
        self._pending_features.clear()

    def add_file(self, file_info: FileIndexDBModel) -> None:
        """
        用途：录入一个图片文件，优先复用内存缓存/特征库的感知哈希（pHash），
        未命中时实时计算并攒批写回缓存。
        入参说明：
            file_info (FileIndexDBModel): 文件索引对象。
        返回值说明：无
        """
        file_path: str = file_info.file_path
        if not self.is_supported(file_path):
            return

        md5: str = file_info.file_md5
        hash_val: Optional[imagehash.ImageHash] = None

        # 1. 优先从内存缓存读取（preload_features 已批量预取）；未预取时回退单条查询
        if md5:
            if md5 not in self._feature_cache:
                cached: Optional[ImageFeatureDBModel] = DBOperations.get_image_feature_by_md5(md5)
                self._feature_cache[md5] = cached.image_hash if cached else None
            cached_hex: Optional[str] = self._feature_cache[md5]
            if cached_hex:
                try:
                    hash_val = imagehash.hex_to_hash(cached_hex)
                except Exception:
                    hash_val = None

        # 2. 未命中则实时计算并攒批持久化
        if hash_val is None:
            try:
                with Image.open(file_path) as img:
                    hash_val = imagehash.phash(img)
            except Exception as e:
                LogUtils.error(t('dup_image_checker_failed', path=file_path, error=str(e)))
                return
            if md5:
                hash_hex: str = str(hash_val)
                self._feature_cache[md5] = hash_hex
                self._pending_features.append(ImageFeatureDBModel(file_md5=md5, image_hash=hash_hex))
                if len(self._pending_features) >= self._batch_size:
                    self.flush_pending_features()

        self.image_data.append(ImageData(info=file_info, hash=hash_val))

    def get_results(self) -> List[DuplicateGroupDBModel]:
        """
        用途：综合 MD5 和汉明距离进行查重分组，并记录每个文件的相似类型和相似率。
        性能说明：采用 numpy 向量化批量计算汉明距离（uint64 打包 + 异或 +  popcount 查表），
        避免逐对 Python 循环在海量图片（数万张）时产生 O(n²) 次 numpy 调用导致报告生成阶段长时间无响应。
        分组语义与逐对遍历版本完全一致：按录入顺序取未分组图片作为组代表，
        其后未分组图片若 MD5 相同或汉明距离 <= 阈值则并入该组。
        返回值说明：
            List[DuplicateGroupDBModel]: 重复/相似图片分组列表。
        """
        results: List[DuplicateGroupDBModel] = []
        num_images: int = len(self.image_data)
        if num_images == 0:
            return results

        # 报告生成前将攒批的新特征强制写回特征库，保证持久化
        self.flush_pending_features()

        LogUtils.info(t('dup_image_report_start', count=num_images))

        # 1. 预处理：将 64 位 pHash 打包为 uint64，便于向量化异或运算
        packed_hashes: np.ndarray = np.empty(num_images, dtype=np.uint64)
        # MD5 映射为整数码（0 保留给空 MD5，空 MD5 之间不允许互相匹配）
        md5_codes: np.ndarray = np.zeros(num_images, dtype=np.int64)
        md5_code_map: Dict[str, int] = {}
        for idx, image_data in enumerate(self.image_data):
            hash_bits: np.ndarray = np.asarray(image_data.hash.hash, dtype=bool).flatten()
            packed_hashes[idx] = np.packbits(hash_bits).view(np.uint64)[0]
            md5: str = image_data.info.file_md5
            if md5:
                if md5 not in md5_code_map:
                    md5_code_map[md5] = len(md5_code_map) + 1
                md5_codes[idx] = md5_code_map[md5]

        # 2. 贪心分组：visited 标记已入组图片，逐个代表向量化比对剩余候选
        visited: np.ndarray = np.zeros(num_images, dtype=bool)
        # 日志节流：每处理 2000 个组代表输出一次进度，便于观察报告生成进展
        log_interval: int = 2000
        processed_representatives: int = 0

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
            processed_representatives += 1
            if processed_representatives % log_interval == 0:
                LogUtils.info(t('dup_image_report_progress', current=i + 1, total=num_images))

            # 无剩余候选时直接收尾
            if i + 1 >= num_images:
                if len(current_group_files) > 1:
                    results.append(DuplicateGroupDBModel(
                        group_name=f"img_sim_{len(results) + 1}",
                        files=current_group_files
                    ))
                continue

            # 3. 向量化计算代表 i 与所有后续图片的汉明距离（异或后按字节查表统计 1 的个数）
            tail_hashes: np.ndarray = packed_hashes[i + 1:]
            xor_bytes: np.ndarray = np.bitwise_xor(tail_hashes, packed_hashes[i]).view(np.uint8).reshape(-1, 8)
            distances: np.ndarray = _POPCOUNT_TABLE[xor_bytes].sum(axis=1)

            # 4. MD5 匹配掩码（空 MD5 不参与匹配）
            md5_matched: np.ndarray = (md5_codes[i + 1:] == md5_codes[i]) & (md5_codes[i] != 0)

            # 5. 合并匹配结果：未分组 且 (MD5 相同 或 汉明距离 <= 阈值)，按原始下标升序入组
            match_mask: np.ndarray = (~visited[i + 1:]) & (md5_matched | (distances <= self.threshold))
            for offset in np.nonzero(match_mask)[0]:
                j: int = i + 1 + int(offset)
                visited[j] = True
                if md5_matched[offset]:
                    # MD5 完全一致
                    current_group_files.append(DuplicateFileDBModel(
                        file_path=self.image_data[j].info.file_path,
                        similarity_type=SimilarityType.MD5,
                        similarity_rate=1.0
                    ))
                else:
                    # 汉明距离匹配（相似图片），pHash 为 64 位，最大距离 64
                    similarity_rate: float = 1.0 - (int(distances[offset]) / 64.0)
                    current_group_files.append(DuplicateFileDBModel(
                        file_path=self.image_data[j].info.file_path,
                        similarity_type=SimilarityType.HASH,
                        similarity_rate=similarity_rate
                    ))

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
