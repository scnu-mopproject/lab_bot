@echo off
REM 本机一键启动后端（Windows）。把本文件放在 backend\ 目录，双击或在该目录执行 run_local.bat
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 python，请先安装 Python 3.10+ 并勾选 Add Python to PATH
  echo 若你的命令是 py，可手动执行： py -m venv .venv
  pause
  exit /b 1
)

if not exist .venv (
  echo ==^> 创建虚拟环境
  python -m venv .venv
)
set PY=.venv\Scripts\python.exe

echo ==^> 安装依赖
"%PY%" -m pip install -q -r requirements.txt

if not exist .env (
  echo ==^> 生成 .env（本机预览默认配置）
  (
    echo DATABASE_URL=sqlite:///./lab_bot.db
    echo JWT_SECRET=local-dev-secret
    echo WECHAT_MOCK=true
    echo SSO_MOCK=true
    echo BOOKING_AUTO_APPROVE=true
    echo ADMIN_SSO_IDS=admin
    echo LLM_PROVIDER=mock
  ) > .env
)

echo ==^> 初始化演示数据
"%PY%" seed.py

echo ==^> 启动服务： http://localhost:8000/docs   (按 Ctrl+C 退出)
"%PY%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
