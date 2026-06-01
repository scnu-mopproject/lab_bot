# 本机预览指南（无需服务器 / 无需备案）

目标：在你自己的电脑上，用**微信开发者工具 + 本机后端**完整体验小程序，**不需要云服务器，也不需要域名备案**。

> 备案/服务器只在你要发布「体验版/正式版」或用真机访问非 localhost 的 HTTPS 域名时才需要（见末尾「进阶」）。开发者工具的「开发版」可关闭域名校验，直接访问本机后端。

---

## 〇、获取代码（首次）

代码都在分支 **`claude/stoic-curie-0ul8L`**（`main` 目前仅有 README），clone 后务必切到该分支：

```bash
git clone https://github.com/scnu-mopproject/lab_bot.git
cd lab_bot
git checkout claude/stoic-curie-0ul8L
```

## 一、启动后端（1 条命令）

需要本机已装 **Python 3.10+**。

```bash
cd backend
bash run_local.sh
```

脚本会自动：建虚拟环境 → 装依赖 → 生成本机用 `.env`（全 mock）→ 写入演示数据 → 启动服务。

成功后访问 **http://localhost:8000/docs** 应能看到接口文档（这本身就是一个可交互的"固定地址"）。

> 在 `/docs` 里验证：先调 `POST /api/auth/dev-login`（body 填 `{"sso_id":"admin","name":"管理员","role":"admin"}`）拿到 `access_token` → 点页面右上角 **Authorize**、粘贴该 token → 之后所有需要登录的接口（rooms / bookings / dashboard / reports 等）都可直接点 **Try it out** 调用。

> Windows 无 bash 时，手动执行：
> ```
> cd backend
> python -m venv .venv && .venv\Scripts\activate
> pip install -r requirements.txt
> python seed.py
> uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
> ```

演示数据：管理员 `sso_id=admin`、3 个实验室、5 条 FAQ。

---

## 二、打开小程序（微信开发者工具）

1. 下载安装 **微信开发者工具**（稳定版）。
2. 新建/导入项目：
   - 目录选 **`miniprogram/`**
   - **AppID** 填你已有的那个（未备案不影响开发版预览）
3. **关键开关**（否则连不上本机后端）：
   右上角 **详情 → 本地设置 →** 勾选
   **「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**
4. 确认 `miniprogram/app.js` 里 `baseUrl` 为 **`http://localhost:8000`**（默认即是）。
5. 编译。进入登录页 → 点 **「开发者调试入口」** → 输入：
   - 学号/工号：`admin`，角色选 **管理员** → 调试登录
   - 即可进入并在「我的 → 管理后台」看到看板/审批/报修/成员/课表/知识库/报表。
   - 想体验学生视角：换 `sso_id=任意`、角色选学生重新登录。

至此，预约、报修、咨询、看板、报表、成员管理全部可点可用。

---

## 三、用真机预览（可选）

模拟器用 `localhost` 即可；**真机**访问不到你电脑的 `localhost`，需把后端临时暴露到公网：

1. 用**内网穿透**工具（如 cpolar / ngrok / frp）把本机 `8000` 端口映射成一个临时 https 地址，例如 `https://xxxx.cpolar.io`。
2. 把 `app.js` 的 `baseUrl` 改成该地址。
3. 开发者工具仍保持「不校验合法域名」勾选，点 **预览 / 真机调试**，手机微信扫码即可。

> 真机「预览/真机调试」属于开发版，同样不需要备案；只有「上传 → 体验版/正式版」才需要备案域名。

---

## 四、进阶：要让师生扫码体验版 / 正式上线时

此时才需要服务器 + 备案：

1. **服务器**：一台带公网 IP 的 Linux（云服务器），部署后端。
2. **HTTPS 域名 + ICP 备案**：配置到小程序后台「开发设置 → 服务器域名」的 request 合法域名。
3. 把 `baseUrl` 指向该域名，开发者工具「上传」→ 提交体验版/审核。
4. 生产环境记得：`SSO_MOCK=false`、`WECHAT_MOCK=false`、填真实 `WECHAT_APPID/SECRET`，并对接学校 CAS。

需要这一步时，告诉我服务器厂商，我直接产出 Dockerfile + docker-compose + Nginx 部署物料。
