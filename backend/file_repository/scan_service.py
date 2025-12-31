import os
import hashlib
import threading
from backend.setting.setting import settings
from backend.common.db_manager import db_manager
from backend.common.log_utils import LogUtils

class ScanService:
    """
    用途：文件仓库扫描服务类，支持异步扫描、进度查询和任务停止
    """
    
    # 扫描状态：idle, scanning, completed, error
    _status = "idle"
    # 进度信息
    _progress = {
        "total": 0,
        "current": 0,
        "current_file": ""
    }
    # 任务控制标志位
    _stop_flag = False
    
    # 锁，保证状态更新的线程安全
    _lock = threading.Lock()

    @staticmethod
    def get_status():
        """
        用途：获取当前扫描状态和进度
        入参说明：无
        返回值说明：dict - 包含 status 和 progress 的字典
        """
        with ScanService._lock:
            return {
                "status": ScanService._status,
                "progress": ScanService._progress.copy()
            }

    @staticmethod
    def stop_scan():
        """
        用途：请求停止当前正在进行的扫描任务
        入参说明：无
        返回值说明：无
        """
        with ScanService._lock:
            if ScanService._status == "scanning":
                ScanService._stop_flag = True
                LogUtils.info("收到停止扫描任务请求")

    @staticmethod
    def calculate_md5(file_path):
        """
        用途：计算指定文件的 MD5 哈希值
        入参说明：file_path (str) - 文件的绝对路径
        返回值说明：str - 文件的 MD5 十六进制字符串；如果读取失败则返回空字符串
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            LogUtils.error(f"计算文件 MD5 失败: {file_path}, 错误: {e}")
            return ""

    @staticmethod
    def start_async_scan():
        """
        用途：启动异步扫描任务
        入参说明：无
        返回值说明：bool - 如果成功启动返回 True，如果已在扫描中则返回 False
        """
        with ScanService._lock:
            if ScanService._status == "scanning":
                return False
            
            # 初始化状态
            ScanService._status = "scanning"
            ScanService._stop_flag = False
            ScanService._progress = {"total": 0, "current": 0, "current_file": ""}

        # 开启线程执行扫描
        thread = threading.Thread(target=ScanService._internal_scan)
        thread.daemon = True
        thread.start()
        return True

    @staticmethod
    def _internal_scan():
        """
        用途：内部扫描逻辑，在独立线程中运行，支持分阶段扫描和中途停止
        入参说明：无
        返回值说明：无
        """
        try:
            # 1. 扫描开始前清空当前索引表
            LogUtils.info("扫描开始，正在清空当前索引表...")
            if not db_manager.clear_file_index():
                LogUtils.error("清空索引表失败，终止扫描")
                with ScanService._lock:
                    ScanService._status = "error"
                return

            directories = settings.file_repository.get("directories", [])
            suffixes = settings.file_repository.get("scan_suffixes", ["*"])
            suffixes = [s.replace('.', '').lower() for s in suffixes]
            scan_all = "*" in suffixes

            all_files_info = []
            
            # 第一阶段：统计总文件数
            LogUtils.info("扫描任务：开始统计文件总数...")
            temp_file_list = []
            for repo_path in directories:
                if ScanService._stop_flag: break
                if not os.path.exists(repo_path): continue
                for root, dirs, files in os.walk(repo_path):
                    if ScanService._stop_flag: break
                    for file in files:
                        file_ext = os.path.splitext(file)[1].replace('.', '').lower()
                        if scan_all or file_ext in suffixes:
                            temp_file_list.append(os.path.join(root, file))
            
            if ScanService._stop_flag:
                ScanService._handle_stopped()
                return

            total_count = len(temp_file_list)
            with ScanService._lock:
                ScanService._progress["total"] = total_count

            # 第二阶段：计算 MD5 并存库
            for i, file_path in enumerate(temp_file_list):
                if ScanService._stop_flag:
                    break
                    
                file_name = os.path.basename(file_path)
                
                # 更新进度
                with ScanService._lock:
                    ScanService._progress["current"] = i + 1
                    ScanService._progress["current_file"] = file_name
                
                file_md5 = ScanService.calculate_md5(file_path)
                if file_md5:
                    all_files_info.append((file_path, file_name, file_md5))
                
                # 每 100 个文件批量写入一次
                if len(all_files_info) >= 100:
                    db_manager.batch_insert_files(all_files_info)
                    all_files_info = []

            # 处理剩余的文件
            if all_files_info and not ScanService._stop_flag:
                db_manager.batch_insert_files(all_files_info)

            with ScanService._lock:
                if ScanService._stop_flag:
                    ScanService._handle_stopped()
                else:
                    # 2. 扫描成功完成后，将数据复制到历史表
                    LogUtils.info("扫描成功，正在备份至历史表...")
                    if db_manager.copy_to_history():
                        ScanService._status = "completed"
                        LogUtils.info(f"扫描任务正常完成，共索引 {total_count} 个文件")
                    else:
                        ScanService._status = "error"
                        LogUtils.error("备份至历史表失败")

        except Exception as e:
            LogUtils.error(f"异步扫描任务发生异常: {e}")
            with ScanService._lock:
                ScanService._status = "error"

    @staticmethod
    def _handle_stopped():
        """
        用途：处理任务被停止时的状态重置
        """
        ScanService._status = "idle"
        ScanService._stop_flag = False
        LogUtils.info("扫描任务已手动终止并重置为待机状态")
