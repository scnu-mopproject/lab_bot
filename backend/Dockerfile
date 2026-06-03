# 后端镜像：FastAPI + Uvicorn（SQLite 数据通过数据卷持久化）
FROM python:3.12-slim

# 让日志实时输出、关闭 pyc 缓存
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖（利用 Docker 层缓存：requirements 不变时不重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷贝源码
COPY . .

# SQLite 数据库放在数据卷目录，容器重建不丢数据
ENV DATABASE_URL=sqlite:////app/data/lab_bot.db
RUN mkdir -p /app/data

EXPOSE 8000

# 启动：先初始化演示数据（幂等），再起服务
ENTRYPOINT ["/app/docker-entrypoint.sh"]
