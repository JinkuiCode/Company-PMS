"""泛微 OA SSO 单点登录服务"""
import base64
import hashlib
import hmac
import json
import os
import time

from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import hash_password, create_access_token
from app.models.user import SysUser
from app.models.rbac import SysDept, SysRole, SysUserRole


def _get_aes_key() -> bytes:
    """将配置密钥 hash 为 32 字节 AES-256 key"""
    return hashlib.sha256(settings.SSO_SECRET_KEY.encode()).digest()


def decrypt_token(encrypted_token: str) -> dict:
    """解密泛微传递的 SSO token，返回用户信息 dict"""
    try:
        raw = base64.urlsafe_b64decode(encrypted_token)
        key = _get_aes_key()
        iv = raw[:16]  # 前 16 字节为 IV
        ciphertext = raw[16:]

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()

        # 去除 PKCS7 填充
        pad_len = decrypted[-1]
        decrypted = decrypted[:-pad_len]

        payload = json.loads(decrypted.decode("utf-8"))

        # 时间戳校验（5 分钟内有效）
        ts = payload.get("timestamp", 0)
        if abs(time.time() - ts) > settings.SSO_TOKEN_EXPIRE_SECONDS:
            raise HTTPException(status_code=401, detail="SSO token 已过期")

        return payload

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="SSO token 无效")


def encrypt_token(payload: dict) -> str:
    """加密生成 SSO token（仅用于本地测试和泛微端配置参考）"""
    from cryptography.hazmat.primitives import padding

    key = _get_aes_key()
    iv = os.urandom(16)

    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(raw) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()

    return base64.urlsafe_b64encode(iv + encrypted).decode()


def find_or_create_user(db: Session, loginid: str, username: str, dept_name: str) -> SysUser:
    """根据 OA 的 loginid 查找本地用户，不存在则自动创建"""
    user = db.query(SysUser).filter(SysUser.username == loginid).first()
    if user:
        # 已有用户：更新真实姓名
        if user.real_name != username:
            user.real_name = username
            db.commit()
        return user

    if not settings.SSO_AUTO_CREATE_USER:
        raise HTTPException(status_code=403, detail="用户不存在且未开启自动创建")

    # 自动创建用户
    # 1. 查找或创建部门
    dept = db.query(SysDept).filter(SysDept.dept_name == dept_name).first()
    dept_id = dept.id if dept else None

    # 2. 创建用户
    user = SysUser(
        username=loginid,
        real_name=username,
        password_hash=hash_password("sso_placeholder"),  # SSO 用户不通过密码登录
        dept_id=dept_id,
        status=1,
    )
    db.add(user)
    db.flush()  # 获取 user.id

    # 3. 分配默认角色（role_code="user" 或第一个可用角色）
    default_role = db.query(SysRole).filter(SysRole.role_code == "user").first()
    if not default_role:
        default_role = db.query(SysRole).first()
    if default_role:
        db.add(SysUserRole(user_id=user.id, role_id=default_role.id))

    db.commit()
    db.refresh(user)
    return user


def sso_login(db: Session, encrypted_token: str) -> dict:
    """SSO 登录：解密 token → 查找/创建用户 → 签发 JWT"""
    payload = decrypt_token(encrypted_token)

    loginid = payload.get("loginid")
    username = payload.get("username", loginid)
    dept_name = payload.get("dept_name", "")

    if not loginid:
        raise HTTPException(status_code=400, detail="SSO token 缺少 loginid")

    user = find_or_create_user(db, loginid, username, dept_name)

    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}


# ==================== HMAC URL 签名方式 ====================

def _get_hmac_key() -> bytes:
    return settings.SSO_SECRET_KEY.encode()


def _make_sign(loginid: str, username: str, dept_name: str, ts: int) -> str:
    """生成 HMAC-SHA256 签名"""
    raw = f"{loginid}|{username}|{dept_name}|{ts}"
    return hmac.new(_get_hmac_key(), raw.encode(), hashlib.sha256).hexdigest()


def verify_hmac_params(loginid: str, username: str, dept_name: str, ts: int, sign: str) -> bool:
    """验证 URL 参数的 HMAC 签名"""
    if abs(time.time() - ts) > settings.SSO_TOKEN_EXPIRE_SECONDS:
        return False
    expected = _make_sign(loginid, username, dept_name, ts)
    return hmac.compare_digest(expected, sign)


def generate_sso_url(loginid: str, username: str, dept_name: str) -> str:
    """生成本地测试用的 SSO URL（HMAC 签名方式）"""
    ts = int(time.time())
    sign = _make_sign(loginid, username, dept_name, ts)
    from urllib.parse import urlencode
    params = urlencode({
        "loginid": loginid,
        "username": username,
        "dept": dept_name,
        "ts": str(ts),
        "sign": sign,
    })
    return f"/sso/login?{params}"


def sso_login_by_params(
    db: Session, loginid: str, username: str, dept_name: str, ts: int, sign: str
) -> dict:
    """URL 参数方式 SSO 登录：验证签名 → 查找/创建用户 → 签发 JWT"""
    if not verify_hmac_params(loginid, username, dept_name, ts, sign):
        raise HTTPException(status_code=401, detail="SSO 签名无效或已过期")

    user = find_or_create_user(db, loginid, username, dept_name)

    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}


def sso_login_by_loginid(
    db: Session, loginid: str, username: str = "", dept_name: str = ""
) -> dict:
    """OA 菜单直接登录（由 Referer 校验保证安全）：查找/创建用户 → 签发 JWT"""
    user = find_or_create_user(
        db, loginid,
        username or loginid,
        dept_name,
    )

    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}
