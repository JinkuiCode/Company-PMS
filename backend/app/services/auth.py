from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from fastapi import HTTPException, Request, status

from app.models.user import SysUser, RememberToken
from app.schemas.user import LoginRequest, TokenResponse, UserInfo
from app.core.security import (
    verify_password,
    generate_remember_token,
    hash_remember_token,
    user_access_token,
    hash_password,
    create_access_token,
)
from app.core.config import settings
from app.services.operation_log import record_operation_log
from app.services.password_policy import check_login_limit, rate_limit_keys, record_login_failure, validate_new_password


def login(db: Session, req: LoginRequest, request: Request | None = None) -> TokenResponse:
    """用户登录，验证密码后返回 JWT 令牌。勾选记住我时额外返回长期令牌"""
    keys = rate_limit_keys(req.username, request)
    check_login_limit(db, keys)
    user = db.query(SysUser).filter(SysUser.username == req.username).first()
    if not user or not user.local_login_enabled or not verify_password(req.password, user.password_hash):
        record_login_failure(db, keys)
        record_operation_log(
            db,
            module="认证",
            action="login",
            entity_type="sys_user",
            entity_id=user.id if user else None,
            entity_name=user.real_name if user else req.username,
            operator_id=user.id if user else None,
            request=request,
            status="failed",
            summary=f"登录失败：{req.username}",
            after_data={"username": req.username, "remember_me": req.remember_me},
            error_msg="用户名或密码错误",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if user.status == 0:
        record_operation_log(
            db,
            module="认证",
            action="login",
            entity_type="sys_user",
            entity_id=user.id,
            entity_name=user.real_name,
            operator_id=user.id,
            request=request,
            status="failed",
            summary=f"登录失败：{user.real_name}",
            after_data={"username": req.username, "remember_me": req.remember_me},
            error_msg="账号已被禁用",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    access_token = user_access_token(user)
    remember_token: str | None = None

    if req.remember_me and not user.must_change_password:
        # 生成长期免密令牌，数据库只存哈希，原值返回给前端
        raw_token = generate_remember_token()
        expires_at = datetime.utcnow() + timedelta(days=settings.REMEMBER_TOKEN_EXPIRE_DAYS)
        record = RememberToken(
            user_id=user.id,
            credential_version=user.credential_version,
            token_hash=hash_remember_token(raw_token),
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()
        remember_token = raw_token

    record_operation_log(
        db,
        module="认证",
        action="login",
        entity_type="sys_user",
        entity_id=user.id,
        entity_name=user.real_name,
        operator_id=user.id,
        request=request,
        summary=f"登录成功：{user.real_name}",
        after_data={"username": user.username, "remember_me": req.remember_me},
        commit=True,
    )
    return TokenResponse(access_token=access_token, remember_token=remember_token, must_change_password=user.must_change_password)


def auto_login(db: Session, remember_token: str, request: Request | None = None) -> TokenResponse:
    """使用免密令牌自动登录，验证通过后签发新的 JWT，同时滚动刷新令牌"""
    token_hash = hash_remember_token(remember_token)
    record = (
        db.query(RememberToken)
        .filter(RememberToken.token_hash == token_hash)
        .first()
    )

    if not record:
        record_operation_log(
            db,
            module="认证",
            action="auto_login",
            entity_type="sys_user",
            request=request,
            status="failed",
            summary="自动登录失败：免密令牌无效",
            after_data={"remember_token": remember_token},
            error_msg="免密令牌无效",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="免密令牌无效",
        )

    if record.expires_at < datetime.utcnow():
        user_id = record.user_id
        db.delete(record)
        db.commit()
        record_operation_log(
            db,
            module="认证",
            action="auto_login",
            entity_type="sys_user",
            entity_id=user_id,
            operator_id=user_id,
            request=request,
            status="failed",
            summary="自动登录失败：免密令牌已过期",
            after_data={"remember_token": remember_token},
            error_msg="免密令牌已过期",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="免密令牌已过期，请重新登录",
        )

    # 验证用户状态
    user = db.query(SysUser).filter(SysUser.id == record.user_id).first()
    if not user or user.status == 0:
        user_id = record.user_id
        if not user:
            db.delete(record)
            db.commit()
        record_operation_log(
            db,
            module="认证",
            action="auto_login",
            entity_type="sys_user",
            entity_id=user_id,
            entity_name=user.real_name if user else None,
            operator_id=user_id if user else None,
            request=request,
            status="failed",
            summary="自动登录失败：账号不存在或已禁用",
            after_data={"remember_token": remember_token},
            error_msg="账号不存在或已被禁用",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号不存在或已被禁用",
        )

    if user.must_change_password or not user.local_login_enabled or record.credential_version != user.credential_version:
        raise HTTPException(401, "请使用密码登录并修改密码")
    # 签发新 JWT，同时滚动刷新免密令牌有效期
    access_token = user_access_token(user)
    record.last_used_at = datetime.utcnow()
    record.expires_at = datetime.utcnow() + timedelta(days=settings.REMEMBER_TOKEN_EXPIRE_DAYS)
    db.commit()

    record_operation_log(
        db,
        module="认证",
        action="auto_login",
        entity_type="sys_user",
        entity_id=user.id,
        entity_name=user.real_name,
        operator_id=user.id,
        request=request,
        summary=f"自动登录成功：{user.real_name}",
        after_data={"username": user.username},
        commit=True,
    )
    return TokenResponse(access_token=access_token, remember_token=None)


def invalidate_user_tokens(db: Session, user_id: int) -> None:
    """清除指定用户的所有免密令牌，密码变更或账号禁用时调用"""
    db.query(RememberToken).filter(RememberToken.user_id == user_id).delete()
    db.query(SysUser).filter(SysUser.id == user_id).update({SysUser.credential_version: SysUser.credential_version + 1})
    db.commit()


def get_current_user(db: Session, user_id: int, authorization_context: dict | None = None) -> UserInfo:
    """通过用户 ID 获取当前用户信息"""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    from app.services.role_home import resolve_user_home
    return UserInfo(
        email=user.email,
        must_change_password=bool((authorization_context or {}).get("must_change_password", user.must_change_password)),
        home_path=resolve_user_home(db, user_id, (authorization_context or {}).get("permissions", [])),
        id=user.id,
        username=user.username,
        real_name=user.real_name,
        dept_id=user.dept_id,
        mobile=user.mobile,
        status=user.status,
        role_codes=(authorization_context or {}).get("role_codes", []),
        permissions=(authorization_context or {}).get("permissions", []),
        data_scope=(authorization_context or {}).get("data_scope", 1),
        product_category_ids=(authorization_context or {}).get("product_category_ids"),
    )


def change_password(db, user_id, data, request=None, *, authenticated_version: int):
    from sqlalchemy import update
    user = db.get(SysUser, user_id)
    if not user or user.credential_version != authenticated_version or user.status != 1 or not user.local_login_enabled:
        raise HTTPException(409, "登录凭据已变化，请重新登录")
    validate_new_password(db, user, data.new_password, data.confirm_password)
    committed_version = authenticated_version + 1
    try:
        result = db.execute(update(SysUser).where(
            SysUser.id == user_id, SysUser.credential_version == authenticated_version,
            SysUser.status == 1, SysUser.local_login_enabled == True,
        ).values(password_hash=hash_password(data.new_password), credential_version=committed_version,
                 must_change_password=False))
        if result.rowcount != 1:
            raise HTTPException(409, "登录凭据已变化，请重新登录")
        db.query(RememberToken).filter_by(user_id=user_id).delete()
        record_operation_log(db, module="认证", action="change_password", entity_type="sys_user",
                             entity_id=user_id, operator_id=user_id, request=request, summary="用户修改密码",
                             after_data={"credentials_changed": True})
        db.commit()
    except Exception:
        db.rollback()
        raise
    # Never adopt a newer reset/logout generation between commit and issuance.
    token = create_access_token(user_id, credential_version=committed_version,
                                auth_method="password", scope="full")
    return TokenResponse(access_token=token, must_change_password=False)
