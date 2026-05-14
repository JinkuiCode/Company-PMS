"""泛微 OA SSO 单点登录接口"""
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.services import sso as sso_service

router = APIRouter(prefix="/api/sso", tags=["SSO 单点登录"])


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


@router.post("/oa-login", summary="OA 菜单直接登录")
def sso_oa_login(req: SsoOaLoginRequest, db: Session = Depends(get_db)):
    """OA 菜单中配置链接直接登录，通过 loginid 查找或创建用户并签发 JWT"""
    return sso_service.sso_login_by_loginid(
        db, req.loginid, req.username or req.loginid, req.dept,
    )


@router.post("/generate-url", summary="生成 SSO 链接（管理工具）")
def sso_generate_url(req: SsoUrlRequest):
    """输入用户信息，返回带签名的 SSO URL"""
    url = sso_service.generate_sso_url(req.loginid, req.username, req.dept)
    return {"url": url}
