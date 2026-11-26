"""用途说明：系统后端重启入口，对应 run.py 的启动入口。"""

import sys

from service_control import run_service_control


def main() -> int:
    """
    用途说明：停止现有后端并重新启动，等待版本接口健康检查通过。
    入参说明：无。
    返回值说明：int - 重启成功返回 0，失败返回 1。
    """
    return run_service_control('restart')


if __name__ == '__main__':
    sys.exit(main())
