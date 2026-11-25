from pathlib import Path
from types import TracebackType
from typing import Any, List, Optional, Type

import cv2
import numpy as np

from backend.album.face_pipeline import (
    DETECTION_MAX_EDGE,
    DETECTION_NMS_THRESHOLD,
    DETECTION_SCORE_THRESHOLD,
    PIPELINE_VERSION
)
from backend.common.i18n_utils import t
from backend.model.db.face_embedding_db_model import FaceEmbeddingDBModel


class FaceRecognitionEngine:
    """
    用途说明：封装 OpenCV YuNet 人脸检测与 SFace 特征提取，仅由单个人脸任务线程调用。
    资源说明：进入上下文时加载模型并临时将 OpenCV 推理线程限制为 1，退出时释放模型并恢复线程数。
    """

    def __init__(self) -> None:
        """
        用途说明：加载随项目分发的 YuNet 与 SFace ONNX 模型。
        入参说明：无
        返回值说明：无；模型缺失或 OpenCV 不支持时抛出异常，由任务层记录并转为错误状态。
        """
        model_dir: Path = Path(__file__).with_name('models')
        detector_path: Path = model_dir / 'face_detection_yunet_2023mar.onnx'
        recognizer_path: Path = model_dir / 'face_recognition_sface_2021dec.onnx'
        for model_path in (detector_path, recognizer_path):
            if not model_path.is_file():
                raise FileNotFoundError(t('face_model_missing', path=str(model_path)))

        self._previous_num_threads: int = cv2.getNumThreads()
        cv2.setNumThreads(1)
        try:
            self._detector: Optional[cv2.FaceDetectorYN] = cv2.FaceDetectorYN.create(
                str(detector_path),
                '',
                (320, 320),
                DETECTION_SCORE_THRESHOLD,
                DETECTION_NMS_THRESHOLD,
                5000,
                cv2.dnn.DNN_BACKEND_OPENCV,
                cv2.dnn.DNN_TARGET_CPU
            )
            self._recognizer: Optional[cv2.FaceRecognizerSF] = cv2.FaceRecognizerSF.create(
                str(recognizer_path),
                ''
            )
        except Exception:
            self._detector = None
            self._recognizer = None
            cv2.setNumThreads(self._previous_num_threads)
            raise

    def __enter__(self) -> 'FaceRecognitionEngine':
        """用途说明：返回已加载模型的引擎；入参说明：无；返回值说明：FaceRecognitionEngine 实例。"""
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> bool:
        """用途说明：释放模型并恢复 OpenCV 线程数；入参说明：异常上下文；返回值说明：False，不吞掉异常。"""
        self.close()
        return False

    def close(self) -> None:
        """
        用途说明：释放 YuNet 与 SFace 模型，并恢复进入引擎前的 OpenCV 线程数。
        入参说明：无
        返回值说明：无
        """
        self._detector = None
        self._recognizer = None
        cv2.setNumThreads(self._previous_num_threads)

    def recognize(self, file_path: str, file_md5: str) -> List[FaceEmbeddingDBModel]:
        """
        用途说明：识别单张图片中的全部人脸，返回一人一条的 128 维 SFace 特征。
        入参说明：
            file_path (str): 图片完整路径，支持 Windows 中文路径。
            file_md5 (str): 文件索引中的内容标识。
        返回值说明：List[FaceEmbeddingDBModel] - 人脸框、置信度、特征和流水线版本列表；无脸时为空列表。
        """
        if self._detector is None or self._recognizer is None:
            raise RuntimeError(t('face_engine_not_ready'))

        image_buffer: np.ndarray = np.fromfile(file_path, dtype=np.uint8)
        image: Optional[np.ndarray] = cv2.imdecode(image_buffer, cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise ValueError(t('face_image_decode_failed', path=file_path))

        height: int = int(image.shape[0])
        width: int = int(image.shape[1])
        scale: float = min(1.0, DETECTION_MAX_EDGE / float(max(width, height)))
        if scale < 1.0:
            detection_image: np.ndarray = cv2.resize(
                image,
                (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                interpolation=cv2.INTER_AREA
            )
        else:
            detection_image = image

        detection_height: int = int(detection_image.shape[0])
        detection_width: int = int(detection_image.shape[1])
        self._detector.setInputSize((detection_width, detection_height))
        detection_result: Any = self._detector.detect(detection_image)
        detections: Optional[np.ndarray]
        if isinstance(detection_result, tuple):
            detections = detection_result[1] if len(detection_result) > 1 else None
        else:
            detections = detection_result
        if detections is None or len(detections) == 0:
            return []

        faces: List[FaceEmbeddingDBModel] = []
        inverse_scale: float = 1.0 / scale
        for face_index, row in enumerate(detections):
            values: np.ndarray = np.asarray(row, dtype=np.float32).reshape(-1)
            bbox_x: float = float(values[0]) * inverse_scale
            bbox_y: float = float(values[1]) * inverse_scale
            bbox_width: float = float(values[2]) * inverse_scale
            bbox_height: float = float(values[3]) * inverse_scale
            landmarks: np.ndarray = values[4:14].reshape(5, 2).copy() * inverse_scale

            # 保存给后续人物匹配的框坐标始终相对于原图，检测缩放不会改变索引语义
            bbox_x = max(0.0, min(bbox_x, float(max(0, width - 1))))
            bbox_y = max(0.0, min(bbox_y, float(max(0, height - 1))))
            bbox_width = max(1.0, min(bbox_width, float(width) - bbox_x))
            bbox_height = max(1.0, min(bbox_height, float(height) - bbox_y))

            aligned_face: np.ndarray = self._recognizer.alignCrop(image, landmarks)
            feature: Optional[np.ndarray] = self._recognizer.feature(aligned_face)
            if feature is None:
                raise RuntimeError(t('face_feature_extract_failed', path=file_path))
            embedding: np.ndarray = np.asarray(feature, dtype=np.float32).reshape(-1)
            if embedding.size != 128:
                raise RuntimeError(t('face_feature_dimension_invalid', size=embedding.size))

            faces.append(FaceEmbeddingDBModel(
                file_path=file_path,
                file_md5=file_md5,
                face_index=face_index,
                bbox_x=bbox_x,
                bbox_y=bbox_y,
                bbox_width=bbox_width,
                bbox_height=bbox_height,
                confidence=float(values[14]),
                embedding=embedding.tobytes(),
                pipeline_version=PIPELINE_VERSION
            ))
        return faces
