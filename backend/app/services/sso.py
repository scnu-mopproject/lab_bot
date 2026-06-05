"""华南师范大学统一身份认证平台对接（OAuth2.0）。

依据《华南师范大学统一身份认证平台接入说明文档》实现。
[认证服务地址] = settings.sso_base_url（生产：https://sso.scnu.edu.cn/AccountService）

登录流程（小程序场景 3.2.1 / Web 场景 2.1.1）：
1. 小程序 wx.login 取得微信 code；用 web-view 打开 `applet_login_url(code)` 指向的
   /openapi/wechat_applet.html，或 Web 应用浏览器跳转 `web_login_url()` 指向的
   /openapi/auth.html；
2. 用户在统一认证平台登录后，平台回调 redirect_uri 并带回一次性 `code`（有效 5 分钟）；
3. 后端用该 code 调 /openapi/token.html 换 access_token（`exchange_token`）；
4. 后端用 access_token 调 /openapi/userinfo.html 取用户信息（`fetch_userinfo`）；
5. 映射为本系统用户（account→学工号，dept→学院，kindCode→角色）。

环境切换：mock(本地) / 测试 / 生产 仅由 .env 决定，代码不变。
设 SSO_MOCK=true 时全程走本地模拟，便于在拿到 client_id/secret 前联调业务。
"""
from urllib.parse import urlencode

import httpx

from app.core.config import settings

# 成功状态码：token/userinfo 文档为 "00"，部分接口为 "0"，统一兼容。
_OK_CODES = {"0", "00"}


class SSOUser:
    def __init__(self, sso_id: str, name: str, role: str = "student",
                 college: str | None = None, openid: str | None = None):
        self.sso_id = sso_id
        self.name = name
        self.role = role
        self.college = college
        self.openid = openid


def _endpoint(path: str) -> str:
    return f"{settings.sso_base_url.rstrip('/')}/openapi/{path}"


def _map_role(kind_code: str) -> str:
    """按 kindCode 前四位映射角色（文档 2.3.3.1）。

    1001 在职教职工 / 1002 其他教职工 -> teacher
    1003 在校学生   / 1004 其他学生   -> student
    其余（1005 其他用户 / 1006 上网用户等）保守按 student 处理。
    kindCode 少于四位的用户文档规定不予授权。
    """
    prefix = (kind_code or "")[:4]
    if len(prefix) < 4:
        raise ValueError(f"用户身份不予授权（kindCode={kind_code!r}）")
    return {
        "1001": "teacher",
        "1002": "teacher",
        "1003": "student",
        "1004": "student",
    }.get(prefix, "student")


# ----------------------------------------------------------------------------
# 1) 构造登录入口 URL
# ----------------------------------------------------------------------------

def applet_login_url(wx_code: str, state: str | None = None) -> str:
    """小程序登录（文档 3.3.2）：返回用于 web-view 打开的统一认证地址。

    wx_code 为小程序 wx.login 拿到的临时登录凭证。
    """
    params = {
        "client_id": settings.sso_client_id,
        "response_type": "code",
        "redirect_uri": settings.sso_service_url,
        "code": wx_code,
        "applet_id": settings.sso_applet_id,
    }
    if state:
        params["forward"] = state
    return f"{_endpoint('wechat_applet.html')}?{urlencode(params)}"


def web_login_url(state: str | None = None) -> str:
    """Web 应用登录（文档 2.3.1）：浏览器跳转地址。"""
    params = {
        "client_id": settings.sso_client_id,
        "response_type": "code",
        "redirect_uri": settings.sso_service_url,
    }
    if state:
        params["forward"] = state
    return f"{_endpoint('auth.html')}?{urlencode(params)}"


# ----------------------------------------------------------------------------
# 2) 回调后：code -> access_token -> 用户信息
# ----------------------------------------------------------------------------

async def exchange_token(code: str) -> str:
    """用回调拿到的 code 换 access_token（文档 2.3.2）。"""
    data = {
        "code": code,
        "client_id": settings.sso_client_id,
        "client_secret": settings.sso_client_secret,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(_endpoint("token.html"), data=data)
        resp.raise_for_status()
        payload = resp.json()
    if str(payload.get("msgcode")) not in _OK_CODES:
        raise ValueError(f"获取 access_token 失败：{payload.get('msgtext') or payload}")
    return payload["access_token"]


async def fetch_userinfo(access_token: str) -> dict:
    """用 access_token 取用户信息（文档 2.3.3）。"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(_endpoint("userinfo.html"), data={"access_token": access_token})
        resp.raise_for_status()
        payload = resp.json()
    if str(payload.get("msgcode")) not in _OK_CODES:
        raise ValueError(f"获取用户信息失败：{payload.get('message') or payload}")
    return payload


async def authenticate(code: str) -> SSOUser:
    """完整流程：code -> token -> userinfo -> 映射为 SSOUser。

    mock 模式下直接返回模拟用户（code 即作 sso_id 派生），无需任何凭据。
    """
    if settings.sso_mock:
        return SSOUser(sso_id=f"mock-{code}", name="模拟用户", role="student",
                       college="人工智能学院", openid=None)

    access_token = await exchange_token(code)
    info = await fetch_userinfo(access_token)
    account = info.get("account")
    if not account:
        raise ValueError("用户信息缺少 account（学工号）")
    return SSOUser(
        sso_id=account,
        name=info.get("name") or account,
        role=_map_role(info.get("kindCode", "")),
        college=info.get("dept"),
        openid=info.get("openid"),
    )
