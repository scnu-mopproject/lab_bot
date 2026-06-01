# lab_bot · 实验室一体化管理智能体系统

面向学院师生的实验室管理微信小程序：**校园统一认证登录 → 场地预约 / 设备报修 / 业务咨询智能体**。

- 场地预约参考企业微信「会议室」：按日期看半小时时段格子，点空闲格预约。
- 设备报修参考「共享表格」：一行一单，管理员流转维修进度。
- 业务咨询为对话机器人，基于 RAG（FAQ 知识库）+ 可插拔大模型。
- 管理员可批量导入课表占用实验室、审批预约、流转报修、维护知识库。

> 详细设计见 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 目录结构

```
backend/        FastAPI 后端（API、鉴权、预约/报修/咨询、课表导入）
  app/          应用代码（core / models / schemas / services / api）
  seed.py       初始化演示数据
  tests/        冒烟测试
miniprogram/    微信原生小程序（场地预约/报修/咨询/我的/管理后台）
docs/DESIGN.md  设计方案
```

## 快速开始（后端）

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 按需修改；默认 SQLite + 全 mock 模式
python seed.py                # 写入管理员(sso_id=admin)、3 个实验室、5 条 FAQ
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- 接口文档：http://localhost:8000/docs
- 运行测试：`pip install pytest && pytest`

### 配置要点（`.env`）

| 变量 | 说明 |
| --- | --- |
| `SSO_MOCK` | `true` 时统一认证走本地模拟，可用 `/api/auth/dev-login` 调试登录 |
| `WECHAT_MOCK` | `true` 时微信登录 code2session 走本地模拟 |
| `BOOKING_AUTO_APPROVE` | 预约是否免审批直接通过 |
| `ADMIN_SSO_IDS` | 管理员白名单（逗号分隔学工号），命中者登录即自动成为 admin；其余管理员由后台「成员管理」授权 |
| `LLM_PROVIDER` | `mock`/`claude`/`openai-compatible`，咨询机器人后端 |
| `SSO_SERVICE_URL` | CAS 回调地址，需在校内统一认证后台登记 |

## 快速开始（小程序）

> 想用微信开发者工具**零成本、免备案**看到完整运行效果，见 [`docs/RUN_LOCAL.md`](docs/RUN_LOCAL.md)。

1. 用微信开发者工具导入 `miniprogram/` 目录。
2. 修改 `miniprogram/app.js` 的 `baseUrl` 为后端地址（本地用局域网 IP，生产用已备案 https 域名）。
3. 调试阶段可在登录页「开发者调试入口」用学号/角色直接登录（需后端 `SSO_MOCK=true`）。
4. 管理员账号：用 `sso_id=admin`、角色选「管理员」登录即可进入管理后台。

## 上线前需替换

- **统一认证**：拿到校内 CAS `service` 注册与回调域名后，将 `SSO_MOCK=false`，确认 `services/sso.py` 的属性字段映射与学校一致。
- **微信登录**：填入真实 `WECHAT_APPID/SECRET`，`WECHAT_MOCK=false`。
- **AI**：选定大模型，配置 `LLM_PROVIDER` 与密钥；报修图片改为上传对象存储后存 URL。
- **数据库**：切换 `DATABASE_URL` 到 MySQL/Postgres，并引入 Alembic 迁移。
