from dataclasses import dataclass
from typing import Optional


@dataclass
class FaceFileIndexStateDBModel:
    """
    用途说明：记录单张图片的人脸处理状态；没有检测到人脸时同样写入，避免重复扫描。
    字段说明：
        file_path: 文件索引中的完整路径，重建索引后仍可稳定关联。
        file_md5: 处理时的文件内容标识，文件内容变化后重新识别。
        pipeline_version: 本次识别使用的模型与处理流水线版本。
        face_count: 该图片识别出的人脸数量。
        processed_at: 完成处理的时间。
    """
    id: Optional[int] = None
    file_path: str = ''
    file_md5: str = ''
    pipeline_version: str = ''
    face_count: int = 0
    processed_at: Optional[str] = None
