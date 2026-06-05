"""认证路由：微信登录、SSO 登录、开发登录。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import DevLoginIn, TokenOut, UserOut, WechatLoginIn
from app.services import sso, wechat

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_token(user: User) -> TokenOut:
    token = create_access_token(user.id, extra={"role": user.role})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


def _upsert_user(db: Session, *, sso_id: str, name: str, role: str,
                 college: str | None, openid: str | None) -> User:
    # 白名单优先：命中者一律 admin（确保后续把人加进白名单后，其下次登录即被提升）
    whitelisted = sso_id in settings.admin_sso_id_set
    user = db.scalar(select(User).where(User.sso_id == sso_id))
    if not user:
        user = User(sso_id=sso_id, name=name, role="admin" if whitelisted else role, college=college)
        db.add(user)
    else:
        user.name = name or user.name
        if college:
            user.college = college
        if whitelisted and user.role != "admin":
            user.role = "admin"
    if openid:
        user.openid = openid
    db.commit()
    db.refresh(user)
    return user


@router.get("/sso/login-url")
def sso_login_url(state: str | None = None):
    """Web 应用统一认证登录地址（浏览器跳转，文档场景 2.1.1）。"""
    return {"url": sso.web_login_url(state=state)}


@router.get("/sso/applet-login-url")
def sso_applet_login_url(code: str, state: str | None = None):
    """小程序统一认证登录地址（文档场景 3.2.1）。

    code 为小程序 wx.login 拿到的临时登录凭证；返回的 url 由前端用 web-view 打开。
    """
    return {"url": sso.applet_login_url(code, state=state)}


@router.get("/sso/callback")
async def sso_callback(code: str, forward: str | None = None, db: Session = Depends(get_db)):
    """统一认证回调（OAuth2）：用 code 换 token、取用户信息，绑定/创建用户并签发 JWT。"""
    try:
        sso_user = await sso.authenticate(code)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"统一认证校验失败: {e}")
    user = _upsert_user(db, sso_id=sso_user.sso_id, name=sso_user.name,
                        role=sso_user.role, college=sso_user.college, openid=sso_user.openid)
    token = _issue_token(user)
    # 重定向回小程序 web-view 中转页，把 token 带回（前端在该页将 token 传回小程序后关闭 web-view）
    return RedirectResponse(url=f"/sso-bridge?token={token.access_token}", status_code=302)


@router.post("/wechat-login", response_model=TokenOut)
async def wechat_login(body: WechatLoginIn, db: Session = Depends(get_db)):
    """微信登录：用 code 换 openid。若已绑定 SSO 身份则直接登录，否则需先完成 SSO。"""
    openid = await wechat.code2session(body.code)
    user = db.scalar(select(User).where(User.openid == openid))
    if not user:
        raise HTTPException(404, "尚未绑定校园身份，请先完成统一认证登录")
    return _issue_token(user)


@router.post("/dev-login", response_model=TokenOut)
def dev_login(body: DevLoginIn, db: Session = Depends(get_db)):
    """本地调试登录，仅在 SSO_MOCK=true 时可用。"""
    if not settings.sso_mock:
        raise HTTPException(403, "仅在 mock 模式下可用")
    user = _upsert_user(db, sso_id=body.sso_id, name=body.name, role=body.role,
                        college=body.college, openid=None)
    return _issue_token(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
