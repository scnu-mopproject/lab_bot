"""学校统一认证 (CAS) 对接。

完整 CAS 流程：
1. 前端打开 `login_url()`（带 service 回调），用户在 sso.scnu.edu.cn 登录；
2. SSO 重定向回 service?ticket=ST-xxx；
3. 后端用 `validate(ticket)` 调 /serviceValidate 校验并解析用户信息。

设 SSO_MOCK=true 时走本地模拟，便于在拿到校内 service 注册前联调。
"""
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

import httpx

from app.core.config import settings

CAS_NS = {"cas": "http://www.yale.edu/tp/cas"}


class SSOUser:
    def __init__(self, sso_id: str, name: str, role: str = "student", college: str | None = None):
        self.sso_id = sso_id
        self.name = name
        self.role = role
        self.college = college


def login_url(state: str | None = None) -> str:
    """构造跳转到学校统一认证的登录 URL。"""
    service = settings.sso_service_url
    if state:
        service = f"{service}?{urlencode({'state': state})}"
    params = {"service": service}
    return f"{settings.sso_base_url}/cas/login?{urlencode(params)}"


async def validate(ticket: str) -> SSOUser:
    """校验 CAS ticket，返回用户信息。"""
    if settings.sso_mock:
        # 本地模拟：ticket 即 sso_id，便于联调
        return SSOUser(sso_id=f"mock-{ticket}", name="模拟用户", role="student", college="计算机学院")

    url = f"{settings.sso_base_url}/cas/serviceValidate"
    params = {"service": settings.sso_service_url, "ticket": ticket}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return _parse_validate_xml(resp.text)


def _parse_validate_xml(xml_text: str) -> SSOUser:
    root = ET.fromstring(xml_text)
    success = root.find(".//cas:authenticationSuccess", CAS_NS)
    if success is None:
        raise ValueError("CAS 校验失败：ticket 无效")
    sso_id = success.findtext("cas:user", default="", namespaces=CAS_NS)
    attrs = success.find("cas:attributes", CAS_NS)
    name = sso_id
    role = "student"
    college = None
    if attrs is not None:
        name = attrs.findtext("cas:name", default=sso_id, namespaces=CAS_NS) or sso_id
        # 学校属性命名各异，这里按常见字段尝试；实际以校内文档为准
        utype = attrs.findtext("cas:userType", default="", namespaces=CAS_NS)
        role = "teacher" if utype in ("teacher", "faculty") else "student"
        college = attrs.findtext("cas:department", default=None, namespaces=CAS_NS)
    return SSOUser(sso_id=sso_id, name=name, role=role, college=college)
