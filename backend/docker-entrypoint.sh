#!/usr/bin/env bash
# 容器启动脚本：初始化演示数据（幂等）后启动 Uvicorn。
set -e

echo "==> 初始化数据库 / 演示数据（幂等）"
python seed.py

echo "==> 启动服务：0.0.0.0:8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
