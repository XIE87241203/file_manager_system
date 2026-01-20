from dataclasses import dataclass

from backend.db.db_constants import DBConstants
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.video_feature_db_model import VideoFeatureDBModel


@dataclass
class VideoFileInfoResult:
    """
    用途：视频文件信息数据类，用于组合文件基础索引信息、视频特征信息以及相似度信息。
    
    属性说明:
    - file_index (FileIndexDBModel): 文件基础索引信息。
    - video_feature (VideoFeatureDBModel): 视频特征信息。
    - similarity_type (str): 相似类型（MD5, VIDEO_FEATURE 等）。
    - similarity_rate (float): 相似率，进组时相对于代表视频的相似度（1.0 表示完全相同或作为代表）。
    """
    file_index: FileIndexDBModel
    video_feature: VideoFeatureDBModel
    similarity_type: str = DBConstants.SimilarityType.VIDEO_FEATURE
    similarity_rate: float = 1.0
