"""泛微 OA SSO 单点登录接口"""
import logging

from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.services import sso as sso_service

router = APIRouter(prefix="/api/sso", tags=["SSO 单点登录"])
logger = logging.getLogger(__name__)


class SsoVerifyRequest(BaseModel):
    token: str


class SsoUrlRequest(BaseModel):
    loginid: str
    username: str
    dept: str = ""


class SsoOaLoginRequest(BaseModel):
    loginid: str
    username: str = ""
    dept: str = ""


class SsoOaPasswordLoginRequest(BaseModel):
    loginid: str  # OA 工号
    password: str  # OA 密码
    remember_me: bool = False  # 是否开启长期免密登录


@router.post("/oa-password-login", summary="OA 密码验证登录")
async def sso_oa_password_login(req: SsoOaPasswordLoginRequest, db: Session = Depends(get_db)):
    """通过 OA 密码验证用户身份，成功后签发 JWT。勾选记住我时额外生成长期免密令牌并种 Cookie。"""
    result = await sso_service.sso_login_by_password(
        db, req.loginid, req.password, req.remember_me,
    )
    resp = JSONResponse(content=result)
    resp.set_cookie(
        key="pms_token",
        value=result["access_token"],
        max_age=8 * 3600,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )
    # 勾选记住我：种长期 Cookie（SameSite=Lax，HTTP 环境可用，OA 链接跳转时自动携带）
    if req.remember_me and "remember_token" in result:
        resp.set_cookie(
            key="pms_remember",
            value=result["remember_token"],
            max_age=settings.REMEMBER_TOKEN_EXPIRE_DAYS * 24 * 3600,
            httponly=True,  # JS 不可读，防 XSS
            samesite="lax",
            secure=False,
            path="/",
        )
    return resp


@router.post("/verify", summary="验证 SSO Token（AES 加密）并返回 JWT")
def sso_verify(req: SsoVerifyRequest, db: Session = Depends(get_db)):
    """泛微 OA 传来的加密 token，验证后签发 PMS 的 JWT"""
    return sso_service.sso_login(db, req.token)


@router.get("/url/verify", summary="验证 SSO URL 参数（HMAC 签名）并返回 JWT")
def sso_url_verify(
    loginid: str = Query(...),
    username: str = Query(...),
    dept: str = Query(""),
    ts: int = Query(...),
    sign: str = Query(...),
    db: Session = Depends(get_db),
):
    """URL 参数方式 SSO 登录，适合 OA 菜单直接配置"""
    return sso_service.sso_login_by_params(db, loginid, username, dept, ts, sign)


@router.post("/oa-login", summary="OA 统一认证登录")
async def sso_oa_login(req: SsoOaLoginRequest, db: Session = Depends(get_db)):
    """通过 OA getToken API 验证用户身份，成功后签发 PMS JWT 并设置 Cookie"""
    result = await sso_service.sso_login_by_loginid(
        db, req.loginid, req.username or req.loginid, req.dept,
    )
    # 设置 Cookie，以便下次自动登录（SameSite=Lax 允许 iframe 内的请求携带）
    resp = JSONResponse(content=result)
    resp.set_cookie(
        key="pms_token",
        value=result["access_token"],
        max_age=8 * 3600,  # 8 小时
        httponly=False,  # 允许 JS 读取，方便登录页检测
        samesite="lax",  # 允许 OA iframe 跨站携带
        secure=False,  # 内网 HTTP，不要求 HTTPS
        path="/",
    )
    return resp


@router.post("/generate-url", summary="生成 SSO 链接（管理工具）")
def sso_generate_url(req: SsoUrlRequest):
    """输入用户信息，返回带签名的 SSO URL"""
    url = sso_service.generate_sso_url(req.loginid, req.username, req.dept)
    return {"url": url}


# ==================== OA 统一认证中心（CAS 流程） ====================


@router.get("/oa-redirect", summary="重定向到 OA 统一认证登录页")
def sso_oa_redirect():
    """将浏览器重定向到 OA 统一认证登录页，登录后 OA 会回调到 /sso/callback"""
    oa_login_url = sso_service.build_oa_login_url()
    logger.info(f"SSO 重定向到 OA: {oa_login_url}")
    return RedirectResponse(url=oa_login_url, status_code=302)


@router.get("/callback", summary="OA 统一认证回调")
async def sso_oa_callback(
    ticket: str = Query(""),
    loginid: str = Query(""),
    token: str = Query(""),
    username: str = Query(""),
    db: Session = Depends(get_db),
):
    """
    OA 统一认证回调端点。OA 登录成功后重定向到此地址。
    当前支持：
    - ticket: CAS ticket（通过 checkToken 验证，必要时用 serviceValidate 获取用户）
    - token: ssoToken（与 ticket 同等对待）
    - loginid: 用户登录名（若 OA 直接传递，可跳过 CAS 解析步骤）
    """
    tkt = ticket or token
    service_url = settings.PMS_CALLBACK_URL

    logger.info(
        f"SSO 回调: ticket={tkt}, loginid={loginid}, username={username}"
    )

    result = await sso_service.handle_oa_callback(
        db, ticket=tkt, loginid=loginid, service_url=service_url
    )
    return result


@router.get("/oa-login-page", summary="OA 统一认证登录入口")
def sso_oa_login_page(request: Request, db: Session = Depends(get_db)):
    """OA 统一认证入口：Cookie 免密 → 直接跳转；无 Cookie → 重定向到前端 SSO 登录页"""
    ft = settings.PMS_FRONTEND_URL

    # 检查长期免密 Cookie（新窗口模式下 SameSite=Lax Cookie 会被发送）
    remember = request.cookies.get("pms_remember")
    if remember:
        from app.services import auth as auth_service
        try:
            result = auth_service.auto_login(db, remember)
            new_token = result.access_token
            resp = RedirectResponse(url=f"{ft}/?token={new_token}", status_code=302)
            resp.set_cookie(
                key="pms_token", value=new_token, max_age=8 * 3600,
                httponly=False, samesite="lax", secure=False, path="/",
            )
            return resp
        except Exception:
            # Cookie 失效，清除并继续重定向到前端
            pass

    # 重定向到前端 SSO 登录页，由前端统一处理免密登录和表单登录
    # 前端在同源环境下使用 localStorage，不受 iframe 跨域存储分区影响
    target = f"{ft}/sso/start"
    resp = RedirectResponse(url=target, status_code=302)
    # 清除可能已失效的 pms_remember Cookie
    resp.set_cookie(
        key="pms_remember", value="", max_age=0,
        path="/", samesite="lax", secure=False,
    )
    return resp
