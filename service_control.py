"""用途说明：提供系统后端安全停止、启动和重启的公共控制逻辑。"""

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import psutil

from backend.common.i18n_utils import I18nUtils, t
from backend.common.log_utils import LogUtils
from config import GlobalConfig


PROJECT_ROOT: Path = Path(__file__).resolve().parent
RUN_SCRIPT_PATH: Path = PROJECT_ROOT / 'run.py'
SETTINGS_PATH: Path = PROJECT_ROOT / 'data' / 'setting.json'
SERVICE_HEALTH_URL: str = (
    f"http://127.0.0.1:{GlobalConfig.SYSTEM_PORT}{GlobalConfig.SERVICE_CONTROL_HEALTH_PATH}"
)


@dataclass
class ServiceControlResult:
    """
    用途说明：表示一次服务控制操作的结果。
    入参说明：
        success (bool): 操作是否成功。
        pid (Optional[int]): 操作涉及的进程号，未运行时为 None。
        message (str): 已按当前语言生成的结果说明。
    返回值说明：无。
    """

    success: bool
    pid: Optional[int] = None
    message: str = ''


class ServiceControlError(Exception):
    """用途说明：表示服务控制过程中需要中止操作的业务异常。"""


class ServiceController:
    """用途说明：管理本项目 run.py 后端进程的生命周期并执行健康检查。"""

    @staticmethod
    def prepare_runtime() -> None:
        """
        用途说明：切换项目工作目录，并按系统配置初始化语言和后端日志。
        入参说明：无。
        返回值说明：无。
        """
        os.chdir(PROJECT_ROOT)
        I18nUtils.init('en')
        LogUtils.init(logging.INFO)

        language: str = 'en'
        try:
            with SETTINGS_PATH.open('r', encoding='utf-8') as settings_file:
                settings_data: dict[str, Any] = json.load(settings_file)
            user_data: Any = settings_data.get('USER_DATA', {})
            configured_language: Any = (
                user_data.get('language') if isinstance(user_data, dict) else None
            )
            if configured_language in ('zh', 'en'):
                language = configured_language
        except (OSError, ValueError, TypeError) as error:
            LogUtils.debug(t('service_control_settings_read_failed', error=str(error)))

        I18nUtils.init(language)

    @staticmethod
    def _get_port_owner_pids(port: int) -> set[int]:
        """
        用途说明：查询指定 TCP 端口当前正在监听的进程号。
        入参说明：port (int) - 系统后端端口，来自 GlobalConfig.SYSTEM_PORT。
        返回值说明：set[int] - 监听进程号集合；端口无监听时返回空集合。
        """
        try:
            connections: list[Any] = psutil.net_connections(kind='inet')
        except (psutil.AccessDenied, OSError) as error:
            raise ServiceControlError(
                t('service_control_connection_query_failed', error=str(error))
            ) from error

        owner_pids: set[int] = set()
        for connection in connections:
            if connection.status == psutil.CONN_LISTEN and connection.pid:
                if connection.laddr and connection.laddr.port == port:
                    owner_pids.add(connection.pid)
        return owner_pids

    @staticmethod
    def _is_project_run_process(process: psutil.Process, strict: bool = False) -> bool:
        """
        用途说明：校验进程是否为本项目根目录下 run.py 启动的后端进程。
        入参说明：
            process (psutil.Process) - 待检查的进程对象。
            strict (bool) - 端口占用进程信息不可读取时是否中止操作。
        返回值说明：bool - 属于本项目后端进程时返回 True。
        """
        try:
            command_line: list[str] = process.cmdline()
            working_directory: Path = Path(process.cwd()).resolve()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return False
        except (psutil.AccessDenied, OSError) as error:
            if strict:
                raise ServiceControlError(
                    t('service_control_process_inspect_failed', error=str(error))
                ) from error
            return False

        for argument in command_line:
            if not argument or Path(argument).name.lower() != 'run.py':
                continue
            script_path: Path = Path(argument)
            if not script_path.is_absolute():
                script_path = working_directory / script_path
            try:
                if script_path.resolve() == RUN_SCRIPT_PATH:
                    return True
            except OSError as error:
                if strict:
                    raise ServiceControlError(
                        t('service_control_process_inspect_failed', error=str(error))
                    ) from error
        return False

    @classmethod
    def find_service_processes(cls) -> list[psutil.Process]:
        """
        用途说明：查找本项目后端进程，并拒绝把同端口的其他程序当作后端。
        入参说明：无。
        返回值说明：list[psutil.Process] - 本项目后端进程列表；未运行时返回空列表。
        """
        owner_pids: set[int] = cls._get_port_owner_pids(GlobalConfig.SYSTEM_PORT)
        matched_processes: dict[int, psutil.Process] = {}

        for pid in owner_pids:
            try:
                process: psutil.Process = psutil.Process(pid)
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            if cls._is_project_run_process(process, strict=True):
                matched_processes[pid] = process

        if owner_pids and not matched_processes:
            raise ServiceControlError(
                t('service_control_port_occupied', port=GlobalConfig.SYSTEM_PORT)
            )

        try:
            process_candidates: Any = psutil.process_iter(attrs=['pid'])
        except (psutil.AccessDenied, OSError) as error:
            raise ServiceControlError(
                t('service_control_process_inspect_failed', error=str(error))
            ) from error

        for candidate in process_candidates:
            candidate_info: Optional[dict[str, Any]] = candidate.info
            candidate_pid: Optional[int] = candidate_info.get('pid') if candidate_info else None
            if candidate_pid is None or candidate_pid in matched_processes:
                continue
            try:
                process = psutil.Process(candidate_pid)
                if cls._is_project_run_process(process):
                    matched_processes[candidate_pid] = process
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue

        return [matched_processes[pid] for pid in sorted(matched_processes)]

    @staticmethod
    def _terminate_process(process: psutil.Process) -> None:
        """
        用途说明：先请求进程退出，超时后强制结束，并等待进程完全退出。
        入参说明：process (psutil.Process) - 需要停止的后端进程。
        返回值说明：无。
        """
        if not process.is_running():
            return

        process.terminate()
        try:
            process.wait(timeout=GlobalConfig.SERVICE_CONTROL_STOP_TIMEOUT)
            return
        except psutil.TimeoutExpired:
            process.kill()

        try:
            process.wait(timeout=GlobalConfig.SERVICE_CONTROL_STOP_TIMEOUT)
        except psutil.TimeoutExpired as error:
            raise ServiceControlError(
                t(
                    'service_control_stop_timeout',
                    timeout=GlobalConfig.SERVICE_CONTROL_STOP_TIMEOUT,
                )
            ) from error

    @classmethod
    def stop(cls) -> ServiceControlResult:
        """
        用途说明：停止本项目的全部后端进程；未运行时视为停止成功。
        入参说明：无。
        返回值说明：ServiceControlResult - 停止结果及进程号。
        """
        processes: list[psutil.Process] = cls.find_service_processes()
        if not processes:
            return ServiceControlResult(True, None, t('service_control_not_running'))

        stopped_pids: list[int] = []
        for process in processes:
            pid: int = process.pid
            LogUtils.info(t('service_control_stopping', pid=pid))
            cls._terminate_process(process)
            stopped_pids.append(pid)

        return ServiceControlResult(True, stopped_pids[-1], t('service_control_stop_success'))

    @staticmethod
    def _wait_for_health(process: subprocess.Popen) -> None:
        """
        用途说明：轮询公开版本接口，直到后端健康或本次启动超时。
        入参说明：process (subprocess.Popen) - 本次启动的后端子进程。
        返回值说明：无；进程提前退出或健康检查超时时抛出 ServiceControlError。
        """
        deadline: float = time.monotonic() + GlobalConfig.SERVICE_CONTROL_START_TIMEOUT
        last_error: Optional[Exception] = None

        while time.monotonic() < deadline:
            exit_code: Optional[int] = process.poll()
            if exit_code is not None:
                raise ServiceControlError(
                    t('service_control_process_exited', code=exit_code)
                )

            try:
                with urllib.request.urlopen(SERVICE_HEALTH_URL, timeout=1.0) as response:
                    status_code: Optional[int] = getattr(response, 'status', None)
                    if status_code == 200:
                        return
                    last_error = ServiceControlError(
                        t('service_control_health_bad_status', status=status_code)
                    )
            except (urllib.error.URLError, OSError, ValueError) as error:
                last_error = error

            time.sleep(0.25)

        raise ServiceControlError(
            t('service_control_health_timeout', error=str(last_error or ''))
        )

    @classmethod
    def start(cls) -> ServiceControlResult:
        """
        用途说明：以独立后台进程启动 run.py，并等待版本接口健康检查通过。
        入参说明：无。
        返回值说明：ServiceControlResult - 启动结果及新进程号。
        """
        existing_processes: list[psutil.Process] = cls.find_service_processes()
        if existing_processes:
            pid: int = existing_processes[0].pid
            return ServiceControlResult(
                True, pid, t('service_control_already_running', pid=pid)
            )

        LogUtils.info(t('service_control_starting'))
        if os.name == 'nt':
            creation_flags: int = (
                getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
                | getattr(subprocess, 'DETACHED_PROCESS', 0)
            )
            process: subprocess.Popen = subprocess.Popen(
                [sys.executable, str(RUN_SCRIPT_PATH)],
                cwd=str(PROJECT_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
        else:
            process = subprocess.Popen(
                [sys.executable, str(RUN_SCRIPT_PATH)],
                cwd=str(PROJECT_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        try:
            cls._wait_for_health(process)
        except ServiceControlError:
            try:
                cls._terminate_process(process)
            except Exception as cleanup_error:
                LogUtils.error(t('service_control_failed', error=str(cleanup_error)))
            raise

        return ServiceControlResult(
            True,
            process.pid,
            t('service_control_start_success', pid=process.pid),
        )

    @classmethod
    def restart(cls) -> ServiceControlResult:
        """
        用途说明：先停止现有后端，再启动新后端并等待健康检查通过。
        入参说明：无。
        返回值说明：ServiceControlResult - 重启结果及新进程号。
        """
        cls.stop()
        result: ServiceControlResult = cls.start()
        return ServiceControlResult(
            True,
            result.pid,
            t('service_control_restart_success', pid=result.pid),
        )


def run_service_control(action: str) -> int:
    """
    用途说明：执行停止或重启操作，并统一记录结果与异常日志。
    入参说明：action (str) - 操作名称，支持 stop 或 restart。
    返回值说明：int - 成功返回 0，失败返回 1。
    """
    try:
        ServiceController.prepare_runtime()
        controller: ServiceController = ServiceController()
        if action == 'stop':
            result: ServiceControlResult = controller.stop()
        elif action == 'restart':
            result = controller.restart()
        else:
            raise ServiceControlError(t('operation_failed', error=action))

        if result.success:
            LogUtils.info(result.message)
        else:
            LogUtils.error(result.message)
        return 0 if result.success else 1
    except Exception as error:
        LogUtils.error(t('service_control_failed', error=str(error)))
        return 1
