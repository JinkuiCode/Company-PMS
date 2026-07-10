from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.config import settings
from app.models.user import SysUser
from app.models.rbac import SysUserRole, SysRole
from app.schemas.user import LoginRequest, AutoLoginRequest, SsoLoginRequest, TokenResponse, UserInfo
from app.services import auth as auth_service
from app.services.operation_log import record_operation_log
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, status

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    """从 JWT 令牌中解析当前用户 ID，所有需要认证的接口依赖此函数"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="令牌无效")
        return int(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")


@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return auth_service.login(db, req, request=request)


def get_current_user_context(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """获取当前用户的完整上下文：user_id, dept_id, data_scope, product_lines"""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    dept_id = user.dept_id

    # 查询用户所有角色的数据权限范围，取最大值
    role_ids = [ur.role_id for ur in db.query(SysUserRole).filter(
        SysUserRole.user_id == user_id).all()]

    if not role_ids:
        return {"user_id": user_id, "dept_id": dept_id, "data_scope": 1, "product_lines": None}

    roles = db.query(SysRole).filter(SysRole.id.in_(role_ids)).all()
    scopes = [r.data_scope for r in roles]
    effective_scope = max(scopes)  # 取最大权限

    # 收集所有角色的产品线，取并集；任一角色为空=不限制
    product_lines_set: set[str] = set()
    has_unrestricted = False
    for r in roles:
        if not r.product_lines:  # 空/null = 不限制
            has_unrestricted = True
            break
        for pl in r.product_lines.split(","):
            pl = pl.strip()
            if pl:
                product_lines_set.add(pl)

    effective_product_lines = None if has_unrestricted else (list(product_lines_set) if product_lines_set else None)

    return {"user_id": user_id, "dept_id": dept_id, "data_scope": effective_scope, "product_lines": effective_product_lines}


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
def get_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return auth_service.get_current_user(db, user_id)


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
