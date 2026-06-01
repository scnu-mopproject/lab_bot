#!/usr/bin/env bash
# 本机一键启动后端（SQLite + 全 mock 模式），供微信开发者工具联调。
# 用法：  cd backend && bash run_local.sh
set -e
cd "$(dirname "$0")"

PY=python3
if [ ! -d ".venv" ]; then
  echo "==> 创建虚拟环境"
  $PY -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> 安装依赖"
pip install -q -r requirements.txt

# 生成默认 .env（若不存在）：本机预览用全 mock，管理员白名单含 admin
if [ ! -f ".env" ]; then
  echo "==> 生成 .env（本机预览默认配置）"
  cat > .env <<'ENV'
DATABASE_URL=sqlite:///./lab_bot.db
JWT_SECRET=local-dev-secret
WECHAT_MOCK=true
SSO_MOCK=true
BOOKING_AUTO_APPROVE=true
ADMIN_SSO_IDS=admin
LLM_PROVIDER=mock
ENV
fi

echo "==> 初始化演示数据（管理员/实验室/FAQ）"
$PY seed.py

echo "==> 启动服务： http://localhost:8000/docs  (Ctrl+C 退出)"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
