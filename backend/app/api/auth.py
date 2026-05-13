from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.core.database import get_db
from app.core.config import settings
from app.schemas.user import LoginRequest, TokenResponse, UserInfo
from app.services import auth as auth_service
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
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, req)


@router.get("/me", response_model=UserInfo, summary="获取当前用户信息")
def get_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return auth_service.get_current_user(db, user_id)
