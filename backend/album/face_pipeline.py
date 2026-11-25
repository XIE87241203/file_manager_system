"""人脸识别流水线版本与模型路径常量。"""

# 模型或处理逻辑变化时递增版本，已处理图片会重新进入增量队列
PIPELINE_VERSION: str = 'yunet_2023mar_sface_2021dec_v1'

# 单批读取的图片数量，避免将整个相册加载到内存
BATCH_SIZE: int = 200

# 检测前缩放图片的最大边长，兼顾双核 CPU 速度与人脸召回率
DETECTION_MAX_EDGE: int = 960

# YuNet 检测阈值与 NMS 阈值
DETECTION_SCORE_THRESHOLD: float = 0.6
DETECTION_NMS_THRESHOLD: float = 0.3
