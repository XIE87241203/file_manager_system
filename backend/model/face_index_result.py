from dataclasses import dataclass


@dataclass
class FaceIndexSummaryResult:
    """
    用途说明：当前仓库的人脸索引统计结果。
    字段说明：
        total: 当前相册中待纳入人脸索引的图片总数。
        pending: 尚未按当前流水线成功处理的图片数量。
        queued: 已加入持久化队列、尚未处理完成的图片数量。
        faces: 当前已保存的人脸特征总数。
    """
    total: int = 0
    pending: int = 0
    queued: int = 0
    faces: int = 0


@dataclass
class FaceTaskStatusResult:
    """
    用途说明：人脸识别任务状态接口的返回结构。
    字段说明：
        status: idle、processing、paused、completed、stopped 或 error。
        running: 是否有人脸识别任务线程正在运行；暂停时仍为 True。
        paused: 任务是否处于暂停状态。
        repo_id: 当前请求的仓库 ID。
        active_repo_id: 正在运行的仓库 ID，空闲时为 None。
        total: 当前任务纳入的图片总数；空闲时为当前仓库图片总数。
        completed: 当前任务已尝试处理的图片数；空闲时为已处理图片数。
        pending: 当前仓库尚未按当前流水线处理的图片数量。
        remaining: 当前队列剩余数量，兼容旧界面字段。
        queued: 当前仓库持久化队列中的图片数量。
        faces: 当前仓库已保存的人脸特征总数。
        failed: 当前任务处理失败的图片数。
        message: 当前状态的中文或英文提示。
    """
    status: str = 'idle'
    running: bool = False
    paused: bool = False
    repo_id: int = 1
    active_repo_id: int | None = None
    total: int = 0
    completed: int = 0
    pending: int = 0
    remaining: int = 0
    queued: int = 0
    faces: int = 0
    failed: int = 0
    message: str = ''
