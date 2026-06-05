"""一次性脚本：把微信小程序注册到华师统一身份认证平台（文档 3.3.1）。

仅在接入申请通过、拿到 client_id/client_secret 后运行一次（每个应用只需注册一次）。
读取 .env 中的 SSO_* 与 WECHAT_* 配置。

用法：
    cd backend
    python register_sso_applet.py "你的小程序名称"

sign = MD5(applet_id + applet_name + applet_secret + client_id + timestamp + client_secret)
"""
import hashlib
import sys
import time

import httpx

from app.core.config import settings


def main(applet_name: str) -> None:
    if settings.sso_mock:
        print("当前 SSO_MOCK=true，无需注册。请先在 .env 配置真实凭据并关闭 mock。")
        return
    applet_id = settings.sso_applet_id or settings.wechat_appid
    applet_secret = settings.wechat_secret
    client_id = settings.sso_client_id
    client_secret = settings.sso_client_secret
    missing = [k for k, v in {
        "sso_applet_id/wechat_appid": applet_id,
        "wechat_secret": applet_secret,
        "sso_client_id": client_id,
        "sso_client_secret": client_secret,
    }.items() if not v]
    if missing:
        print("缺少配置：", ", ".join(missing))
        return

    timestamp = str(int(time.time() * 1000))  # 13 位毫秒时间戳
    raw = applet_id + applet_name + applet_secret + client_id + timestamp + client_secret
    sign = hashlib.md5(raw.encode("utf-8")).hexdigest()

    url = f"{settings.sso_base_url.rstrip('/')}/openapi/wechat_applet_reg.html"
    data = {
        "applet_id": applet_id,
        "applet_secret": applet_secret,
        "applet_name": applet_name,
        "client_id": client_id,
        "timestamp": timestamp,
        "sign": sign,
    }
    resp = httpx.post(url, data=data, timeout=10)
    resp.raise_for_status()
    print("注册结果：", resp.json())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python register_sso_applet.py \"小程序名称\"")
        sys.exit(1)
    main(sys.argv[1])
