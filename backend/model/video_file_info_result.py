from dataclasses import dataclass

from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.video_feature_db_model import VideoFeatureDBModel


@dataclass
class VideoFileInfoResult:
    """
    用途：视频文件信息数据类，用于组合文件基础索引信息和视频特征信息。
    
    属性说明:
    - file_index (FileIndex): 文件基础索引信息，包含路径、MD5、大小等。
    - video_feature (VideoFeature): 视频特征信息，包含指纹、时长等。
    """
    file_index: FileIndexDBModel
    video_feature: VideoFeatureDBModel
