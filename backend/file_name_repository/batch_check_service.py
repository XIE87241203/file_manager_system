from typing import List, Dict, Tuple, Optional

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
    def init_service(cls) -> None:
        """
        用途说明：初始化服务状态，检测数据库中是否已存在批量检测数据。
        如果存在，则将进度管理器初始化为“已完成”状态。
        """
        try:
            count: int = processor_manager.batch_check_processor.get_count()
            if count > 0:
                cls._progress_manager.set_status(ProgressStatus.COMPLETED)
                cls._progress_manager.update_progress(
                    current=1,
                    total=1,
                    message=f"检测完成，共有 {count} 条检测记录"
                )
                LogUtils.info(f"批量检测服务初始化：检测到已有 {count} 条记录，已自动恢复进度状态")
        except Exception as e:
            LogUtils.error(f"批量检测服务初始化失败: {e}")

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
        用途说明：批量检测内部逻辑，支持中途停止。采用分批查询优化数据库性能。
        入参说明：file_names (List[str]): 待检测的文件名列表。
        """
        try:
            # 1. 清空旧的结果
            processor_manager.batch_check_processor.clear_results()
            
            total: int = len(file_names)
            batch_size: int = 100  # 综合性能与进度反馈频率，设置每批处理 100 条
            
            for i in range(0, total, batch_size):
                # 检测是否被叫停
                if cls._progress_manager.is_stopped():
                    LogUtils.info("批量检测任务已由用户手动停止")
                    break

                # 获取当前批次的文件名
                current_batch = file_names[i : i + batch_size]
                
                # 批量构建搜索模式 (模糊匹配模式)
                name_patterns: List[Tuple[str, str]] = [(name, Utils.process_search_query(name)) for name in current_batch]
                
                # 2. 调用处理器进行批量搜索 (注：FileIndexProcessor.get_paths_by_patterns 已调整为搜索文件名而非路径)
                index_matches: Dict[str, str] = processor_manager.file_index_processor.get_paths_by_patterns(name_patterns)
                history_matches: Dict[str, str] = processor_manager.already_entered_file_processor.check_names_exist_by_patterns(name_patterns)
                pending_matches: Dict[str, str] = processor_manager.pending_entry_file_processor.check_names_exist_by_patterns(name_patterns)
                
                results_to_save: List[BatchCheckDBModel] = []
                for name in current_batch:
                    # 汇总各库检测结果
                    source: str = "new"
                    detail: str = ""
                    
                    if name in index_matches:
                        # 文件索引库匹配：返回路径
                        source, detail = "index", index_matches[name]
                    elif name in history_matches:
                        # 曾录入库匹配：返回匹配到的完整名
                        source, detail = "history", f"匹配到: {history_matches[name]}"
                    elif name in pending_matches:
                        # 待录入库匹配：返回匹配到的名
                        source, detail = "pending", pending_matches[name]
                    
                    results_to_save.append(BatchCheckDBModel(name=name, source=source, detail=detail))
                
                # 3. 批量存入结果表
                processor_manager.batch_check_processor.batch_insert_results(results_to_save)
                
                # 4. 更新进度
                current_progress = min(i + batch_size, total)
                cls._progress_manager.update_progress(
                    current=current_progress,
                    message=f"已完成 {current_progress}/{total}"
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
    def get_all_results(sort_by: Optional[str] = None, order_asc: bool = False) -> List[BatchCheckDBModel]:
        """
        用途说明：获取所有检测结果，支持排序。
        入参说明：
            sort_by (Optional[str]): 排序字段。
            order_asc (bool): 是否升序。
        返回值说明：List[BatchCheckDBModel]: 检测结果列表。
        """
        return processor_manager.batch_check_processor.get_all_results(sort_by=sort_by, order_asc=order_asc)

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


# 在模块加载时执行初始化
BatchCheckService.init_service()
