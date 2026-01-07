import os
import cv2
import hashlib
import threading
from collections import deque
from typing import List, Optional, Tuple, Set, Deque
from PIL import Image

from backend.common.utils import Utils
from backend.common.log_utils import LogUtils
from backend.common.thread_pool import ThreadPoolManager
from backend.db.db_operations import DBOperations
from backend.setting.setting_service import settingService

class ThumbnailGenerator:
    """
    用途：缩略图生成器类，采用单例模式。
    设计说明：
        - 使用 collections.deque 保证 O(1) 的任务弹出效率。
        - 使用 set 保证 O(1) 的任务去重查找效率。
        - 结合两者确保任务按先进先出顺序处理且不重复入队。
    """
    _instance = None
    _lock = threading.Lock()
    _queue: Deque[str] = deque()  # 任务队列，保证 FIFO 顺序
    _queue_set: Set[str] = set()    # 去重集合，保证入队原子性和唯一性
    _is_processing: bool = False
    _THUMBNAIL_DIR = os.path.join(Utils.get_runtime_path(), "cache", "thumbnail")

    def __new__(cls) -> 'ThumbnailGenerator':
        """
        用途：实现单例模式，确保全局只有一个生成器实例。
        入参说明：无。
        返回值说明：ThumbnailGenerator - 生成器单例实例。
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ThumbnailGenerator, cls).__new__(cls)
                if not os.path.exists(cls._THUMBNAIL_DIR):
                    os.makedirs(cls._THUMBNAIL_DIR, exist_ok=True)
            return cls._instance

    def add_tasks(self, file_paths: List[str]) -> None:
        """
        用途：向待处理队列中原子性地添加任务并启动生成工作。
        入参说明：
            file_paths (List[str]): 待处理的文件绝对路径列表。
        返回值说明：无。
        """
        with self._lock:
            added_count = 0
            for path in file_paths:
                if path not in self._queue_set:
                    self._queue.append(path)
                    self._queue_set.add(path)
                    added_count += 1
            
            if added_count > 0:
                LogUtils.info(f"缩略图队列已添加 {added_count} 个新任务，当前等待中: {len(self._queue)}")
            
            if not self._is_processing and self._queue:
                self._is_processing = True
                ThreadPoolManager.submit(self._worker)

    def get_remaining_count(self) -> int:
        """
        用途：原子性地获取队列中剩余未处理的任务数量。
        入参说明：无。
        返回值说明：int - 剩余任务数。
        """
        with self._lock:
            return len(self._queue)

    def clear_queue(self) -> None:
        """
        用途：原子性地清空待处理队列和去重集合，停止后续任务。
        入参说明：无。
        返回值说明：无。
        """
        with self._lock:
            self._queue.clear()
            self._queue_set.clear()
            LogUtils.info("缩略图生成队列及去重集合已清空")

    def _worker(self) -> None:
        """
        用途：工作循环。从队列提取任务并在锁外执行耗时生成逻辑，避免阻塞主线程或产生死锁。
        入参说明：无。
        返回值说明：无。
        """
        file_path: Optional[str] = None
        
        # 1. 提取任务（临界区：轻量级操作）
        with self._lock:
            if not self._queue:
                self._is_processing = False
                self._queue_set.clear() # 任务清空时同步重置集合
                LogUtils.info("缩略图生成队列处理完毕")
                return
            
            file_path = self._queue.popleft()
            if file_path in self._queue_set:
                self._queue_set.remove(file_path)

        # 2. 锁外执行耗时任务（磁盘IO与图像处理，预防死锁）
        if file_path:
            try:
                thumb_size = settingService.get_config().file_repository.thumbnail_size
                actual_path, thumb_path = self._generate_single_thumbnail(file_path, thumb_size)
                if thumb_path:
                    DBOperations.update_thumbnail_path(actual_path, thumb_path)
            except Exception as e:
                LogUtils.error(f"处理缩略图失败: {file_path}, 错误: {e}")
        
        # 3. 异步提交下一次循环，实现非阻塞的串行处理
        ThreadPoolManager.submit(self._worker)

    def _generate_single_thumbnail(self, file_path: str, size: int) -> Tuple[str, Optional[str]]:
        """
        用途：为单个文件生成缩略图（支持常见图片和视频格式）。
        入参说明：
            file_path (str): 文件物理路径。
            size (int): 缩略图最大边长（保持纵横比）。
        返回值说明：
            Tuple[str, Optional[str]]: (原始文件路径, 缩略图生成后的物理路径或None)。
        """
        if not os.path.exists(file_path):
            return file_path, None

        ext = os.path.splitext(file_path)[1].lower()
        # 使用路径的 MD5 作为文件名确保唯一性且符合系统命名规范
        thumb_name = hashlib.md5(file_path.encode()).hexdigest() + ".jpg"
        thumb_path = os.path.join(self._THUMBNAIL_DIR, thumb_name)

        try:
            # 图片处理
            if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                with Image.open(file_path) as img:
                    img.thumbnail((size, size))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(thumb_path, "JPEG")
                return file_path, thumb_path
            
            # 视频处理 (通过 OpenCV 提取第一帧)
            elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.flv']:
                cap = cv2.VideoCapture(file_path)
                success, frame = cap.read()
                if success:
                    h, w = frame.shape[:2]
                    scale = size / max(h, w)
                    new_h, new_w = int(h * scale), int(w * scale)
                    resized = cv2.resize(frame, (new_w, new_h))
                    cv2.imwrite(thumb_path, resized)
                    cap.release()
                    return file_path, thumb_path
                cap.release()
        except Exception as e:
            LogUtils.error(f"文件生成缩略图异常: {file_path}, 错误: {e}")
        
        return file_path, None
