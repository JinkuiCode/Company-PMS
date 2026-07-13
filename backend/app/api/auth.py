from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.user import LoginRequest, AutoLoginRequest, SsoLoginRequest, TokenResponse, UserInfo
from app.services import auth as auth_service
from app.services.authorization import get_current_user_context, get_current_user_id
from app.services.operation_log import record_operation_log
from fastapi import HTTPException

router = APIRouter(prefix="/api/auth", tags=["认证"])
@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return auth_service.login(db, req, request=request)


@router.post("/auto-login", response_model=TokenResponse, summary="免密自动登录")
def auto_login(req: AutoLoginRequest, request: Request, db: Session = Depends(get_db)):
    """使用长期免密令牌自动登录，签发新的 JWT"""
    return auth_service.auto_login(db, req.remember_token, request=request)


@router.post("/sso-login", response_model=TokenResponse, summary="OA JSP 重定向 SSO 免密登录")
def sso_login(req: SsoLoginRequest, request: Request, db: Session = Depends(get_db)):
    """OA 服务器 JSP 获取 loginId 后 302 重定向到 PMS 前端，前端调用此接口完成免密登录"""
    from app.services import sso as sso_service
    try:
        token = sso_service.sso_login_by_oa_redirect(db, req.sso_login_id, req.ts, req.sign)
        record_operation_log(
            db,
            module="认证",
            action="sso_login",
            entity_type="sys_user",
            entity_name=req.sso_login_id,
            request=request,
            summary=f"SSO 登录成功：{req.sso_login_id}",
            after_data={"sso_login_id": req.sso_login_id, "ts": req.ts, "sign": req.sign},
            commit=True,
        )
        return token
    except HTTPException as exc:
        record_operation_log(
            db,
            module="认证",
            action="sso_login",
            entity_type="sys_user",
            entity_name=req.sso_login_id,
            request=request,
            status="failed",
            summary=f"SSO 登录失败：{req.sso_login_id}",
            after_data={"sso_login_id": req.sso_login_id, "ts": req.ts, "sign": req.sign},
            error_msg=str(exc.detail),
            commit=True,
        )
        raise


@router.post("/logout", summary="退出登录")
def logout(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """退出登录，清除当前用户所有免密令牌"""
    auth_service.invalidate_user_tokens(db, user_id)
    record_operation_log(
        db,
        module="认证",
        action="logout",
        entity_type="sys_user",
        entity_id=user_id,
        operator_id=user_id,
        request=request,
        summary="退出登录",
        commit=True,
    )
    return {"detail": "已退出登录"}


@router.get("/me", response_model=UserInfo, summary="获取当前用户信息")
def get_me(
    scope_ctx: dict = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    return auth_service.get_current_user(db, scope_ctx["user_id"], authorization_context=scope_ctx)


@router.get("/product-lines", summary="获取当前用户允许的产品线")
def get_allowed_product_lines(
    scope_ctx: dict = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """返回当前用户允许的产品线列表，null 表示不限制"""
    allowed = scope_ctx.get("product_lines")  # None = 不限制
    # 从字典接口获取所有产品线定义
    from app.services.dict import get_dict_by_code
    all_lines_data = get_dict_by_code(db, "product_line")
    all_lines = [item["value"] for item in (all_lines_data.get("items", []) if all_lines_data else [])]

    if allowed is None:
        # 不限制，返回全部
        return {"unrestricted": True, "items": all_lines}
    else:
        # 只返回允许的
        return {"unrestricted": False, "items": allowed}
