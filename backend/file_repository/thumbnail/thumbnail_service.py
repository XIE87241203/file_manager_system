import os
import shutil
from typing import List, Dict, Any, Optional

from backend.db.db_operations import DBOperations
from backend.db.db_manager import DBManager
from backend.common.utils import Utils
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressManager, ProgressStatus
from backend.file_repository.thumbnail.thumbnail_generator import ThumbnailGenerator


class ThumbnailService:
    """
    用途：缩略图生成服务类，负责管理生成任务的状态、启动停止及进度查询。
    """
    _progress_manager: ProgressManager = ProgressManager()
    _THUMBNAIL_DIR = os.path.join(Utils.get_runtime_path(), "cache", "thumbnail")

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """
        用途：获取当前缩略图生成状态和进度信息。
        入参说明：无
        返回值说明：Dict[str, Any] - 包含状态和进度的字典，包含剩余任务数。
        """
        status_info = ThumbnailService._progress_manager.get_status()
        remaining = ThumbnailGenerator().get_remaining_count()
        
        # 如果队列中有任务但状态不是 processing，或者队列处理完但状态还是 processing，进行同步
        raw_status = ThumbnailService._progress_manager.get_raw_status()
        if remaining > 0 and raw_status != ProgressStatus.PROCESSING:
            ThumbnailService._progress_manager.set_status(ProgressStatus.PROCESSING)
            ThumbnailService._progress_manager.update_progress(message=f"剩余任务数:{remaining}" )
        elif remaining == 0 and raw_status == ProgressStatus.PROCESSING:
            ThumbnailService._progress_manager.set_status(ProgressStatus.COMPLETED)
            ThumbnailService._progress_manager.update_progress(message="所有任务处理完成")

        status_info["progress"]["remaining"] = remaining
        return status_info

    @staticmethod
    def stop_generation() -> None:
        """
        用途：请求停止当前正在进行的缩略图生成任务。
        入参说明：无
        返回值说明：无
        """
        ThumbnailGenerator().clear_queue()
        ThumbnailService._progress_manager.set_status(ProgressStatus.IDLE)
        ThumbnailService._progress_manager.update_progress(message="任务已手动停止并清空队列")
        LogUtils.info("用户请求停止缩略图生成任务，已清空生成器队列")

    @staticmethod
    def start_async_generation(rebuild_all: bool = False) -> bool:
        """
        用途：启动异步缩略图生成任务。
        入参说明：
            rebuild_all (bool): True - 全部重建模式；False - 仅针对无缩略图文件重建。
        返回值说明：bool - 是否成功启动
        """
        if ThumbnailService._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            LogUtils.error("缩略图生成任务已在运行中")
            return False

        # 1. 确定查询条件
        only_no_thumb = not rebuild_all
        
        # 获取符合条件的文件总数，用于初始化进度条
        total_count = DBOperations.get_file_index_count(only_no_thumbnail=only_no_thumb)
        
        if total_count == 0:
            ThumbnailService._progress_manager.set_status(ProgressStatus.COMPLETED)
            ThumbnailService._progress_manager.update_progress(message="没有需要生成缩略图的文件")
            LogUtils.info("启动缩略图生成：无可处理文件")
            return True

        # 设置状态为处理中并重置进度信息
        ThumbnailService._progress_manager.set_status(ProgressStatus.PROCESSING)
        ThumbnailService._progress_manager.reset_progress(
            total=total_count, 
            message="正在分批将任务加入队列..."
        )

        # 2. 分批获取文件路径并添加到生成队列
        batch_size = 1000
        offset = 0
        total_added = 0
        
        LogUtils.info(f"缩略图生成模式：{'全部重建' if rebuild_all else '仅缺失重建'}，预计处理 {total_count} 个文件")

        while offset < total_count:
            # 分批从数据库查询文件记录
            batch = DBOperations.get_file_index_list_by_condition(
                limit=batch_size,
                offset=offset,
                only_no_thumbnail= only_no_thumb
            )

            if not batch:
                break
                
            paths = [f.file_path for f in batch]
            # 批量添加到生成器的任务队列中
            ThumbnailGenerator().add_tasks(paths)
            
            total_added += len(paths)
            offset += batch_size
            
            if len(batch) < batch_size:
                break

        LogUtils.info(f"成功将 {total_added} 个缩略图生成任务提交后台处理")
        return True

    @staticmethod
    def clear_all_thumbnails() -> bool:
        """
        用途：删除所有缩略图文件及数据库记录。
        入参说明：无
        返回值说明：bool - 是否成功
        """
        try:
            # 停止当前生成任务
            ThumbnailService.stop_generation()
            
            # 1. 删除物理文件
            if os.path.exists(ThumbnailService._THUMBNAIL_DIR):
                shutil.rmtree(ThumbnailService._THUMBNAIL_DIR)
                os.makedirs(ThumbnailService._THUMBNAIL_DIR, exist_ok=True)
            
            # 2. 清空数据库记录
            return DBOperations.clear_all_thumbnail_records()
        except Exception as e:
            LogUtils.error(f"清除缩略图失败: {e}")
            return False
