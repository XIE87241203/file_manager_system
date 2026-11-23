import os
import shutil
from typing import Any, List, Optional

from backend.common.base_async_service import BaseAsyncService
from backend.common.file_type_enum import FileType
from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.db.db_operations import DBOperations
from backend.file_repository.thumbnail.thumbnail_generator import ThumbnailGenerator
from backend.file_repository.thumbnail.thumbnail_path_utils import ThumbnailPathUtils
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.thumbnail_result import ThumbnailResult
from backend.repository.repository_service import repositoryService


class ThumbnailService(BaseAsyncService):
    """
    用途说明：缩略图服务类。
    管理职责：
    1. 派发缩略图生成任务（非耗时操作，直接填充队列）。
    2. 同步物理文件（耗时操作，利用线程池异步清理无效文件）。
    3. 提供生成队列余量监控。
    """

    @classmethod
    def ensure_thumbnail(cls, file_path: str) -> ThumbnailResult:
        """
        用途说明：统一的按需缩略图生成入口（相册等页面共用同一接口）。
            1. 仅处理图片/视频、非回收站且物理文件真实存在的索引记录；
            2. 同内容（同 MD5）缩略图已存在时直接复用并回填数据库；
            3. 缺失时调用生成器同步生成；并发生成由生成器内部加锁与原子写入兜底。
        入参说明：
            file_path (str): 文件完整路径。
        返回值说明：ThumbnailResult - 源文件路径与缩略图路径（失败时缩略图路径为空）。
        """
        result: ThumbnailResult = ThumbnailResult(file_path=file_path, thumbnail_path=None)
        try:
            file_info: Optional[FileIndexDBModel] = DBOperations.get_file_by_path(file_path)
            media_types: List[str] = [FileType.IMAGE.value, FileType.VIDEO.value]
            if (file_info is None or file_info.recycle_bin_time
                    or file_info.file_type not in media_types
                    or not os.path.isfile(file_info.file_path)):
                LogUtils.error(t('thumb_ensure_file_invalid', path=file_path))
                return result

            existing_path: Optional[str] = ThumbnailGenerator.get_existing_thumbnail_path(file_info.file_md5)
            if existing_path:
                # 物理文件已存在时同步回填数据库，保证列表直接命中缩略图
                DBOperations.update_thumbnail_path_by_md5(file_info.file_md5, existing_path)
                result.thumbnail_path = existing_path
                return result

            thumb_size: int = repositoryService.get_current_config().thumbnail_size
            if not isinstance(thumb_size, int) or thumb_size <= 0:
                thumb_size = 256

            generated_path: Optional[str] = ThumbnailGenerator().generate_now(file_info, thumb_size)
            result.thumbnail_path = generated_path
            if generated_path:
                LogUtils.info(t('thumb_ensure_generated_log', path=file_path, thumb_path=generated_path))
            else:
                LogUtils.error(t('thumb_ensure_generate_failed', path=file_path))
        except Exception as e:
            LogUtils.error(t('thumb_ensure_generate_error', path=file_path, error=str(e)))
        return result

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
        LogUtils.info(t('thumb_stop_all_request'))
        ThumbnailGenerator().clear_queue()

    @classmethod
    def start_thumbnail_sync_task(cls) -> bool:
        """
        用途说明：启动异步物理文件同步任务，清理缓存目录下的无效缩略图。包含环境检查与状态初始化。
        入参说明：无
        返回值说明：bool - 任务是否成功提交至线程池。
        """
        try:
            # --- 初始化逻辑开始 ---
            if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
                LogUtils.error(t('thumb_sync_running'))
                return False

            ThumbnailPathUtils.ensure_thumbnail_dir()

            # 重置进度管理器
            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            cls._progress_manager.reset_progress(message=t('thumb_sync_preparing'))
            # --- 初始化逻辑结束 ---
            
            # 使用基类的私有方法启动物理同步任务
            return cls._start_task(cls._internal_sync_logic)
        except Exception as e:
            LogUtils.error(t('thumb_sync_start_failed', error=str(e)))
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
            cls._progress_manager.update_progress(message=t('thumb_sync_scanning'))

            # 同时扫描当前配置目录与历史兼容目录，升级后旧缩略图也能被正确维护
            thumbnail_dirs: List[str] = ThumbnailPathUtils.get_known_dirs()
            all_files: List[str] = []
            for thumbnail_dir in thumbnail_dirs:
                if os.path.isdir(thumbnail_dir):
                    all_files.extend(
                        os.path.join(thumbnail_dir, filename) for filename in os.listdir(thumbnail_dir)
                    )
            total_files: int = len(all_files)

            if total_files == 0:
                cls._progress_manager.set_status(ProgressStatus.COMPLETED)
                cls._progress_manager.update_progress(message=t('thumb_sync_empty'))
                return

            cls._progress_manager.reset_progress(total=total_files, message=t('thumb_sync_found_files', count=total_files))

            delete_count: int = 0
            for index, file_path in enumerate(all_files):
                # 检查任务是否被手动停止
                if cls._progress_manager.is_stopped():
                    LogUtils.info(t('thumb_sync_user_stop'))
                    return

                # 获取文件名（MD5）
                name_without_ext: str = os.path.splitext(os.path.basename(file_path))[0]

                # 如果数据库中不存在此 MD5 的记录，则物理文件为无效
                if not DBOperations.check_file_md5_exists(name_without_ext):
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        delete_count += 1

                # 分批更新进度，避免 UI 刷新过频
                if index % 100 == 0 or index == total_files - 1:
                    cls._progress_manager.update_progress(
                        current=index + 1,
                        message=t('thumb_sync_progress', current=index + 1, total=total_files, delete_count=delete_count)
                    )

            cls._progress_manager.set_status(ProgressStatus.COMPLETED)
            cls._progress_manager.update_progress(message=t('thumb_sync_done', count=delete_count))
            LogUtils.info(t('thumb_sync_done_log', count=delete_count))
            
        except Exception as e:
            LogUtils.error(t('thumb_sync_logic_error', error=str(e)))
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=t('thumb_sync_failed', error=str(e)))

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
            mode_str = t('thumb_dispatch_mode_all') if rebuild_all else t('thumb_dispatch_mode_missing')
            LogUtils.info(t('thumb_dispatch_no_files', mode=mode_str))
            return True

        batch_size: int = 1000
        offset: int = 0
        
        LogUtils.info(t('thumb_dispatch_start', count=total_count))

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

            LogUtils.info(t('thumb_dispatch_done', count=offset))
            return True
        except Exception as e:
            LogUtils.error(t('thumb_dispatch_error', error=str(e)))
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

            # 清空当前配置目录与历史兼容目录，避免旧缩略图残留
            for thumbnail_dir in ThumbnailPathUtils.get_known_dirs():
                if os.path.exists(thumbnail_dir):
                    shutil.rmtree(thumbnail_dir, ignore_errors=True)
            ThumbnailPathUtils.ensure_thumbnail_dir()

            return DBOperations.clear_all_thumbnail_records()
        except Exception as e:
            LogUtils.error(t('thumb_clear_all_failed', error=str(e)))
            return False
