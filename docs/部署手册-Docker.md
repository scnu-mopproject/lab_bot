# 后端部署手册（Docker Compose / 自测免备案版）

本手册用于把 **lab_bot 后端**部署到一台云服务器，供微信开发者工具「真机调试」联调。
当前为**自测阶段**：保持 mock 模式、用公网 IP 直连、关闭小程序域名校验，**无需备案/HTTPS**。

---

## 一、准备云服务器

推荐 **腾讯云轻量应用服务器（Lighthouse）2核2G**，或阿里云同档轻量服务器；
SCNU 学生可用「学生服务器」(1核2G 也够自测)。

- 系统镜像：优先选 **「Docker」应用镜像**（自带 Docker，省去安装）；
  若选的是纯 Ubuntu 22.04，安装 Docker：
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```
- **放行端口**：在云厂商控制台「防火墙 / 安全组」放行 **TCP 8000**（自测用）。

---

## 二、拉取代码

服务器上执行（云服务器访问 GitHub 通常没问题）：

```bash
git clone -b claude/stoic-curie-0ul8L https://github.com/scnu-mopproject/lab_bot.git
cd lab_bot
```

> 若访问 GitHub 慢，可在本机打包后用 `scp` 上传，再解压。

---

## 三、配置环境变量

```bash
cp backend/.env.docker.example backend/.env
```

自测保持默认即可（全 mock、`ADMIN_SSO_IDS=admin`）。
> 注意：`DATABASE_URL` **不要**在 .env 里设置——镜像已固定指向数据卷 `/app/data/lab_bot.db`。

---

## 四、启动

在仓库根目录（有 `docker-compose.yml` 处）：

```bash
docker compose up -d --build
```

查看状态 / 日志：

```bash
docker compose ps
docker compose logs -f backend
```

---

## 五、验证

```bash
curl http://localhost:8000/health
# 期望：{"status":"ok","app":"lab_bot"}
```

浏览器访问 `http://你的公网IP:8000/docs` 能看到接口文档即成功。
若打不开：检查云厂商**安全组是否放行 8000**、`docker compose ps` 是否 Up。

---

## 六、小程序真机调试配置

1. 修改 `miniprogram/app.js` 里的 `baseUrl` 为 `http://你的公网IP:8000`。
2. 微信开发者工具 → **详情 → 本地设置 → 勾选「不校验合法域名…」**。
3. 点 **真机调试**（不是普通预览）→ 手机扫码联调。

---

## 七、常用运维命令

```bash
# 更新代码后重新部署
git pull && docker compose up -d --build

# 停止 / 重启
docker compose down
docker compose restart

# 备份数据库（SQLite 单文件）
cp backend/data/lab_bot.db backend/data/lab_bot.db.bak
```

数据持久化在宿主机 `backend/data/` 目录，容器重建不丢数据。

---

## 八、安全提醒（重要）

- 当前 mock 模式下，任何知道你 IP 的人都能调用后端。**自测无妨，勿放真实敏感数据。**
- 对外/长期上线前请：
  - 关闭各 `*_MOCK`、填真实凭据；
  - 把 `JWT_SECRET` 换成随机串（`openssl rand -hex 32`）；
  - 前置 Nginx + HTTPS、配置业务域名并完成备案；
  - 安全组收敛端口、按需开放。
