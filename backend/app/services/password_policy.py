import hashlib
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.core.security import verify_password
from app.models.user import LoginFailure
from app.models.parameter import SysParameter
from app.services.parameter import INITIAL_PASSWORD


def rate_limit_keys(username, request):
    ip = request.client.host if request and request.client else "internal"
    return tuple(hashlib.sha256(value.encode()).hexdigest() for value in (username.casefold(), ip))


def check_login_limit(db, keys):
    since = datetime.utcnow() - timedelta(minutes=15)
    db.query(LoginFailure).filter(LoginFailure.attempted_at < since).delete(synchronize_session=False)
    account, ip = keys
    for column, value in ((LoginFailure.account_key, account), (LoginFailure.ip_key, ip)):
        if db.query(LoginFailure).filter(column == value, LoginFailure.attempted_at >= since).count() >= 5:
            raise HTTPException(429, "登录失败次数过多，请 15 分钟后重试")


def record_login_failure(db, keys):
    db.add(LoginFailure(account_key=keys[0], ip_key=keys[1], attempted_at=datetime.utcnow()))


COMMON_PASSWORDS = {"12345678", "123456789", "1234567890", "password", "password1", "password123",
                    "qwertyuiop", "qwerty123", "abcdefgh", "87654321", "11111111", "00000000",
                    "admin123", "admin1234", "letmein123", "iloveyou", "welcome1", "welcome123"}


def validate_new_password(db, user, password, confirmation):
    if password != confirmation:
        raise HTTPException(422, "两次输入的密码不一致")
    normalized = password.casefold()
    terms = {user.username.casefold(), user.real_name.casefold(), "aelsystem"}
    if not 8 <= len(password) <= 64 or normalized in COMMON_PASSWORDS or len(set(password)) == 1 or normalized in terms:
        raise HTTPException(422, "密码过于常见或与账号、姓名、公司名称相同")
    parameter = db.get(SysParameter, INITIAL_PASSWORD)
    if verify_password(password, user.password_hash) or (parameter and parameter.secret_hash and verify_password(password, parameter.secret_hash)):
        raise HTTPException(422, "新密码不能与当前密码或初始密码相同")
