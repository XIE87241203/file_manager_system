from typing import List, Dict, Tuple

from backend.common.base_async_service import BaseAsyncService
from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressStatus
from backend.common.utils import Utils
from backend.db.processor_manager import processor_manager
from backend.model.db.batch_check_db_model import BatchCheckDBModel


class BatchCheckService(BaseAsyncService):
    """
    用途说明：批量检测服务类，支持异步检测文件名是否存在于全库中，并管理进度。
    继承自 BaseAsyncService 以支持标准的异步任务控制。
    """

    @classmethod
    def start_batch_check_task(cls, file_names: List[str]) -> bool:
        """
        用途说明：启动异步批量检测任务。包含初始化进度、重置状态及提交线程池逻辑。
        入参说明：file_names (List[str]): 待检测的文件名列表。
        返回值说明：bool: 是否成功启动。
        """
        try:
            # --- 初始化逻辑开始 ---
            if cls._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
                LogUtils.error("批量检测任务已在运行中，拒绝启动")
                raise RuntimeError("批量检测任务已在运行中")

            # 重置进度和状态
            cls._progress_manager.set_status(ProgressStatus.PROCESSING)
            cls._progress_manager.set_stop_flag(False)
            cls._progress_manager.reset_progress(message="准备开始检测...", total=len(file_names))
            # --- 初始化逻辑结束 ---
            
            # 使用基类的私有方法启动任务
            return cls._start_task(cls._internal_check, file_names)
        except Exception as e:
            LogUtils.error(f"启动批量检测任务失败: {e}")
            return False

    @classmethod
    def _internal_check(cls, file_names: List[str]) -> None:
        """
        用途说明：批量检测内部逻辑，支持中途停止。
        入参说明：file_names (List[str]): 待检测的文件名列表。
        """
        try:
            # 1. 清空旧的结果
            processor_manager.batch_check_processor.clear_results()
            
            total: int = len(file_names)
            batch_size: int = 50  # 每50个文件更新一次进度和存库
            results_to_save: List[BatchCheckDBModel] = []
            
            for i, name in enumerate(file_names):
                # 检测是否被叫停
                if cls._progress_manager.is_stopped():
                    LogUtils.info("批量检测任务已由用户手动停止")
                    break

                # 构建搜索模式
                pattern: List[Tuple[str, str]] = [(name, Utils.process_search_query(name))]
                
                # 检测各库
                index_matches: Dict[str, str] = processor_manager.file_index_processor.get_paths_by_patterns(pattern)
                history_matches: Dict[str, str] = processor_manager.already_entered_file_processor.check_names_exist_by_patterns(pattern)
                pending_matches: Dict[str, str] = processor_manager.pending_entry_file_processor.check_names_exist_by_patterns(pattern)
                
                # 汇总
                source: str = "new"
                detail: str = ""
                
                if name in index_matches:
                    source, detail = "index", index_matches[name]
                elif name in history_matches:
                    source, detail = "history", f"匹配到: {history_matches[name]}"
                elif name in pending_matches:
                    source, detail = "pending", pending_matches[name]
                
                results_to_save.append(BatchCheckDBModel(name=name, source=source, detail=detail))
                
                # 分批存库并更新进度
                if (i + 1) % batch_size == 0 or (i + 1) == total:
                    processor_manager.batch_check_processor.batch_insert_results(results_to_save)
                    results_to_save.clear()
                    cls._progress_manager.update_progress(
                        current=i + 1,
                        message=f"已完成 {i + 1}/{total}"
                    )

            if cls._progress_manager.is_stopped():
                cls._progress_manager.set_status(ProgressStatus.IDLE)
                cls._progress_manager.update_progress(message="检测任务已停止")
            else:
                cls._progress_manager.set_status(ProgressStatus.COMPLETED)
                LogUtils.info("批量检测任务已完成")
            
        except Exception as e:
            LogUtils.error(f"批量检测任务异常: {e}")
            cls._progress_manager.set_status(ProgressStatus.ERROR)
            cls._progress_manager.update_progress(message=f"内部异常: {str(e)}")

    @staticmethod
    def get_all_results() -> List[BatchCheckDBModel]:
        """
        用途说明：获取所有检测结果。
        返回值说明：List[BatchCheckDBModel]: 检测结果列表。
        """
        return processor_manager.batch_check_processor.get_all_results()

    @classmethod
    def clear_task(cls) -> bool:
        """
        用途说明：清空任务结果和重置进度。
        返回值说明：bool: 是否成功。
        """
        processor_manager.batch_check_processor.clear_results()
        cls._progress_manager.set_status(ProgressStatus.IDLE)
        cls._progress_manager.reset_progress()
        return True
