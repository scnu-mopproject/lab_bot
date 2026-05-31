from pydantic import BaseModel


class WechatLoginIn(BaseModel):
    code: str  # wx.login 拿到的 code
    # 可选：从 SSO 回调换得的临时凭证，用于绑定 sso 身份
    sso_token: str | None = None


class DevLoginIn(BaseModel):
    """本地调试登录（仅 mock 模式可用）。"""
    sso_id: str
    name: str = "测试用户"
    role: str = "student"
    college: str | None = "计算机学院"


class UserOut(BaseModel):
    id: int
    sso_id: str
    name: str
    role: str
    college: str | None = None
    phone: str | None = None

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
