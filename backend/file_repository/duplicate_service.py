import threading
import os
from backend.common.db_manager import db_manager
from backend.common.log_utils import LogUtils

class DuplicateService:
    """
    用途：文件查重服务类，支持异步查重、进度查询、任务停止以及文件删除
    """
    
    # 查重状态：idle, checking, completed, error
    _status = "idle"
    # 进度信息
    _progress = {
        "total": 0,
        "current": 0,
        "status_text": ""
    }
    # 查重结果缓存
    _results = []
    # 任务控制标志位
    _stop_flag = False
    
    # 锁，保证状态更新的线程安全
    _lock = threading.Lock()

    @staticmethod
    def get_status():
        """
        用途：获取当前查重状态和进度
        入参说明：无
        返回值说明：dict - 包含 status, progress 和 results 的字典
        """
        with DuplicateService._lock:
            return {
                "status": DuplicateService._status,
                "progress": DuplicateService._progress.copy(),
                "results": DuplicateService._results if DuplicateService._status == "completed" else []
            }

    @staticmethod
    def stop_check():
        """
        用途：请求停止当前正在进行的查重任务
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
        用途：启动异步查重任务
        入参说明：无
        返回值说明：bool - 如果成功启动返回 True，如果已在查重中则返回 False
        """
        with DuplicateService._lock:
            if DuplicateService._status == "checking":
                return False
            
            # 初始化状态
            DuplicateService._status = "checking"
            DuplicateService._stop_flag = False
            DuplicateService._progress = {"total": 100, "current": 0, "status_text": "正在初始化..."}
            DuplicateService._results = []

        # 开启线程执行查重
        thread = threading.Thread(target=DuplicateService._internal_check)
        thread.daemon = True
        thread.start()
        return True

    @staticmethod
    def _internal_check():
        """
        用途：内部查重逻辑，在独立线程中运行
        入参说明：无
        返回值说明：无
        """
        try:
            LogUtils.info("开始执行文件查重...")
            
            with DuplicateService._lock:
                DuplicateService._progress["status_text"] = "正在查询重复 MD5..."
                DuplicateService._progress["current"] = 20

            # 1. 找出重复的 MD5
            query_md5 = """
                SELECT file_md5, COUNT(*) as count 
                FROM file_index 
                GROUP BY file_md5 
                HAVING count > 1
            """
            duplicate_md5s = db_manager.execute_query(query_md5)
            
            if DuplicateService._stop_flag:
                DuplicateService._handle_stopped()
                return

            if not duplicate_md5s:
                with DuplicateService._lock:
                    DuplicateService._status = "completed"
                    DuplicateService._progress["current"] = 100
                    DuplicateService._progress["status_text"] = "未发现重复文件"
                    DuplicateService._results = []
                return

            total_groups = len(duplicate_md5s)
            with DuplicateService._lock:
                DuplicateService._progress["total"] = total_groups
                DuplicateService._progress["current"] = 0
                DuplicateService._progress["status_text"] = f"发现 {total_groups} 组重复文件，正在提取详细信息..."

            # 2. 提取重复文件的详细信息
            results = []
            for i, (md5, count) in enumerate(duplicate_md5s):
                if DuplicateService._stop_flag:
                    break
                
                query_files = "SELECT file_name, file_path, file_md5 FROM file_index WHERE file_md5 = ?"
                files_in_group = db_manager.execute_query(query_files, (md5,))
                
                group_data = {
                    "group_id": md5,
                    "count": count,
                    "files": []
                }
                for f_name, f_path, f_md5 in files_in_group:
                    group_data["files"].append({
                        "file_name": f_name,
                        "file_path": f_path,
                        "file_md5": f_md5
                    })
                
                results.append(group_data)
                
                with DuplicateService._lock:
                    DuplicateService._progress["current"] = i + 1

            if DuplicateService._stop_flag:
                DuplicateService._handle_stopped()
                return

            with DuplicateService._lock:
                DuplicateService._status = "completed"
                DuplicateService._results = results
                DuplicateService._progress["status_text"] = f"查重完成，共发现 {total_groups} 组重复文件"
                LogUtils.info(f"查重完成，共发现 {total_groups} 组重复文件")

        except Exception as e:
            LogUtils.error(f"异步查重任务发生异常: {e}")
            with DuplicateService._lock:
                DuplicateService._status = "error"
                DuplicateService._progress["status_text"] = f"查重失败: {str(e)}"

    @staticmethod
    def _handle_stopped():
        """
        用途：处理任务被停止时的状态重置
        """
        with DuplicateService._lock:
            DuplicateService._status = "idle"
            DuplicateService._stop_flag = False
            DuplicateService._progress["status_text"] = "任务已停止"
        LogUtils.info("查重任务已手动终止")

    @staticmethod
    def delete_file(file_path):
        """
        用途：删除物理文件并从 file_index 中移除索引
        入参说明：file_path (str) - 文件绝对路径
        返回值说明：tuple - (bool, str) 是否成功及错误信息
        """
        try:
            # 1. 检查文件是否存在
            if os.path.exists(file_path):
                # 2. 删除物理文件
                os.remove(file_path)
                LogUtils.info(f"物理文件已删除: {file_path}")
            else:
                LogUtils.warning(f"物理文件不存在，仅清理索引: {file_path}")

            # 3. 从数据库 file_index 中删除
            db_manager.execute_update("DELETE FROM file_index WHERE file_path = ?", (file_path,))
            
            # 4. 同步更新内存中的 results (如果查重已完成)
            with DuplicateService._lock:
                if DuplicateService._status == "completed":
                    for group in DuplicateService._results:
                        group["files"] = [f for f in group["files"] if f["file_path"] != file_path]
                        group["count"] = len(group["files"])
                    # 过滤掉文件数少于 2 的组（不再是重复组）
                    DuplicateService._results = [g for g in DuplicateService._results if g["count"] > 1]

            return True, "删除成功"
        except Exception as e:
            LogUtils.error(f"删除文件失败: {file_path}, 错误: {e}")
            return False, str(e)

    @staticmethod
    def delete_group(md5):
        """
        用途：删除某 MD5 对应的所有物理文件并从索引中移除
        入参说明：md5 (str) - 文件的 MD5 值
        返回值说明：tuple - (int, list) 成功删除的文件数量及失败的文件路径列表
        """
        # 1. 查询该 MD5 下的所有文件路径
        query = "SELECT file_path FROM file_index WHERE file_md5 = ?"
        results = db_manager.execute_query(query, (md5,))
        
        success_count = 0
        failed_files = []
        
        for (path,) in results:
            success, msg = DuplicateService.delete_file(path)
            if success:
                success_count += 1
            else:
                failed_files.append(path)
        
        return success_count, failed_files
