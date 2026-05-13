from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import SysUser
from app.schemas.user import LoginRequest, TokenResponse, UserInfo
from app.core.security import verify_password, create_access_token


def login(db: Session, req: LoginRequest) -> TokenResponse:
    """用户登录，验证密码后返回 JWT 令牌"""
    user = db.query(SysUser).filter(SysUser.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if user.status == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )

    access_token = create_access_token(subject=user.id)
    return TokenResponse(access_token=access_token)


def get_current_user(db: Session, user_id: int) -> UserInfo:
    """通过用户 ID 获取当前用户信息"""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserInfo.model_validate(user)
