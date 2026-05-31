# 实验室一体化管理智能体系统 · 设计方案

> 面向学院师生的实验室管理小程序：统一认证登录 → 场地预约 / 设备报修 / 业务咨询智能体。

## 1. 目标与范围

| 角色 | 能力 |
| --- | --- |
| 师生（普通用户） | 校园统一认证登录、查看实验室、预约空闲时段、提交/查看报修、咨询机器人 |
| 管理员 | 批量导入课表占用实验室、审批预约、流转报修维修进度、维护 FAQ 知识库 |

设计原则：**功能与界面尽量克制**。场地预约参考企业微信会议室（按日期看时段格子、点空闲格预约），报修参考共享表格（一行一单、状态流转）。

## 2. 总体架构

```
┌──────────────────────────┐      HTTPS / JSON       ┌────────────────────────────┐
│   微信小程序 (前端)        │  ───────────────────▶   │   FastAPI 后端              │
│  - 登录 (SSO + wx登录)    │  ◀───────────────────   │  - 鉴权 (JWT)               │
│  - 场地预约 (会议室视图)   │                          │  - 预约 / 报修 / 咨询 API    │
│  - 报修 (共享表格视图)     │                          │  - 课表导入 / 报修流转       │
│  - 业务咨询 (对话机器人)   │                          │  - AI 抽象层 (RAG + LLM)    │
│  - 管理后台 (页内)         │                          └───────────────┬─────────────┘
└──────────────────────────┘                                          │
                                                          ┌───────────▼───────────┐
                                                          │  数据库 (SQLite/MySQL) │
                                                          │  统一认证 CAS (校内)    │
                                                          │  LLM Provider (占位)   │
                                                          └────────────────────────┘
```

技术选型：

- **后端**：Python 3.10+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2，默认 SQLite（一键本地跑），生产可切 MySQL。
- **前端**：微信原生小程序（无额外框架，体积小、上手快）。
- **AI**：可插拔 `LLMProvider` + `Retriever` 抽象层，默认 Mock，后续接 Claude / 国内大模型只需实现接口。
- **鉴权**：登录态用 JWT（小程序本地存 token，请求带 `Authorization: Bearer`）。

## 3. 认证设计（关键）

学校统一认证 `https://sso.scnu.edu.cn/` 通常是 **CAS 协议**。完整流程：

```
小程序                     后端                       学校 CAS
  │  wx.login → code        │                            │
  │ ───────────────────────▶│ code2session→openid        │
  │                         │                            │
  │  打开 SSO 授权页(webview) │── service=后端回调 URL ────▶│
  │ ◀───────────────────────│◀── 重定向带 ticket ─────────│
  │                         │  serviceValidate(ticket)   │
  │                         │ ──────────────────────────▶│
  │                         │◀── 用户信息(学号/姓名/角色)──│
  │  ◀── 颁发 JWT ───────────│ 绑定 openid ↔ sso_id        │
```

落地策略（按本次选型「完整对接框架 + 本地模拟」）：

- `services/sso.py` 实现标准 CAS `login` 跳转 URL 构造 + `serviceValidate` XML 解析。
- 设 `SSO_MOCK=true` 时走本地模拟，返回可配置的测试用户，便于联调；拿到校内 `service` 注册与回调域名后改为 `false`。
- 同理 `services/wechat.py` 的 `code2session` 也支持 mock。

> 注意：CAS 的 `service` 回调地址必须在校内 SSO 后台登记，且小程序 webview 仅支持业务域名 https。生产部署时把后端回调域名配置进 `.env` 与小程序合法域名。

## 4. 数据模型

- **User** 用户：`sso_id`(学号/工号)、`name`、`role`(student/teacher/admin)、`college`、`openid`、`phone`
- **Room** 实验室：`name`、`location`、`capacity`、`description`、`open_time`/`close_time`、`is_active`
- **Booking** 预约：`room_id`、`user_id`、`start_time`、`end_time`、`purpose`、`status`、`source`(user/course)、`course_name`
  - 课表占用 = `source=course` 的预约记录（批量导入生成），与用户预约统一冲突检测。
- **Repair** 报修单：`room_id`、`device_name`、`description`、`images`、`reporter_id`、`handler_id`、`status`、`logs`(流转日志)
- **FAQ** 知识库：`question`、`answer`、`category`、`keywords` —— 供咨询机器人 RAG 检索。

状态机：

- 预约 `status`：`pending → approved / rejected`，用户可 `cancelled`。（可配置免审批直接 approved）
- 报修 `status`：`submitted → assigned → in_progress → done → closed`，每次流转写 `logs`。

## 5. 功能模块

### 5.1 场地预约（企业微信会议室式）
- 选实验室 + 日期 → 后端返回当天 0.5h 粒度时段的占用情况（含课表 & 已批预约）。
- 前端画时段格子，绿色可选、灰色占用；选连续空闲段提交预约。
- 后端按时间区间重叠检测冲突，原子写入。

### 5.2 设备报修（共享表格式）
- 列表页一行一单，显示设备/实验室/状态/时间，可筛选「我的/全部」。
- 提交：选实验室 + 设备名 + 描述 + 照片。
- 管理员在详情页流转状态并填写处理说明，用户看到进度时间线。

### 5.3 业务咨询（智能体）
- 对话式：用户提问 → `Retriever` 召回相关 FAQ → 拼进 prompt → `LLMProvider` 生成回答（带来源）。
- 当前 `MockLLMProvider` 返回基于检索的模板回答；接真实模型时替换 provider 即可。

### 5.4 管理员
- **课表批量导入**：上传 CSV/Excel（实验室/星期/节次/起止周/课程名），解析展开为多条 `course` 预约。
- **报修流转**：分配处理人、更新状态、记录日志。
- **FAQ 维护**：增删改知识库条目。
- **成员管理（角色授权）**：管理员可在后台检索用户、把师生**设为/取消管理员**。判定 admin 的唯一依据是 `User.role == "admin"`（后端 `get_current_admin` 实时查库）。两条赋权途径：
  - **白名单**：`ADMIN_SSO_IDS` 配置逗号分隔的学号/工号，命中者登录即自动 `admin`（解决"第一个管理员从哪来"，且不依赖学校返回的 userType）。
  - **后台 CRUD**：`PUT /api/admin/users/{id}/role`，已有管理员授权他人。防呆：不能取消自己、不能在后台降级白名单成员（应改配置）。
- **数据看板**：汇总待审批预约 / 待维修设备 / 今日预约 / 开放实验室数；展示待审批预约列表、报修状态分布、**高频咨询问题 Top N**（近 30 天，由 `ChatLog` 聚合）、实验室使用热度。
- **报表导出**：按时间段 + 状态 + 实验室 + 来源筛选，导出 **Excel(xlsx)**（预约报表 / 报修报表），含中文表头与列宽，前端 `wx.downloadFile` + `wx.openDocument` 直接预览/转发。

> 高频问题统计依赖 `ChatLog` 表：每次咨询记录提问与命中的 FAQ，看板按「命中问题（无命中则原文）」聚合计数。

## 6. 接口概览

| 模块 | 方法 & 路径 |
| --- | --- |
| 认证 | `POST /api/auth/wechat-login`、`GET /api/auth/sso/login-url`、`GET /api/auth/sso/callback`、`POST /api/auth/dev-login` |
| 实验室 | `GET /api/rooms`、`GET /api/rooms/{id}`、`GET /api/rooms/{id}/availability?date=` |
| 预约 | `POST /api/bookings`、`GET /api/bookings/mine`、`POST /api/bookings/{id}/cancel` |
| 报修 | `POST /api/repairs`、`GET /api/repairs`、`GET /api/repairs/{id}` |
| 咨询 | `POST /api/chat` |
| 管理 | `GET /api/admin/bookings`、`POST /api/admin/bookings/{id}/review`、`POST /api/admin/repairs/{id}/transition`、`POST /api/admin/schedules/import`、FAQ CRUD |
| 看板/报表 | `GET /api/admin/dashboard`、`GET /api/admin/reports/bookings.xlsx`、`GET /api/admin/reports/repairs.xlsx`（均支持 `start`/`end`/`status` 等筛选） |
| 成员管理 | `GET /api/admin/users?keyword=&role=`、`PUT /api/admin/users/{id}/role` |

## 7. 目录结构

```
backend/
  app/
    main.py            # FastAPI 入口
    core/config.py     # 配置
    core/database.py   # DB 引擎/Session
    core/security.py   # JWT
    core/deps.py       # 依赖注入(当前用户/管理员)
    models/            # ORM 模型
    schemas/           # Pydantic DTO
    services/          # sso / wechat / booking / repair / schedule / ai
    api/               # 路由
  seed.py              # 初始化演示数据
  requirements.txt
miniprogram/           # 微信小程序
  pages/{index,login,booking,repair,chat,profile,admin,...}
```

## 8. 部署与安全要点
- `.env` 管理密钥（JWT secret、微信 AppID/Secret、SSO service、LLM key），勿入库。
- 小程序合法域名需备案 https；CAS service 回调需校内登记。
- 鉴权全部走 JWT 中间件；管理员接口二次校验 `role=admin`。
- 后续可加：Redis 缓存时段、异步任务发报修通知、操作审计日志。
