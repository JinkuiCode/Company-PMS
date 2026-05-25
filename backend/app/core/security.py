import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """生成 JWT 令牌"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def generate_remember_token() -> str:
    """生成 64 位随机字符串作为免密登录令牌"""
    return secrets.token_hex(32)


def hash_remember_token(token: str) -> str:
    """对免密令牌做 SHA256 哈希，数据库中只存储哈希值"""
    return hashlib.sha256(token.encode()).hexdigest()
