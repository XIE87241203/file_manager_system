from typing import List, Optional

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.image_feature_db_model import ImageFeatureDBModel


class ImageFeatureProcessor(BaseDBProcessor):
    """
    用途：图片特征数据库处理器，负责 image_features 表的相关操作（缓存图片感知哈希，避免重复计算）
    """

    def add_or_update_feature(self, features: ImageFeatureDBModel) -> bool:
        """
        用途说明：添加或更新图片特征信息。
        入参说明：features (ImageFeatureDBModel): 图片特征对象。
        返回值说明：bool: 是否成功。
        """
        query: str = f"""
            INSERT INTO {DBConstants.ImageFeature.TABLE_NAME} (
                {DBConstants.ImageFeature.COL_FILE_MD5},
                {DBConstants.ImageFeature.COL_IMAGE_HASH}
            )
            VALUES (?, ?)
            ON CONFLICT({DBConstants.ImageFeature.COL_FILE_MD5}) DO UPDATE SET
                {DBConstants.ImageFeature.COL_IMAGE_HASH} = EXCLUDED.{DBConstants.ImageFeature.COL_IMAGE_HASH}
        """
        params: tuple = (features.file_md5, features.image_hash)
        result: int = self._execute(query, params)
        return result is not None and result > 0

    def get_feature_by_md5(self, file_md5: str) -> Optional[ImageFeatureDBModel]:
        """
        用途说明：根据 MD5 获取图片特征信息。
        入参说明：file_md5 (str): 文件的 MD5 值。
        返回值说明：Optional[ImageFeatureDBModel]: 图片特征对象，若不存在则返回 None。
        """
        query: str = f"SELECT * FROM {DBConstants.ImageFeature.TABLE_NAME} WHERE {DBConstants.ImageFeature.COL_FILE_MD5} = ?"
        row: Optional[dict] = self._execute(query, (file_md5,), is_query=True, fetch_one=True)
        if row:
            return ImageFeatureDBModel(**row)
        return None

    def get_features_by_md5s(self, file_md5s: List[str]) -> List[ImageFeatureDBModel]:
        """
        用途说明：根据 MD5 列表批量获取图片特征信息（单次连接查询，避免逐条查询的连接开销）。
        入参说明：file_md5s (List[str]): 文件 MD5 值列表，调用方应控制单批数量（建议 <= 500）。
        返回值说明：List[ImageFeatureDBModel]: 命中的图片特征对象列表，未命中的 MD5 不返回。
        """
        if not file_md5s:
            return []
        placeholders: str = ','.join(['?'] * len(file_md5s))
        query: str = (
            f"SELECT * FROM {DBConstants.ImageFeature.TABLE_NAME} "
            f"WHERE {DBConstants.ImageFeature.COL_FILE_MD5} IN ({placeholders})"
        )
        rows: List[dict] = self._execute(query, tuple(file_md5s), is_query=True)
        return [ImageFeatureDBModel(**row) for row in rows]

    def add_or_update_features_batch(self, features: List[ImageFeatureDBModel]) -> bool:
        """
        用途说明：批量添加或更新图片特征信息（单事务提交，避免逐条写入的连接与提交开销）。
        入参说明：features (List[ImageFeatureDBModel]): 图片特征对象列表，调用方应控制单批数量（建议 <= 500）。
        返回值说明：bool: 是否成功。
        """
        if not features:
            return True
        query: str = f"""
            INSERT INTO {DBConstants.ImageFeature.TABLE_NAME} (
                {DBConstants.ImageFeature.COL_FILE_MD5},
                {DBConstants.ImageFeature.COL_IMAGE_HASH}
            )
            VALUES (?, ?)
            ON CONFLICT({DBConstants.ImageFeature.COL_FILE_MD5}) DO UPDATE SET
                {DBConstants.ImageFeature.COL_IMAGE_HASH} = EXCLUDED.{DBConstants.ImageFeature.COL_IMAGE_HASH}
        """
        data: List[tuple] = [(f.file_md5, f.image_hash) for f in features]
        result: int = self._execute_batch(query, data)
        return result is not None and result >= 0

    @staticmethod
    def clear_image_features() -> bool:
        """
        用途说明：清空图片特征表。
        入参说明：无
        返回值说明：bool: 是否成功。
        """
        return BaseDBProcessor._clear_table(DBConstants.ImageFeature.TABLE_NAME)