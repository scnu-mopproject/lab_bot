from pydantic import BaseModel


class MemberOut(BaseModel):
    id: int
    sso_id: str
    name: str
    role: str
    college: str | None = None
    phone: str | None = None
    is_whitelisted: bool = False  # 是否在管理员白名单（白名单成员不可在后台降级）

    model_config = {"from_attributes": True}


class RoleUpdate(BaseModel):
    role: str  # student / teacher / admin
