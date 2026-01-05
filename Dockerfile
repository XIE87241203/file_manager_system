# 使用轻量级的 Python 基础镜像
FROM python:3.11-slim

# 定义参数，允许在构建时指定 UID 和 GID（默认 1000）
# 这样可以方便地与宿主机用户匹配，解决挂载卷的权限问题
ARG USER_ID=1000
ARG GROUP_ID=1000

# 设置环境变量
ENV PYTHONUNBUFFERED=1
# 将 /app 加入 PYTHONPATH，确保模块导入路径正确
ENV PYTHONPATH=/app

# 设置工作目录为 /app
WORKDIR /app

# 安装系统依赖并创建非 root 用户和组
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libglib2.0-0 \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g ${GROUP_ID} appgroup \
    && useradd -l -u ${USER_ID} -g appgroup -m appuser

# 1. 复制依赖文件并安装（以 root 身份安装，提高安全性）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. 复制项目代码并修改所有权
COPY --chown=appuser:appgroup backend/ ./backend/

# 3. 关键：预先创建数据目录并授权
# 这样程序在运行时就有权在 /app/data 下创建 setting.json
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# 切换到非 root 用户运行容器
USER appuser

# 暴露后端端口
EXPOSE 5000

# 启动命令
# 确保在 /app 目录下执行，这样 os.getcwd() 就会返回 /app
CMD ["python", "backend/main.py"]