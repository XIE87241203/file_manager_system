"""用途说明：系统后端停止入口，对应 run.py 的启动入口。"""

import sys

from service_control import run_service_control


def main() -> int:
    """
    用途说明：停止当前项目 run.py 启动的后端进程。
    入参说明：无。
    返回值说明：int - 停止成功或原本未运行时返回 0，失败返回 1。
    """
    return run_service_control('stop')


if __name__ == '__main__':
    sys.exit(main())
