from dataclasses import dataclass
from typing import Optional


@dataclass
class FaceEmbeddingDBModel:
    """
    用途说明：保存一张图片中的单张人脸；同一图片的多人通过 face_index 区分，互不覆盖。
    字段说明：
        file_path: 所属文件索引路径。
        file_md5: 识别时的文件内容标识。
        face_index: 该人脸在图片检测结果中的序号，从 0 开始。
        bbox_*: 相对于原图像素尺寸的人脸框位置与宽高。
        confidence: YuNet 检测置信度。
        embedding: SFace 输出的 float32 特征 BLOB，标准维度为 128。
        pipeline_version: 特征提取使用的模型与处理流水线版本。
        created_at: 记录写入时间。
    """
    id: Optional[int] = None
    file_path: str = ''
    file_md5: str = ''
    face_index: int = 0
    bbox_x: float = 0.0
    bbox_y: float = 0.0
    bbox_width: float = 0.0
    bbox_height: float = 0.0
    confidence: float = 0.0
    embedding: bytes = b''
    pipeline_version: str = ''
    created_at: Optional[str] = None
