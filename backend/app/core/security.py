import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from jose import jwt
import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

from app.core.config import settings

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
        return password_hasher.verify(hashed_password, plain_password)
    except (VerificationError, InvalidHashError, ValueError, TypeError):
        return False


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None, *,
                        credential_version: int | None = None, auth_method: str | None = None,
                        scope: str | None = None) -> str:
    """生成 JWT 令牌"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    if credential_version is not None:
        to_encode.update(credential_version=credential_version, auth_method=auth_method, scope=scope)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def user_access_token(user, auth_method="password") -> str:
    limited = auth_method == "password" and user.must_change_password
    return create_access_token(user.id, timedelta(minutes=10) if limited else None,
                               credential_version=user.credential_version, auth_method=auth_method,
                               scope="change_password" if limited else "full")


def generate_remember_token() -> str:
    """生成 64 位随机字符串作为免密登录令牌"""
    return secrets.token_hex(32)


def hash_remember_token(token: str) -> str:
    """对免密令牌做 SHA256 哈希，数据库中只存储哈希值"""
    return hashlib.sha256(token.encode()).hexdigest()
