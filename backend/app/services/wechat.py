"""微信小程序登录：code2session 换取 openid。"""
import hashlib

import httpx

from app.core.config import settings


async def code2session(code: str) -> str:
    """用 wx.login 的 code 换 openid。mock 模式下用 code 派生稳定 openid。"""
    if settings.wechat_mock:
        return "openid-" + hashlib.md5(code.encode()).hexdigest()[:16]

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if "openid" not in data:
            raise ValueError(f"微信登录失败: {data}")
        return data["openid"]
