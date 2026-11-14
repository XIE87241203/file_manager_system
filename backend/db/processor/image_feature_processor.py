from typing import Optional

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

    @staticmethod
    def clear_image_features() -> bool:
        """
        用途说明：清空图片特征表。
        入参说明：无
        返回值说明：bool: 是否成功。
        """
        return BaseDBProcessor._clear_table(DBConstants.ImageFeature.TABLE_NAME)