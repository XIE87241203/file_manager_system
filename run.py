import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.main import start_server

if __name__ == "__main__":
    """
    用途说明：项目统一启动入口。
    入参说明：无
    返回值说明：无
    """
    try:
        # 直接调用后端定义的启动函数，不再使用 subprocess，减少进程管理复杂性
        start_server()
    except KeyboardInterrupt:
        print("\n[系统] 正在退出...")
        sys.exit(0)
