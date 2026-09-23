"""统一的运行时认证与 RBAC 授权依赖。"""
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole
from app.models.user import SysUser
from app.services.product_line_scope import get_authorized_product_line_ids


security = HTTPBearer()
AuthorizationContext = dict[str, Any]


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> int:
    return authenticate_session(credentials, db, allow_change=False)["user_id"]


def authenticate_session(credentials, db, *, allow_change=False):
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        subject = payload.get("sub")
        if subject is None:
            raise HTTPException(status_code=401, detail="令牌无效")
        user = db.get(SysUser, int(subject))
        if not user:
            raise HTTPException(401, "用户不存在")
        if user.status != 1:
            raise HTTPException(403, "账号已被禁用，请联系管理员")
        version = payload.get("credential_version")
        method = payload.get("auth_method")
        scope = payload.get("scope")
        # Pre-upgrade tokens cannot prove OA provenance. Fail closed instead of
        # letting an unversioned token bypass reset or local enrollment.
        if version != user.credential_version or method not in {"password", "oa"} or scope not in {"full", "change_password"}:
            raise HTTPException(401, "登录凭据已失效，请重新登录")
        if method == "password" and not user.local_login_enabled:
            raise HTTPException(401, "本地登录已停用")
        limited = scope == "change_password" or (method == "password" and user.must_change_password)
        if limited and not allow_change:
            raise HTTPException(403, "请先修改密码")
        return {"user_id": user.id, "auth_method": method, "must_change_password": limited,
                "credential_version": version}
    except (JWTError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="令牌无效或已过期") from exc


def get_password_session(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    return authenticate_session(credentials, db, allow_change=True)


def get_me_context(session=Depends(get_password_session), db: Session = Depends(get_db)):
    context = build_authorization_context(db, session["user_id"])
    context.update(session)
    if session["must_change_password"]:
        context.update(permissions=[], role_codes=[], data_scope=1, product_category_ids=[], product_line_ids=[])
    return context


def build_authorization_context(db: Session, user_id: int) -> AuthorizationContext:
    """按当前数据库状态计算用户的有效角色、权限和数据范围。"""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status != 1:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    roles = (
        db.query(SysRole)
        .join(SysUserRole, SysUserRole.role_id == SysRole.id)
        .filter(SysUserRole.user_id == user_id, SysRole.status == 1)
        .order_by(SysRole.id)
        .all()
    )
    role_ids = [role.id for role in roles]
    permissions: set[str] = set()
    if role_ids:
        rows = (
            db.query(SysMenu.permission_code)
            .join(SysRoleMenu, SysRoleMenu.menu_id == SysMenu.id)
            .filter(
                SysRoleMenu.role_id.in_(role_ids),
                SysMenu.status == 1,
                SysMenu.permission_code.isnot(None),
            )
            .all()
        )
        permissions = {code for (code,) in rows if code}

    product_category_ids: list[int] | None
    if not roles:
        product_category_ids = []
    elif 'business:data:all' in permissions or any(not role.product_category_ids for role in roles):
        product_category_ids = None
    else:
        product_category_ids = sorted({
            int(value.strip())
            for role in roles
            for value in (role.product_category_ids or "").split(",")
            if value.strip().isdigit()
        })

    return {
        "user_id": user.id,
        "dept_id": user.dept_id,
        "role_codes": [role.role_code for role in roles],
        "permissions": sorted(permissions),
        "data_scope": max(
            (role.data_scope if 1 <= role.data_scope <= 4 else 1 for role in roles),
            default=1,
        ),
        "product_category_ids": product_category_ids,
        "product_line_ids": get_authorized_product_line_ids(db, roles),
    }


def get_current_user_context(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AuthorizationContext:
    return build_authorization_context(db, user_id)


def enforce_permission(context: AuthorizationContext, permission_code: str) -> None:
    if permission_code not in context.get("permissions", []):
        raise HTTPException(status_code=403, detail=f"无权限执行此操作：{permission_code}")


def enforce_any_permission(context: AuthorizationContext, permission_codes: tuple[str, ...]) -> None:
    permissions = set(context.get("permissions", []))
    if not permissions.intersection(permission_codes):
        raise HTTPException(status_code=403, detail="无权限访问此资源")


def require_permission(permission_code: str) -> Callable[..., AuthorizationContext]:
    def dependency(
        context: AuthorizationContext = Depends(get_current_user_context),
    ) -> AuthorizationContext:
        enforce_permission(context, permission_code)
        return context

    return dependency


def require_any_permission(*permission_codes: str) -> Callable[..., AuthorizationContext]:
    if not permission_codes:
        raise ValueError("至少需要一个权限码")

    def dependency(
        context: AuthorizationContext = Depends(get_current_user_context),
    ) -> AuthorizationContext:
        enforce_any_permission(context, permission_codes)
        return context

    return dependency
