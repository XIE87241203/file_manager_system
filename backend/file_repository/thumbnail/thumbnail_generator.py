import os
import threading
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set, Deque

import cv2
from PIL import Image

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import get_current_repo_id, set_current_repo_id
from backend.common.thread_pool import ThreadPoolManager
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.thumbnail.thumbnail_path_utils import ThumbnailPathUtils
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.setting.setting_service import settingService


@dataclass
class ThumbnailTaskProgress:
    """
    用途说明：单个仓库的缩略图队列进度快照。
    字段说明：repo_id 为仓库 ID，total/completed/remaining 为总任务数、已完成数和剩余数，paused 为是否暂停。
    """
    repo_id: int
    total: int = 0
    completed: int = 0
    remaining: int = 0
    paused: bool = False


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
    _queue: Deque[Tuple[int, FileIndexDBModel]] = deque()  # 任务队列，存储 (仓库ID, 模型对象)
    _queue_set: Set[Tuple[int, str]] = set()    # 待处理任务去重集合，存储 (仓库ID, 文件路径)
    _processing_keys: Set[Tuple[int, str]] = set()  # 正在处理的任务去重集合，防止扫描时重复入队
    _is_processing: bool = False
    _active_repo_id: Optional[int] = None
    _paused_repos: Set[int] = set()
    _resume_events: Dict[int, threading.Event] = {}
    _total_by_repo: Dict[int, int] = {}
    _completed_by_repo: Dict[int, int] = {}
    _generation_by_repo: Dict[int, int] = {}  # 停止时递增，用于取消暂停等待中的已取出任务
    # 同步生成锁：相册按需生成缩略图时避免同一时刻重复写文件
    _generate_now_lock = threading.Lock()

    def __new__(cls) -> 'ThumbnailGenerator':
        """
        用途：实现单例模式，确保全局只有一个生成器实例。
        入参说明：无。
        返回值说明：ThumbnailGenerator - 生成器单例实例。
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ThumbnailGenerator, cls).__new__(cls)
                # 按最新配置创建缩略图目录（路径支持在相册设置中修改）
                ThumbnailPathUtils.ensure_thumbnail_dir()
            return cls._instance

    def add_tasks(self, tasks: List[FileIndexDBModel]) -> int:
        """
        用途：向待处理队列中原子性地添加任务并启动生成工作，待处理和处理中的同一路径均去重。
        入参说明：
            tasks (List[FileIndexDBModel]): 待处理的文件索引模型列表。
        返回值说明：int - 实际新加入队列的任务数量。
        """
        with self._lock:
            added_count: int = 0
            repo_id: int = get_current_repo_id()
            for task in tasks:
                key: Tuple[int, str] = (repo_id, task.file_path)
                if key not in self._queue_set and key not in self._processing_keys:
                    self._queue.append((repo_id, task))
                    self._queue_set.add(key)
                    self._total_by_repo[repo_id] = self._total_by_repo.get(repo_id, 0) + 1
                    added_count += 1

            if added_count > 0:
                LogUtils.info(t('thumb_gen_queue_added', added_count=added_count, remaining=len(self._queue)))

            if not self._is_processing and self._queue:
                self._is_processing = True
                ThreadPoolManager.submit(self._worker)
            return added_count

    def get_remaining_count(self) -> int:
        """
        用途：原子性地获取全部仓库中尚未完成的缩略图任务数量，包含正在处理的一项。
        入参说明：无。
        返回值说明：int - 剩余任务数。
        """
        with self._lock:
            return len(self._queue) + len(self._processing_keys)

    def get_repo_statuses(self) -> List[ThumbnailTaskProgress]:
        """
        用途说明：获取各仓库缩略图队列进度，供统一任务入口聚合。
        入参说明：无。
        返回值说明：List[ThumbnailTaskProgress] - 仍有任务或正在处理的任务快照。
        """
        with self._lock:
            remaining_by_repo: Dict[int, int] = {}
            for repo_id, _ in self._queue:
                remaining_by_repo[repo_id] = remaining_by_repo.get(repo_id, 0) + 1
            for repo_id, _ in self._processing_keys:
                remaining_by_repo[repo_id] = remaining_by_repo.get(repo_id, 0) + 1
            repo_ids: Set[int] = set(self._total_by_repo) | set(remaining_by_repo) | set(self._paused_repos)
            if self._active_repo_id is not None:
                repo_ids.add(self._active_repo_id)
            results: List[ThumbnailTaskProgress] = []
            for repo_id in sorted(repo_ids):
                total: int = self._total_by_repo.get(repo_id, 0)
                completed: int = self._completed_by_repo.get(repo_id, 0)
                remaining: int = remaining_by_repo.get(repo_id, 0)
                if total > completed or remaining > 0:
                    results.append(ThumbnailTaskProgress(repo_id=repo_id, total=total, completed=completed,
                                                         remaining=remaining, paused=repo_id in self._paused_repos))
            return results

    def pause_repo(self, repo_id: int) -> bool:
        """
        用途说明：暂停指定仓库的缩略图队列，当前图片处理完成或下一张图片取出后等待恢复。
        入参说明：repo_id (int) - 目标仓库 ID。
        返回值说明：bool - 仓库存在待处理任务时返回 True。
        """
        with self._lock:
            has_task: bool = repo_id == self._active_repo_id or any(item[0] == repo_id for item in self._queue)
            if not has_task:
                return False
            self._paused_repos.add(repo_id)
            self._resume_events.setdefault(repo_id, threading.Event()).clear()
        LogUtils.info(t('thumb_gen_repo_paused', repo_id=repo_id))
        return True

    def resume_repo(self, repo_id: int) -> bool:
        """
        用途说明：恢复指定仓库的缩略图队列。
        入参说明：repo_id (int) - 目标仓库 ID。
        返回值说明：bool - 已暂停并成功恢复时返回 True。
        """
        with self._lock:
            if repo_id not in self._paused_repos:
                return False
            self._paused_repos.discard(repo_id)
            self._resume_events.setdefault(repo_id, threading.Event()).set()
        LogUtils.info(t('thumb_gen_repo_resumed', repo_id=repo_id))
        return True

    def clear_queue(self, repo_id: Optional[int] = None) -> None:
        """
        用途说明：清空待处理缩略图任务；指定仓库时只清理该仓库，并解除其暂停状态。
        入参说明：repo_id (Optional[int]) - 目标仓库；为空时清空全部仓库。
        返回值说明：无。
        """
        with self._lock:
            target_ids: Set[int] = (set(self._total_by_repo) | set(self._generation_by_repo)
                                    | ({self._active_repo_id} if self._active_repo_id is not None else set()))
            if repo_id is None:
                self._queue.clear()
                self._queue_set.clear()
                self._processing_keys.clear()
                self._total_by_repo.clear()
                self._completed_by_repo.clear()
                self._paused_repos.clear()
                for target_id in target_ids:
                    self._generation_by_repo[target_id] = self._generation_by_repo.get(target_id, 0) + 1
                    self._resume_events.setdefault(target_id, threading.Event()).set()
            else:
                kept: Deque[Tuple[int, FileIndexDBModel]] = deque(
                    item for item in self._queue if item[0] != repo_id)
                self._queue = kept
                self._queue_set = {(item[0], item[1].file_path) for item in kept}
                self._processing_keys = {key for key in self._processing_keys if key[0] != repo_id}
                self._total_by_repo.pop(repo_id, None)
                self._completed_by_repo.pop(repo_id, None)
                self._paused_repos.discard(repo_id)
                self._generation_by_repo[repo_id] = self._generation_by_repo.get(repo_id, 0) + 1
                self._resume_events.setdefault(repo_id, threading.Event()).set()
            LogUtils.info(t('thumb_gen_queue_cleared'))

    @staticmethod
    def get_existing_thumbnail_path(file_md5: str) -> Optional[str]:
        """
        用途说明：根据文件 MD5 获取已存在的缩略图物理路径。缩略图以内容 MD5 命名，同内容文件可共享同一缩略图。
        入参说明：file_md5 (str): 文件 MD5 哈希值。
        返回值说明：Optional[str]: 缩略图物理文件存在则返回其绝对路径，否则返回 None。
        """
        return ThumbnailPathUtils.get_existing_thumbnail(file_md5)

    def generate_now(self, file_info: FileIndexDBModel, size: int) -> Optional[str]:
        """
        用途说明：同步生成单个文件缩略图（供相册按需生成接口使用），完成后按 MD5 回填数据库路径。
                  锁内会再次检查缩略图是否已存在：同内容文件并发请求时，后到的请求直接复用先到者
                  的成果，避免对同一文件反复删除重建。
        入参说明：
            file_info (FileIndexDBModel): 文件索引模型。
            size (int): 缩略图最大边长。
        返回值说明：Optional[str] - 生成成功返回缩略图绝对路径，失败返回 None。
        """
        with self._generate_now_lock:
            existing_path: Optional[str] = ThumbnailPathUtils.get_existing_thumbnail(file_info.file_md5)
            if existing_path:
                DBOperations.update_thumbnail_path_by_md5(file_info.file_md5, existing_path)
                return existing_path
            _, thumb_path = self._generate_single_thumbnail(file_info, size)
            if thumb_path:
                DBOperations.update_thumbnail_path_by_md5(file_info.file_md5, thumb_path)
            return thumb_path

    def _worker(self) -> None:
        """
        用途：工作循环。从队列提取任务并在锁外执行耗时生成逻辑，避免阻塞主线程或产生死锁。
        入参说明：无。
        返回值说明：无。
        """
        file_info: Optional[FileIndexDBModel] = None
        repo_id: int = get_current_repo_id()

        # 1. 提取任务（临界区：轻量级操作）
        with self._lock:
            if not self._queue:
                self._is_processing = False
                self._queue_set.clear()
                self._total_by_repo.clear()
                self._completed_by_repo.clear()
                self._paused_repos.clear()
                LogUtils.info(t('thumb_gen_completed_log'))
                return

            repo_id, file_info = self._queue.popleft()
            self._active_repo_id = repo_id
            generation: int = self._generation_by_repo.get(repo_id, 0)
            key: Tuple[int, str] = (repo_id, file_info.file_path)
            if key in self._queue_set:
                self._queue_set.remove(key)
            self._processing_keys.add(key)

        # 切换到任务所属仓库上下文，确保配置读取与索引更新落到正确的业务库
        set_current_repo_id(repo_id)

        # 2. 锁外执行耗时任务（磁盘IO与图像处理，预防死锁）
        resume_event: threading.Event = self._resume_events.setdefault(repo_id, threading.Event())
        while repo_id in self._paused_repos and not resume_event.wait(timeout=0.1):
            pass
        with self._lock:
            cancelled: bool = self._generation_by_repo.get(repo_id, 0) != generation
        if file_info and not cancelled:
            try:
                thumb_size: int = settingService.get_album_thumbnail_size()
                actual_path, thumb_path = self._generate_single_thumbnail(file_info, thumb_size)
                if thumb_path:
                    # 按 MD5 回填所有同内容文件（含副本）的缩略图路径，确保副本也能预览
                    DBOperations.update_thumbnail_path_by_md5(file_info.file_md5, thumb_path)
            except Exception as e:
                LogUtils.error(t('thumb_gen_failed_log', path=file_info.file_path, error=str(e)))

        with self._lock:
            self._processing_keys.discard(key)
            if not cancelled:
                self._completed_by_repo[repo_id] = self._completed_by_repo.get(repo_id, 0) + 1
            if self._active_repo_id == repo_id:
                self._active_repo_id = None

        # 3. 异步提交下一次循环，实现非阻塞的串行处理
        ThreadPoolManager.submit(self._worker)

    def _generate_single_thumbnail(self, file_info: FileIndexDBModel, size: int) -> Tuple[str, Optional[str]]:
        """
        用途：为单个文件生成缩略图（支持常见图片和视频格式，视频提取中间帧）。
        设计说明：先写入同目录临时文件再原子替换目标文件，避免并发访问时读到"已删除未写入"的空窗。
        入参说明：
            file_info (FileIndexDBModel): 文件索引模型。
            size (int): 缩略图最大边长（保持纵横比）。
        返回值说明：
            Tuple[str, Optional[str]]: (原始文件路径, 缩略图生成后的物理路径或None)。
        """
        file_path: str = file_info.file_path
        if not os.path.exists(file_path):
            return file_path, None

        # 使用源文件的 MD5 作为文件名确保唯一性，且同内容文件可复用缩略图
        thumb_path: str = ThumbnailPathUtils.get_thumbnail_file(file_info.file_md5)
        # 临时文件与目标同目录，保证 os.replace 为原子操作
        # 注意：临时文件必须保留 .jpg 后缀，OpenCV 按扩展名选择编码器，缺少可识别后缀会导致视频缩略图写入失败
        tmp_path: str = f"{thumb_path}.tmp.jpg"

        try:
            # 图片处理
            if Utils.is_image_file(file_path):
                with Image.open(file_path) as img:
                    img.thumbnail((size, size))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.save(tmp_path, "JPEG")
                os.replace(tmp_path, thumb_path)
                return file_path, thumb_path

            # 视频处理 (通过 OpenCV 提取中间帧)
            elif Utils.is_video_file(file_path):
                cap = cv2.VideoCapture(file_path)
                try:
                    if not cap.isOpened():
                        return file_path, None

                    # 获取视频总帧数
                    frame_count: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    # 计算中间帧位置，如果帧数获取失败则默认为 0
                    middle_frame_index: int = max(0, frame_count // 2)

                    # 设置跳转到中间帧
                    cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_index)
                    success, frame = cap.read()

                    # 兜底逻辑：如果中间帧读取失败，尝试读取第一帧
                    if not success and middle_frame_index > 0:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        success, frame = cap.read()

                    if success:
                        h: int = frame.shape[0]
                        w: int = frame.shape[1]
                        scale: float = size / max(h, w)
                        new_h: int = int(h * scale)
                        new_w: int = int(w * scale)
                        resized = cv2.resize(frame, (new_w, new_h))
                        if not cv2.imwrite(tmp_path, resized):
                            return file_path, None
                        os.replace(tmp_path, thumb_path)
                        return file_path, thumb_path
                finally:
                    cap.release()
        except Exception as e:
            LogUtils.error(t('thumb_gen_error_log', path=file_path, error=str(e)))
        finally:
            # 清理可能残留的临时文件
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as e:
                    LogUtils.error(t('thumb_gen_delete_failed_log', path=tmp_path, error=str(e)))

        return file_path, None
