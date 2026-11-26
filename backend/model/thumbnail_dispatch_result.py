from dataclasses import dataclass


@dataclass
class ThumbnailDispatchResult:
    """
    用途说明：手动扫描缺少缩略图的媒体并派发任务后的返回结果。
    字段说明：scanned_count 为扫描到的缺失媒体数量；enqueued_count 为实际新加入队列的任务数量。
    """
    scanned_count: int = 0
    enqueued_count: int = 0
