import os
from dataclasses import asdict
from typing import Dict, Any, List, Tuple, Optional

from backend.db.db_operations import DBOperations
from backend.db.db_manager import DBManager
from backend.common.log_utils import LogUtils
from backend.file_repository.duplicate_check.duplicate_check_helper import DuplicateCheckHelper
from backend.common.thread_pool import ThreadPoolManager
from backend.common.progress_manager import ProgressManager, ProgressInfo, ProgressStatus


class DuplicateService:
    """
    用途：文件查重服务类，支持异步查重、进度查询、任务停止以及文件删除。
    接入全局线程池 ThreadPoolManager。
    """

    _progress_manager: ProgressManager = ProgressManager()

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """
        用途：获取当前查重任务的状态、进度及结果信息。
        入参说明：无
        返回值说明：Dict[str, Any] - 包含 status (状态), progress (进度详情) 和 results (查重结果列表) 的字典。
        """
        # 直接获取 ProgressManager 维护的状态字典作为基础
        status_data = DuplicateService._progress_manager.get_status()
        
        # 初始化结果列表
        results_list: List[Dict[str, Any]] = []
        
        # 查重特有逻辑：非运行状态下，尝试从数据库恢复历史查重结果
        if status_data["status"] != ProgressStatus.PROCESSING:
            results = DBOperations.get_all_duplicate_results()
            if results:
                # 自动同步状态：如果有历史结果担管理器状态不是“已完成”，则修正状态和消息
                if status_data["status"] != ProgressStatus.COMPLETED:
                    DuplicateService._progress_manager.set_status(ProgressStatus.COMPLETED)
                    DuplicateService._progress_manager.update_progress(message="已加载历史查重结果")
                    # 状态变更后重新拉取最新的状态字典
                    status_data = DuplicateService._progress_manager.get_status()
                
                results_list = [asdict(group) for group in results]

        # 挂载结果数据并返回
        status_data["results"] = results_list
        return status_data

    @staticmethod
    def stop_check() -> None:
        """
        用途：请求停止当前正在进行的查重任务。
        入参说明：无
        返回值说明：无
        """
        if DuplicateService._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            DuplicateService._progress_manager.set_stop_flag(True)
            LogUtils.info("收到停止查重任务请求")

    @staticmethod
    def start_async_check() -> bool:
        """
        用途：通过全局线程池启动异步查重任务。
        入参说明：无
        返回值说明：bool - 如果成功启动返回 True，如果已在查重中则返回 False。
        """
        if DuplicateService._progress_manager.get_raw_status() == ProgressStatus.PROCESSING:
            LogUtils.error("查重任务已在运行中，请勿重复启动")
            return False

        DuplicateService._progress_manager.set_status(ProgressStatus.PROCESSING)
        DuplicateService._progress_manager.set_stop_flag(False)
        DuplicateService._progress_manager.reset_progress(message="正在初始化...")

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
            results (List[DuplicateGroup]) - 查重结果对象列表。
            status_text (str) - 结束时的描述。
        返回值说明：无
        """
        DBOperations.save_duplicate_results(results)

        DuplicateService._progress_manager.set_status(ProgressStatus.COMPLETED)
        current_progress_info = DuplicateService._progress_manager.get_raw_progress_info()
        DuplicateService._progress_manager.update_progress(
            current=current_progress_info.total,
            message=status_text
        )
        LogUtils.info(status_text)

    @staticmethod
    def _internal_check() -> None:
        """
        用途：内部查重逻辑，在全局线程池中运行。
        入参说明：无
        返回值说明：无
        """
        try:
            LogUtils.info("开始执行文件查重逻辑...")

            total_files = DBOperations.get_file_count(DBManager.TABLE_FILE_INDEX)
            if total_files == 0:
                DuplicateService._complete_check([], "未发现可检查的文件")
                return

            DuplicateService._progress_manager.update_progress(total=total_files,
                                              message="正在准备分析文件...")

            helper = DuplicateCheckHelper()

            batch_size = 500
            processed_count = 0
            current_processed = 0

            while processed_count < total_files:
                if DuplicateService._progress_manager.is_stopped():
                    DuplicateService._handle_stopped()
                    return
                
                files = DBOperations.get_file_list_with_pagination(
                    table_name=DBManager.TABLE_FILE_INDEX,
                    limit=batch_size,
                    offset=processed_count,
                    sort_by="id",
                    order="ASC"
                )

                if not files:
                    break

                for file_info in files:
                    if DuplicateService._progress_manager.is_stopped():
                        DuplicateService._handle_stopped()
                        return
                    
                    current_processed += 1
                    DuplicateService._progress_manager.update_progress(
                        current=current_processed,
                        total=total_files,
                        message=f"正在分析 ({current_processed}/{total_files}): {file_info.file_name}"
                    )
                    helper.add_file(file_info)

                processed_count += batch_size

            if DuplicateService._progress_manager.is_stopped():
                DuplicateService._handle_stopped()
                return

            DuplicateService._progress_manager.update_progress(message="正在生成查重报告，请稍候...")
            results = helper.get_all_results()
            DuplicateService._complete_check(results, f"查重完成，共发现 {len(results)} 组重复文件")

        except Exception as e:
            LogUtils.error(f"异步查重任务发生异常: {e}")
            DuplicateService._progress_manager.set_status(ProgressStatus.ERROR)
            DuplicateService._progress_manager.update_progress(message=f"查重失败: {str(e)}")

    @staticmethod
    def _handle_stopped() -> None:
        """
        用途：处理任务被停止时的状态重置。
        入参说明：无
        返回值说明：无
        """
        DuplicateService._progress_manager.set_status(ProgressStatus.IDLE)
        DuplicateService._progress_manager.set_stop_flag(False)
        DuplicateService._progress_manager.update_progress(message="任务已由用户停止")
        LogUtils.info("查重任务已手动终止并重置状态")

    @staticmethod
    def delete_file(file_path: str) -> Tuple[bool, str]:
        """
        用途：删除物理文件并从数据库索引及重复结果中移除，同时删除对应的缩略图文件。
        入参说明：
            file_path (str) - 文件的绝对路径。
        返回值说明：Tuple[bool, str] - (是否成功, 详细说明)。
        """
        try:
            # 1. 获取并删除缩略图文件
            file_info = DBOperations.get_file_by_path(file_path)
            if file_info and file_info.thumbnail_path:
                if os.path.exists(file_info.thumbnail_path):
                    try:
                        os.remove(file_info.thumbnail_path)
                        LogUtils.info(f"缩略图文件已删除: {file_info.thumbnail_path}")
                    except Exception as e:
                        LogUtils.error(f"删除缩略图文件失败: {file_info.thumbnail_path}, 错误: {e}")

            # 2. 删除原物理文件
            if os.path.exists(file_path):
                os.remove(file_path)
                LogUtils.info(f"物理文件已成功删除: {file_path}")
            else:
                LogUtils.error(f"物理文件路径不存在，将仅清理数据库索引: {file_path}")

            # 3. 清理数据库记录
            DBOperations.delete_file_index_by_path(file_path)
            DBOperations.delete_duplicate_file_by_path(file_path)

            return True, "文件及其索引、缩略图已成功删除"
        except Exception as e:
            LogUtils.error(f"删除文件操作失败: {file_path}, 错误: {e}")
            return False, f"删除失败: {str(e)}"

    @staticmethod
    def delete_group(md5: str) -> Tuple[int, List[str]]:
        """
        用途：删除指定 MD5 对应的所有物理文件及其索引。
        入参说明：
            md5 (str) - 文件的 MD5 哈希值。
        返回值说明：Tuple[int, List[str]] - (成功删除的数量, 失败的文件路径列表)。
        """
        results = DBOperations.get_paths_by_md5(md5)

        success_count = 0
        failed_files = []

        for path in results:
            success, _ = DuplicateService.delete_file(path)
            if success:
                success_count += 1
            else:
                failed_files.append(path)

        LogUtils.info(f"批量删除完成: MD5={md5}, 成功={success_count}, 失败={len(failed_files)}")
        return success_count, failed_files
