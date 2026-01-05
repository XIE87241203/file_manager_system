import threading
import os
from dataclasses import asdict
from backend.db.db_operations import DBOperations
from backend.db.db_manager import DBManager
from backend.common.log_utils import LogUtils
from backend.file_repository.duplicate_check.duplicate_check_helper import DuplicateCheckHelper

class DuplicateService:
    """
    用途：文件查重服务类，支持异步查重、进度查询、任务停止以及文件删除。
    """

    # 查重状态：idle, checking, completed, error
    _status = "idle"
    # 进度信息
    _progress = {
        "total": 0,
        "current": 0,
        "status_text": ""
    }
    # 查重结果缓存 (存储 DuplicateGroup 对象列表)
    _results = []
    # 任务控制标志位
    _stop_flag = False

    # 锁，保证状态更新的线程安全
    _lock = threading.Lock()

    @staticmethod
    def get_status():
        """
        用途：获取当前查重状态和进度。
        入参说明：无
        返回值说明：dict - 包含 status (状态), progress (进度详情) 和 results (查重结果列表，已转换为字典) 的字典。
        """
        with DuplicateService._lock:
            # 只有在完成状态下才返回结果，并将数据类对象转换为字典以支持 JSON 序列化
            results_dict = []
            if DuplicateService._status == "completed":
                results_dict = [asdict(group) for group in DuplicateService._results]

            return {
                "status": DuplicateService._status,
                "progress": DuplicateService._progress.copy(),
                "results": results_dict
            }

    @staticmethod
    def stop_check():
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
    def start_async_check():
        """
        用途：启动异步查重任务。
        入参说明：无
        返回值说明：bool - 如果成功启动返回 True，如果已在查重中则返回 False。
        """
        with DuplicateService._lock:
            if DuplicateService._status == "checking":
                LogUtils.warning("查重任务已在运行中，请勿重复启动")
                return False

            # 初始化状态
            DuplicateService._status = "checking"
            DuplicateService._stop_flag = False
            DuplicateService._progress = {"total": 0, "current": 0, "status_text": "正在初始化..."}
            DuplicateService._results = []

        # 开启线程执行查重
        thread = threading.Thread(target=DuplicateService._internal_check)
        thread.daemon = True
        thread.start()
        LogUtils.info("异步查重任务已启动")
        return True

    @staticmethod
    def _update_progress(current=None, total=None, status_text=None):
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
    def _is_stopped():
        """
        用途：检查停止标志位（线程安全）。
        入参说明：无
        返回值说明：bool - 是否已请求停止。
        """
        with DuplicateService._lock:
            return DuplicateService._stop_flag

    @staticmethod
    def _complete_check(results, status_text):
        """
        用途：完成查重任务，更新最终状态和结果（线程安全）。
        入参说明：
            results (List[DuplicateGroup]) - 查重结果对象列表。
            status_text (str) - 结束时的描述。
        返回值说明：无
        """
        with DuplicateService._lock:
            DuplicateService._status = "completed"
            DuplicateService._results = results
            DuplicateService._progress["current"] = DuplicateService._progress["total"]
            DuplicateService._progress["status_text"] = status_text
        LogUtils.info(status_text)

    @staticmethod
    def _internal_check():
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

            DuplicateService._update_progress(total=total_files, status_text="正在分析文件重复情况...")

            # 2. 实例化查重助手
            helper = DuplicateCheckHelper()

            # 3. 分批读取文件并录入
            batch_size = 500
            processed_count = 0
            
            while processed_count < total_files:
                if DuplicateService._is_stopped():
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
    def _handle_stopped():
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
    def delete_file(file_path):
        """
        用途：删除物理文件并从 file_index 中移除索引。
        入参说明：
            file_path (str) - 文件的绝对路径。
        返回值说明：tuple - (bool, str) 是否成功及详细说明。
        """
        try:
            # 1. 检查并删除物理文件
            if os.path.exists(file_path):
                os.remove(file_path)
                LogUtils.info(f"物理文件已成功删除: {file_path}")
            else:
                LogUtils.warning(f"物理文件路径不存在，将仅清理数据库索引: {file_path}")

            # 2. 从数据库索引中移除
            DBOperations.delete_file_index_by_path(file_path)
            
            # 3. 同步更新内存中的查重结果缓存
            DuplicateService._sync_results_after_deletion(file_path)

            return True, "文件及其索引已成功删除"
        except Exception as e:
            LogUtils.error(f"删除文件操作失败: {file_path}, 错误: {e}")
            return False, f"删除失败: {str(e)}"

    @staticmethod
    def _sync_results_after_deletion(file_path):
        """
        用途：文件删除后，同步更新内存中已存在的查重结果（线程安全）。
        入参说明：
            file_path (str) - 被删除文件的路径。
        返回值说明：无
        """
        with DuplicateService._lock:
            if DuplicateService._status != "completed":
                return
            
            # 遍历并更新结果
            new_results = []
            for group in DuplicateService._results:
                # 过滤掉被删除的文件对象
                group.files = [f for f in group.files if f.file_path != file_path]
                
                # 只有当组内文件数仍大于 1 时，才保留该重复组
                if len(group.files) > 1:
                    new_results.append(group)
            
            DuplicateService._results = new_results

    @staticmethod
    def delete_group(md5):
        """
        用途：删除指定 MD5 对应的所有物理文件及其索引。
        入参说明：
            md5 (str) - 文件的 MD5 哈希值。
        返回值说明：tuple - (int, list) 成功删除的数量及失败的文件路径列表。
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
