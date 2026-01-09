from typing import Optional

from backend.db.db_constants import DBConstants
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.video_feature_db_model import VideoFeatureDBModel


class VideoFeatureProcessor(BaseDBProcessor):
    """
    用途：视频特征数据库处理器，负责 video_features 表的相关操作
    """

    def add_or_update_feature(self, features: VideoFeatureDBModel) -> bool:
        """
        用途：添加或更新视频特征信息
        入参说明：
            features (VideoFeatureDBModel): 视频特征对象
        返回值说明：
            bool: 是否成功
        """
        query: str = f"""
            INSERT INTO {DBConstants.VideoFeature.TABLE_NAME} (
                {DBConstants.VideoFeature.COL_FILE_MD5}, 
                {DBConstants.VideoFeature.COL_VIDEO_HASHES}, 
                {DBConstants.VideoFeature.COL_DURATION}
            )
            VALUES (?, ?, ?)
            ON CONFLICT({DBConstants.VideoFeature.COL_FILE_MD5}) DO UPDATE SET
                {DBConstants.VideoFeature.COL_VIDEO_HASHES} = EXCLUDED.{DBConstants.VideoFeature.COL_VIDEO_HASHES},
                {DBConstants.VideoFeature.COL_DURATION} = EXCLUDED.{DBConstants.VideoFeature.COL_DURATION}
        """
        params: tuple = (features.file_md5, features.video_hashes, features.duration)
        result: int = self._execute(query, params)
        return result is not None and result > 0

    def get_feature_by_md5(self, file_md5: str) -> Optional[VideoFeatureDBModel]:
        """
        用途：根据 MD5 获取视频特征信息
        入参说明：
            file_md5 (str): 文件的 MD5 值
        返回值说明：
            Optional[VideoFeatureDBModel]: 视频特征对象，若不存在则返回 None
        """
        query: str = f"SELECT * FROM {DBConstants.VideoFeature.TABLE_NAME} WHERE {DBConstants.VideoFeature.COL_FILE_MD5} = ?"
        row: Optional[dict] = self._execute(query, (file_md5,), is_query=True, fetch_one=True)
        if row:
            return VideoFeatureDBModel(**row)
        return None

    @staticmethod
    def clear_video_features() -> bool:
        """
        用途：清空视频特征表
        入参说明：无
        返回值说明：
            bool: 是否成功
        """
        return BaseDBProcessor._clear_table(DBConstants.VideoFeature.TABLE_NAME)
