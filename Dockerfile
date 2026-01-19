# 使用轻量级的 Python 3.11 基础镜像
FROM python:3.11-slim

# 用途说明：定义构建参数，用于匹配宿主机用户 UID/GID，解决挂载卷的权限冲突
ARG USER_ID=1000
ARG GROUP_ID=1000

# 设置环境变量
# PYTHONUNBUFFERED=1：确保 Python 日志能够实时输出到容器控制台
ENV PYTHONUNBUFFERED=1
# PYTHONPATH=/app：将项目根目录加入模块搜索路径，确保 backend 等包导入正常
ENV PYTHONPATH=/app

# 设置容器内的工作目录
WORKDIR /app

# 用途说明：安装后端运行所需的系统依赖
# libmagic1: 用于文件类型检测
# libglib2.0-0, libxcb1, libgl1: 用于 OpenCV 等图像处理库的运行环境
# gcc, python3-dev: 用于部分 Python 库的编译
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libglib2.0-0 \
    libxcb1 \
    libgl1 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g ${GROUP_ID} appgroup \
    && useradd -l -u ${USER_ID} -g appgroup -m appuser

# 步骤 1：复制依赖文件并安装 Python 依赖库
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 步骤 2：复制项目代码并修改所有者为非 root 用户
# 复制后端代码
COPY --chown=appuser:appgroup backend/ ./backend/
# 复制前端代码（用于 run.py 启动 http.server）
COPY --chown=appuser:appgroup frontend/ ./frontend/
# 复制全局配置文件和启动入口
COPY --chown=appuser:appgroup config.py run.py ./

# 步骤 3：预先创建并授权数据目录
# 用途说明：确保程序运行时有权限在 /app/data 下读写配置文件及数据库
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# 切换到非 root 用户运行，提升安全性
USER appuser

# 暴露服务端口
# 5000: 后端 API 端口
# 8080: 前端静态服务端口
EXPOSE 5000 8080

# 启动命令
# 用途说明：执行根目录下的启动脚本，该脚本将同时拉起前后端服务。
CMD ["python", "run.py"]
