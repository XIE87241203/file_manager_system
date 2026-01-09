from typing import Dict, Any, List, Tuple

from backend.common.log_utils import LogUtils
from backend.common.progress_manager import ProgressManager, ProgressInfo, ProgressStatus
from backend.common.thread_pool import ThreadPoolManager
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.file_repository.base_file_service import BaseFileService
from backend.file_repository.duplicate_check.duplicate_check_helper import DuplicateCheckHelper
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.duplicate_group_result import DuplicateGroupResult
from backend.model.pagination_result import PaginationResult


class DuplicateService(BaseFileService):
    """
    用途：文件查重服务类，支持异步查重、进度查询、任务停止以及文件删除。
    继承自 BaseFileService 以复用核心文件操作逻辑。
    接入全局线程池 ThreadPoolManager。
    """

    _progress_manager: ProgressManager = ProgressManager()

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """
        用途：获取当前查重任务的状态及进度。
        入参说明：无
        返回值说明：Dict[str, Any] - 包含 status (状态字符串) 和 progress (进度详情对象) 的字典。
        """
        return DuplicateService._progress_manager.get_status()

    @staticmethod
    def stop_check() -> None:
        """
        用途：请求停止当前正在进行的查重任务。
        入参说明：无
        返回值说明：无
        """
        status: ProgressStatus = DuplicateService._progress_manager.get_raw_status()
        if status == ProgressStatus.PROCESSING:
            DuplicateService._progress_manager.set_stop_flag(True)
            LogUtils.info("收到停止查重任务请求")

    @staticmethod
    def start_async_check() -> bool:
        """
        用途：通过全局线程池启动异步查重任务。
        入参说明：无
        返回值说明：bool - 如果成功启动返回 True，如果任务已在运行中则返回 False。
        """
        status: ProgressStatus = DuplicateService._progress_manager.get_raw_status()
        if status == ProgressStatus.PROCESSING:
            LogUtils.error("查重任务已在运行中，请勿重复启动")
            return False

        DuplicateService._progress_manager.set_status(ProgressStatus.PROCESSING)
        DuplicateService._progress_manager.set_stop_flag(False)
        DuplicateService._progress_manager.reset_progress(message="正在初始化...")

        # 清空旧的重复数据
        DBOperations.clear_duplicate_results()

        # 使用全局线程池提交查重任务
        ThreadPoolManager.submit(DuplicateService._internal_check)
        LogUtils.info("异步查重任务已提交至全局线程池")
        return True

    @staticmethod
    def _complete_check(results: List[Any], status_text: str) -> None:
        """
        用途：完成查重任务，将结果保存至数据库并更新最终状态。
        入参说明：
            results (List[DuplicateGroupDBModule]): 查重生成的分组结果列表。
            status_text (str): 任务结束时的描述信息。
        返回值说明：无
        """
        DBOperations.save_duplicate_results(results)

        DuplicateService._progress_manager.set_status(ProgressStatus.COMPLETED)
        current_info: ProgressInfo = DuplicateService._progress_manager.get_raw_progress_info()
        DuplicateService._progress_manager.update_progress(
            current=current_info.total,
            message=status_text
        )
        LogUtils.info(status_text)

    @staticmethod
    def _internal_check() -> None:
        """
        用途：内部查重逻辑，在独立线程中执行耗时扫描。
        入参说明：无
        返回值说明：无
        """
        try:
            LogUtils.info("开始执行文件查重逻辑...")

            total_files: int = DBOperations.get_file_index_count()
            if total_files == 0:
                DuplicateService._complete_check([], "未发现可检查的文件")
                return

            DuplicateService._progress_manager.update_progress(
                total=total_files,
                message="正在准备分析文件..."
            )

            helper: DuplicateCheckHelper = DuplicateCheckHelper()
            batch_size: int = 500
            processed_count: int = 0
            current_processed: int = 0

            while processed_count < total_files:
                if DuplicateService._progress_manager.is_stopped():
                    DuplicateService._handle_stopped()
                    return

                files: List[FileIndexDBModel] = DBOperations.get_file_index_list_by_condition(
                    limit=batch_size,
                    offset=processed_count,
                    only_no_thumbnail=False
                )

                if not files:
                    break

                for file_info in files:
                    if DuplicateService._progress_manager.is_stopped():
                        DuplicateService._handle_stopped()
                        return
                    
                    current_processed += 1
                    file_name: str = Utils.get_filename(file_info.file_path)
                    DuplicateService._progress_manager.update_progress(
                        current=current_processed,
                        total=total_files,
                        message=f"正在分析 ({current_processed}/{total_files}): {file_name}"
                    )
                    helper.add_file(file_info)

                processed_count += batch_size

            if DuplicateService._progress_manager.is_stopped():
                DuplicateService._handle_stopped()
                return

            DuplicateService._progress_manager.update_progress(message="正在生成查重报告，请稍候...")
            results: List[Any] = helper.get_all_results()
            DuplicateService._complete_check(results, f"查重完成，共发现 {len(results)} 组重复文件")

        except Exception as e:
            LogUtils.error(f"异步查重任务发生异常: {e}")
            DuplicateService._progress_manager.set_status(ProgressStatus.ERROR)
            DuplicateService._progress_manager.update_progress(message=f"查重失败: {str(e)}")

    @staticmethod
    def _handle_stopped() -> None:
        """
        用途：处理查重任务被手动停止时的状态重设。
        入参说明：无
        返回值说明：无
        """
        DuplicateService._progress_manager.set_status(ProgressStatus.IDLE)
        DuplicateService._progress_manager.set_stop_flag(False)
        DuplicateService._progress_manager.update_progress(message="任务已由用户停止")
        LogUtils.info("查重任务已手动终止并重置状态")

    @staticmethod
    def delete_group(md5: str) -> Tuple[int, List[str]]:
        """
        用途：删除指定 MD5 对应的所有重复物理文件及其索引记录。
        入参说明：
            md5 (str): 目标文件的 MD5 哈希值。
        返回值说明：
            Tuple[int, List[str]]: (成功删除的文件数量, 删除失败的文件路径列表)。
        """
        # 注意：此处假设 DBOperations 已实现 get_paths_by_md5，
        # 如果未实现，应改为通过 get_all_duplicate_results 逻辑获取路径。
        results: List[str] = DBOperations.get_paths_by_md5(md5)

        success_count: int = 0
        failed_files: List[str] = []

        for path in results:
            # 调用基类 BaseFileService 的删除逻辑
            success, _ = BaseFileService.delete_file(path)
            if success:
                success_count += 1
            else:
                failed_files.append(path)

        LogUtils.info(f"批量删除完成: MD5={md5}, 成功={success_count}, 失败={len(failed_files)}")
        return success_count, failed_files

    @staticmethod
    def get_all_duplicate_results(page: int, limit: int) -> PaginationResult[DuplicateGroupResult]:
        """
        用途：分页获取所有查重结果分组。
        入参说明：
            page (int): 当前页码。
            limit (int): 每页记录数。
        返回值说明：
            PaginationResult[DuplicateGroupResult]: 包含分页信息和结果列表的对象。
        """
        return DBOperations.get_all_duplicate_results(page, limit)
