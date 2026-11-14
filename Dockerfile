# syntax=docker/dockerfile:1
# 第一阶段：构建阶段 (Builder)
# 用途说明：安装编译工具并构建 Python 轮子 (wheels)，避免将编译工具链带入最终镜像
FROM python:3.11-slim AS builder

WORKDIR /app

# 设置环境变量，防止 python 产生 pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装编译所需的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并编译
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# 第二阶段：运行阶段 (Runtime)
# 用途说明：仅包含运行程序所需的最小环境和库
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ARG USER_ID=1000
ARG GROUP_ID=1000

WORKDIR /app

# 仅安装运行时必需的系统库（移除 gcc 和 python3-dev）
# libstdc++6: opencv-python-headless 的 cv2 动态库依赖（DT_NEEDED 含 libstdc++.so.6）
# 说明：改用 headless 版 OpenCV 后无需 GUI 库（libgl1/libglib2.0-0/libxcb1）；
#       文件类型检测按扩展名实现，无需 libmagic1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g ${GROUP_ID} appgroup \
    && useradd -l -u ${USER_ID} -g appgroup -m appuser

# 通过 BuildKit 临时挂载构建阶段的 wheels 并安装，避免将 wheel 安装包固化进镜像层（节省约 77MB）
COPY requirements.txt .
RUN --mount=from=builder,source=/app/wheels,target=/wheels \
    pip install --no-cache-dir /wheels/*

# 复制项目代码
COPY --chown=appuser:appgroup backend/ ./backend/
COPY --chown=appuser:appgroup frontend/ ./frontend/
COPY --chown=appuser:appgroup config.py run.py ./

# 创建并授权数据目录
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

USER appuser

EXPOSE 5000 8080

CMD ["python", "run.py"]
