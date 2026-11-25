from dataclasses import dataclass
from typing import Optional


@dataclass
class FaceQueueItemDBModel:
    """
    用途：持久化人脸识别队列中的单张图片，file_path 唯一以保证重复入队不会产生多个任务。
    """
    id: Optional[int] = None
    file_path: str = ''
    file_md5: str = ''
    queued_at: Optional[str] = None
