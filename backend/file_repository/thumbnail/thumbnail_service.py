import os
import shutil
from typing import Any, List

from backend.common.base_async_service import BaseAsyncService
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.thumbnail.thumbnail_generator import ThumbnailGenerator


class ThumbnailService(BaseAsyncService):
    """
    用途说明：缩略图服务类。
    管理职责：
    1. 派发缩略图生成任务（非耗时操作，直接填充队列）。
    2. 同步物理文件（耗时操作，利用线程池异步清理孤儿文件）。
    3. 提供生成队列余量监控。
    """
    _THUMBNAIL_DIR: str = os.path.join(Utils.get_runtime_path(), "cache", "thumbnail")

    @classmethod
    def get_thumbnail_queue_count(cls) -> int:
        """
        用途说明：获取缩略图生成器队列中剩余的任务数量。
        入参说明：无
        返回值说明：int - 队列中剩余待处理的任务总数。
        """
        return ThumbnailGenerator().get_remaining_count()

    @classmethod
    def stop_thumbnail_generation(cls) -> None:
        """
        用途说明：停止缩略图生成任务，清空任务队列并停止物理同步任务。
        入参说明：无
        返回值说明：无
        """
        LogUtils.info("正在请求停止所有缩略图相关任务...")
        ThumbnailGenerator().clear_queue()

    @classmethod
    def start_thumbnail_sync_task(cls) -> bool:
        """
        用途说明：启动异步物理文件同步任务，清理缓存目录下的“孤儿”缩略图。包含环境检查与状态初始化。
        入参说明：
            params (Any): 启动参数（预留）。
        返回值说明：bool - 任务是否成功提交至线程池。
        """
        try:
            # --- 初始化逻辑开始 ---
            if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
                LogUtils.error("物理同步任务已在运行中，拒绝重复启动")
                return False

            if not os.path.exists(cls._THUMBNAIL_DIR):
                os.makedirs(cls._THUMBNAIL_DIR, exist_ok=True)
            
            # 重置进度管理器
            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            cls._progress_manager.reset_progress(message="正在准备同步...")
            # --- 初始化逻辑结束 ---
            
            # 使用基类的私有方法启动物理同步任务
            return cls._start_task(cls._internal_sync_logic)
        except Exception as e:
            LogUtils.error(f"启动物理同步任务失败: {e}")
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            return False

    @classmethod
    def _internal_sync_logic(cls) -> None:
        """
        用途说明：物理同步任务的核心调度逻辑。遍历磁盘文件并校验数据库状态。
        入参说明：无
        返回值说明：无
        """
        try:
            cls._progress_manager.update_progress(message="正在扫描缩略图缓存目录...")
            
            all_files: List[str] = os.listdir(cls._THUMBNAIL_DIR)
            total_files: int = len(all_files)
            
            if total_files == 0:
                cls._progress_manager.set_status(ProgressStatus.COMPLETED)
                cls._progress_manager.update_progress(message="缓存目录为空，无需同步")
                return

            cls._progress_manager.reset_progress(total=total_files, message=f"找到 {total_files} 个物理文件，开始校验...")

            delete_count: int = 0
            for index, filename in enumerate(all_files):
                # 检查任务是否被手动停止
                if cls._progress_manager.is_stopped():
                    LogUtils.info("物理同步任务被用户手动停止")
                    return

                # 获取文件名（MD5）
                name_without_ext: str = os.path.splitext(filename)[0]
                
                # 仅校验标准的 32 位 MD5 文件名，防止误删非缓存文件
                if len(name_without_ext) == 32:
                    # 如果数据库中不存在此 MD5 的记录，则物理文件为无效“孤儿”
                    if not DBOperations.check_file_md5_exists(name_without_ext):
                        file_path: str = os.path.join(cls._THUMBNAIL_DIR, filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            delete_count += 1
                
                # 分批更新进度，避免 UI 刷新过频
                if index % 100 == 0 or index == total_files - 1:
                    cls._progress_manager.update_progress(
                        current=index + 1, 
                        message=f"已扫描: {index + 1}/{total_files}，已清理失效文件: {delete_count}"
                    )

            cls._progress_manager.set_status(ProgressStatus.COMPLETED)
            cls._progress_manager.update_progress(message=f"同步完成！共清理了 {delete_count} 个无效缩略图")
            LogUtils.info(f"缩略图物理同步执行完毕，共清理文件: {delete_count}")
            
        except Exception as e:
            LogUtils.error(f"执行物理同步任务逻辑异常: {e}")
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=f"同步异常: {str(e)}")

    @classmethod
    def dispatch_thumbnail_tasks(cls, rebuild_all: bool) -> bool:
        """
        用途说明：将缩略图生成任务分派至后台生成器。此操作为轻量级，仅负责批量推送任务。
        入参说明：
            rebuild_all (bool): 是否强制重建所有缩略图。
        返回值说明：bool - 任务是否成功加入生成队列。
        """
        only_no_thumb: bool = not rebuild_all
        total_count: int = DBOperations.get_file_index_count(only_no_thumbnail=only_no_thumb)
        
        if total_count == 0:
            LogUtils.info(f"派发缩略图任务：无可处理文件 (模式: {'全部' if rebuild_all else '仅缺失'})")
            return True

        batch_size: int = 1000
        offset: int = 0
        
        LogUtils.info(f"开始分派缩略图任务: 预计 {total_count} 个文件")

        try:
            while offset < total_count:
                batch: List[Any] = DBOperations.get_file_index_list_by_condition(
                    limit=batch_size,
                    offset=offset,
                    only_no_thumbnail=only_no_thumb
                )
                if not batch:
                    break
                
                ThumbnailGenerator().add_tasks(batch)
                offset += len(batch)

            LogUtils.info(f"缩略图分派完毕，共计 {offset} 个任务已进入后台生成队列")
            return True
        except Exception as e:
            LogUtils.error(f"分派缩略图任务时发生异常: {e}")
            return False

    @classmethod
    def clear_all_thumbnails(cls) -> bool:
        """
        用途说明：全量清理操作。停止所有任务，清空物理缓存并重置数据库标记。
        入参说明：无
        返回值说明：bool - 操作是否全部成功。
        """
        try:
            cls.stop_thumbnail_generation()
            
            if os.path.exists(cls._THUMBNAIL_DIR):
                shutil.rmtree(cls._THUMBNAIL_DIR)
                os.makedirs(cls._THUMBNAIL_DIR, exist_ok=True)
            
            return DBOperations.clear_all_thumbnail_records()
        except Exception as e:
            LogUtils.error(f"全量清除缩略图失败: {e}")
            return False
