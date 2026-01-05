import threading
import os
from dataclasses import asdict
from typing import Dict, Any, List, Tuple, Optional

from backend.db.db_operations import DBOperations
from backend.db.db_manager import DBManager
from backend.common.log_utils import LogUtils
from backend.file_repository.duplicate_check.duplicate_check_helper import DuplicateCheckHelper


class DuplicateService:
    """
    用途：文件查重服务类，支持异步查重、进度查询、任务停止以及文件删除。
    结果现在持久化存储在数据库中，不再使用内存缓存。
    """

    # 查重状态：idle, checking, completed, error
    _status: str = "idle"
    # 进度信息
    _progress: Dict[str, Any] = {
        "total": 0,
        "current": 0,
        "status_text": ""
    }
    # 任务控制标志位
    _stop_flag: bool = False

    # 锁，保证状态更新的线程安全
    _lock: threading.Lock = threading.Lock()

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """
        用途：获取当前查重状态和进度。优先检查数据库缓存，若存在结果则状态标记为已完成。
        入参说明：无
        返回值说明：Dict[str, Any] - 包含 status (状态), progress (进度详情) 和 results (查重结果列表) 的字典。
        """
        # 初始化局部变量，避免 referenced before assignment 警告
        current_status: str = "idle"
        current_progress: Dict[str, Any] = {"total": 0, "current": 0, "status_text": ""}
        results_dict: List[Dict[str, Any]] = []

        with DuplicateService._lock:
            current_status = DuplicateService._status
            current_progress = DuplicateService._progress.copy()

        # 如果当前不是正在检查中，则尝试从数据库获取持久化的结果
        if current_status != "checking":
            results = DBOperations.get_all_duplicate_results()
            if results:
                # 数据库有数据，则状态视为已完成，即便内存状态为 idle (例如服务重启后)
                current_status = "completed"
                results_dict = [asdict(group) for group in results]
                # 补充进度描述信息，如果是冷启动状态（即内存进度没有描述）
                if not current_progress.get("status_text"):
                    current_progress["status_text"] = "已加载历史查重结果"

        return {
            "status": current_status,
            "progress": current_progress,
            "results": results_dict
        }

    @staticmethod
    def stop_check() -> None:
        """
        用途：请求停止当前正在进行的查重任务。
        入参说明：无
        返回值说明：无
        """
        with DuplicateService._lock:
            if DuplicateService._status == "checking":
                DuplicateService._stop_flag = True
                LogUtils.info("收到停止查重任务请求")

    @staticmethod
    def start_async_check() -> bool:
        """
        用途：启动异步查重任务。
        入参说明：无
        返回值说明：bool - 如果成功启动返回 True，如果已在查重中则返回 False。
        """
        with DuplicateService._lock:
            if DuplicateService._status == "checking":
                LogUtils.error("查重任务已在运行中，请勿重复启动")
                return False

            # 初始化状态
            DuplicateService._status = "checking"
            DuplicateService._stop_flag = False
            DuplicateService._progress = {"total": 0, "current": 0, "status_text": "正在初始化..."}

            # 每次开始扫描前清空对应数据库表
            DBOperations.clear_duplicate_results()

        # 开启线程执行查重
        thread = threading.Thread(target=DuplicateService._internal_check)
        thread.daemon = True
        thread.start()
        LogUtils.info("异步查重任务已启动，已清空历史重复结果")
        return True

    @staticmethod
    def _update_progress(current: Optional[int] = None, total: Optional[int] = None,
                         status_text: Optional[str] = None) -> None:
        """
        用途：更新查重任务的进度信息（线程安全）。
        入参说明：
            current (int, optional) - 当前完成的任务数。
            total (int, optional) - 总任务数。
            status_text (str, optional) - 进度描述文本。
        返回值说明：无
        """
        with DuplicateService._lock:
            if current is not None:
                DuplicateService._progress["current"] = current
            if total is not None:
                DuplicateService._progress["total"] = total
            if status_text is not None:
                DuplicateService._progress["status_text"] = status_text

    @staticmethod
    def _is_stopped() -> bool:
        """
        用途：检查停止标志位（线程安全）。
        入参说明：无
        返回值说明：bool - 是否已请求停止。
        """
        with DuplicateService._lock:
            return DuplicateService._stop_flag

    @staticmethod
    def _complete_check(results: List[Any], status_text: str) -> None:
        """
        用途：完成查重任务，将结果保存至数据库并更新最终状态（线程安全）。
        入参说明：
            results (List[DuplicateGroup]) - 查重结果对象列表。
            status_text (str) - 结束时的描述。
        返回值说明：无
        """
        # 将结果保存到数据库
        DBOperations.save_duplicate_results(results)

        with DuplicateService._lock:
            DuplicateService._status = "completed"
            DuplicateService._progress["current"] = DuplicateService._progress["total"]
            DuplicateService._progress["status_text"] = status_text
        LogUtils.info(status_text)

    @staticmethod
    def _internal_check() -> None:
        """
        用途：内部查重逻辑，在独立线程中运行。遍历文件索引并调用检查器。
        入参说明：无
        返回值说明：无
        """
        try:
            LogUtils.info("开始执行文件查重逻辑...")

            # 1. 获取总文件数
            total_files = DBOperations.get_file_count(DBManager.TABLE_FILE_INDEX)
            if total_files == 0:
                DuplicateService._complete_check([], "未发现可检查的文件")
                return

            DuplicateService._update_progress(total=total_files,
                                              status_text="正在分析文件重复情况...")

            # 2. 实例化查重助手
            helper = DuplicateCheckHelper()

            # 3. 分批读取文件并录入
            batch_size = 500
            processed_count = 0

            while processed_count < total_files:
                if DuplicateService._is_stopped():
                    DuplicateService._handle_stopped()
                    return
                DuplicateService._update_progress(current=processed_count, total=total_files,
                                                  status_text="正在分析文件重复情况...")
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
                    helper.add_file(file_info)

                processed_count += len(files)
                DuplicateService._update_progress(current=processed_count)

            # 4. 获取并完成结果汇总
            results = helper.get_all_results()
            DuplicateService._complete_check(results, f"查重完成，共发现 {len(results)} 组重复文件")

        except Exception as e:
            LogUtils.error(f"异步查重任务发生异常: {e}")
            with DuplicateService._lock:
                DuplicateService._status = "error"
                DuplicateService._progress["status_text"] = f"查重失败: {str(e)}"

    @staticmethod
    def _handle_stopped() -> None:
        """
        用途：处理任务被停止时的状态重置。
        入参说明：无
        返回值说明：无
        """
        with DuplicateService._lock:
            DuplicateService._status = "idle"
            DuplicateService._stop_flag = False
            DuplicateService._progress["status_text"] = "任务已由用户停止"
        LogUtils.info("查重任务已手动终止并重置状态")

    @staticmethod
    def delete_file(file_path: str) -> Tuple[bool, str]:
        """
        用途：删除物理文件并从数据库索引及重复结果中移除。
        入参说明：
            file_path (str) - 文件的绝对路径。
        返回值说明：Tuple[bool, str] - (是否成功, 详细说明)。
        """
        try:
            # 1. 检查并删除物理文件
            if os.path.exists(file_path):
                os.remove(file_path)
                LogUtils.info(f"物理文件已成功删除: {file_path}")
            else:
                LogUtils.error(f"物理文件路径不存在，将仅清理数据库索引: {file_path}")

            # 2. 从数据库索引中移除
            DBOperations.delete_file_index_by_path(file_path)

            # 3. 同步更新数据库中的查重结果
            DBOperations.delete_duplicate_file_by_path(file_path)

            return True, "文件及其索引已成功删除"
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
        # 1. 查询该 MD5 关联的所有路径
        results = DBOperations.get_paths_by_md5(md5)

        success_count = 0
        failed_files = []

        # 2. 依次调用删除逻辑
        for path in results:
            success, _ = DuplicateService.delete_file(path)
            if success:
                success_count += 1
            else:
                failed_files.append(path)

        LogUtils.info(f"批量删除完成: MD5={md5}, 成功={success_count}, 失败={len(failed_files)}")
        return success_count, failed_files
