"""泛微 OA SSO 单点登录服务"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import hash_password, create_access_token
from app.models.user import SysUser
from app.models.rbac import SysDept, SysRole, SysUserRole

logger = logging.getLogger(__name__)


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
        if user.status != 1:
            raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
        # 已有用户：更新真实姓名
        if user.real_name != username:
            user.real_name = username
            db.commit()
        return user

    if not settings.SSO_AUTO_CREATE_USER:
        raise HTTPException(status_code=403, detail="用户不存在且未开启自动创建")

    default_role = db.query(SysRole).filter(
        SysRole.role_code == "operator",
        SysRole.status == 1,
    ).first()
    if not default_role:
        raise HTTPException(status_code=503, detail="默认操作员角色不存在或已禁用，请联系系统管理员")

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

    # 3. OA 自动开户始终分配启用的操作员模板，缺失时上方已失败关闭。
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


def sso_login_by_oa_redirect(db: Session, loginid: str, ts: int, sign: str) -> dict:
    """OA JSP 302 重定向过来的 SSO 免密登录：验证 HMAC 签名 + 时间戳 → 签发 JWT"""
    # 1. 验证时间戳（5 分钟内有效，防重放攻击）
    if abs(time.time() - ts) > settings.SSO_TOKEN_EXPIRE_SECONDS:
        raise HTTPException(status_code=401, detail="SSO 请求已过期，请刷新 OA 页面后重试")

    # 2. 验证 HMAC-SHA256 签名（防伪造 loginId）
    expected_sign = _make_sign(loginid, "", "", ts)
    if not hmac.compare_digest(expected_sign, sign):
        raise HTTPException(status_code=401, detail="SSO 签名无效")

    # 3. 查找或创建用户 → 签发 JWT
    user = find_or_create_user(db, loginid, loginid, "")
    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}


def sso_login_by_password(db: Session, username: str, password: str, remember_me: bool = False) -> dict:
    """PMS 账号密码登录（OA 菜单跳转入口）：验证 PMS 本地密码 → 签发 JWT → 可选记住我"""
    from app.core.security import verify_password
    user = db.query(SysUser).filter(SysUser.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if user.status == 0:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    access_token = create_access_token(subject=str(user.id))
    result: dict = {"access_token": access_token, "token_type": "bearer"}

    if remember_me:
        from datetime import datetime, timedelta
        from app.models.user import RememberToken
        from app.core.security import generate_remember_token, hash_remember_token
        from app.core.config import settings as app_settings

        raw_token = generate_remember_token()
        expires_at = datetime.utcnow() + timedelta(days=app_settings.REMEMBER_TOKEN_EXPIRE_DAYS)
        record = RememberToken(
            user_id=user.id,
            token_hash=hash_remember_token(raw_token),
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()
        result["remember_token"] = raw_token

    return result


async def sso_login_by_loginid(
    db: Session, loginid: str, username: str = "", dept_name: str = ""
) -> dict:
    """OA 登录：调用 OA getToken 验证用户 → 查找/创建用户 → 签发 JWT"""
    # 调用 OA getToken 验证该 loginid 是否存在于 OA 中
    _ = await oa_get_token(loginid)

    user = find_or_create_user(
        db, loginid,
        username or loginid,
        dept_name,
    )

    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}


# ==================== OA 密码验证 ====================


async def oa_verify_password(loginid: str, password: str) -> bool:
    """验证 OA 用户的密码是否正确

    依次尝试：
    1. REST API: POST /ssologin/checkUserPassword
    2. SOAP WebService: checkUser 方法
    """
    # 方式1: REST-like API
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.OA_CHECK_USER_PWD_URL, data={
                "appid": settings.OA_APP_ID,
                "loginid": loginid,
                "password": password,
            })
            text = resp.text.strip()
            logger.info(f"OA checkUserPassword(REST): loginid={loginid}, status={resp.status_code}, body={text[:200]}")
            if resp.status_code == 200:
                if text == "true" or text.lower() == "true":
                    return True
                # 某些 OA 返回 JSON
                try:
                    data = json.loads(text)
                    if data.get("result") is True or data.get("success") is True:
                        return True
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"OA checkUserPassword REST 失败，尝试 SOAP: {e}")

    # 方式2: SOAP WebService
    try:
        soap_body = _build_check_user_soap(loginid, password)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                settings.OA_HRM_SERVICE_URL,
                content=soap_body,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "",
                },
            )
            text = resp.text
            logger.info(f"OA checkUser(SOAP): loginid={loginid}, status={resp.status_code}, body={text[:300]}")
            if resp.status_code == 200:
                # 解析 SOAP 响应，查找 "true"
                import re
                m = re.search(r'<checkUserReturn>\s*true\s*</checkUserReturn>', text, re.IGNORECASE)
                if m:
                    return True
                # 也尝试检查 body 中是否包含 true
                if re.search(r'>\s*true\s*<', text, re.IGNORECASE):
                    return True
    except Exception as e:
        logger.error(f"OA checkUser SOAP 失败: {e}")

    return False


def _build_check_user_soap(loginid: str, password: str) -> str:
    """构造 SOAP 请求体，调用 HrmService 的 checkUser 方法"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:hrm="http://localhost/services/HrmService">
  <soapenv:Header/>
  <soapenv:Body>
    <hrm:checkUser>
      <hrm:ipaddress>10.10.91.60</hrm:ipaddress>
      <hrm:loginid>{loginid}</hrm:loginid>
      <hrm:password>{password}</hrm:password>
    </hrm:checkUser>
  </soapenv:Body>
</soapenv:Envelope>"""


# ==================== OA 统一认证中心集成（CAS 流程） ====================


async def oa_get_token(loginid: str) -> str:
    """调用 OA 的 getToken API，为指定 loginid 获取 token"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.OA_GET_TOKEN_URL, data={
            "appid": settings.OA_APP_ID,
            "loginid": loginid,
        })
        text = resp.text.strip()
        logger.info(f"OA getToken(loginid={loginid}): status={resp.status_code}, body={text[:200]}")
        if resp.status_code != 200 or text.startswith("Token获取失败"):
            raise HTTPException(status_code=401, detail=f"OA getToken 失败: {text}")
        return text


async def oa_check_token(token: str) -> dict:
    """调用 OA checkToken API 验证 token，返回原始响应供上层解析"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.OA_CHECK_TOKEN_URL, data={
            "appid": settings.OA_APP_ID,
            "token": token,
        })
        text = resp.text.strip()
        logger.info(f"OA checkToken: status={resp.status_code}, body={text[:200]}")
        return {"valid": text == "true", "raw": text, "status_code": resp.status_code}


async def oa_validate_cas_ticket(ticket: str, service_url: str) -> dict:
    """调用 OA CAS /sso/serviceValidate 验证 ticket 并获取用户信息"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(settings.OA_SERVICE_VALIDATE_URL, params={
            "ticket": ticket,
            "service": service_url,
        })
        text = resp.text.strip()
        logger.info(f"OA serviceValidate: status={resp.status_code}, body={text[:500]}")
        return {"status_code": resp.status_code, "raw": text}


def build_oa_login_url() -> str:
    """构造 OA 统一认证登录页 URL（带 service 回调地址）"""
    params = {
        "appid": settings.OA_APP_ID,
        "service": settings.PMS_CALLBACK_URL,
    }
    return f"{settings.OA_LOGIN_URL}?{urlencode(params)}"


async def handle_oa_callback(db: Session, ticket: str, loginid: str = "", service_url: str = "") -> dict:
    """
    处理 OA 统一认证回调：验证 ticket → 获取用户身份 → 签发 JWT

    验证策略（按优先级）：
    1. 若 callback 已携带 loginid → 用 checkToken 验票即可
    2. 若只有 ticket → 先用 checkToken 验票，再用 CAS serviceValidate 获取用户 loginid
    """
    username = loginid

    if ticket:
        # 验证 ticket 有效性
        check_result = await oa_check_token(ticket)
        if not check_result["valid"]:
            # checkToken 失败，尝试 CAS serviceValidate
            if service_url:
                cas_result = await oa_validate_cas_ticket(ticket, service_url)
                if cas_result["status_code"] != 200:
                    raise HTTPException(status_code=401, detail=f"OA ticket 验证失败（checkToken + CAS 双重失败）")
                # 尝试从 CAS 响应中提取用户标识
                loginid = _extract_user_from_cas_response(cas_result["raw"]) or loginid

            if not loginid:
                raise HTTPException(
                    status_code=401,
                    detail="OA ticket 验证失败，且无法获取用户标识",
                )

        if not loginid:
            # ticket 有效但无 loginid，尝试从 checkToken 原始响应中提取
            loginid = _extract_user_from_check_token_response(check_result["raw"])
            if not loginid:
                raise HTTPException(
                    status_code=400,
                    detail="OA 验证通过但缺少 loginid，请确认 OA 回调包含用户标识",
                )

    if not loginid:
        raise HTTPException(status_code=400, detail="缺少 OA 用户标识（loginid）")

    user = find_or_create_user(db, loginid, username, "")
    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}


def _extract_user_from_cas_response(xml_text: str) -> str | None:
    """从 CAS serviceValidate 的 XML 响应中提取用户名"""
    import re
    # CAS 2.0: <cas:user>loginid</cas:user>
    m = re.search(r'<cas:user>(.*?)</cas:user>', xml_text)
    if m: return m.group(1)
    # CAS 3.0: <cas:authenticationSuccess><cas:user>...</cas:user>
    m = re.search(r'<cas:authenticationSuccess>.*?<cas:user>(.*?)</cas:user>', xml_text, re.DOTALL)
    if m: return m.group(1)
    # 泛微可能用其他标签
    m = re.search(r'<user>(.*?)</user>', xml_text)
    if m: return m.group(1)
    return None


def _extract_user_from_check_token_response(text: str) -> str | None:
    """尝试从 checkToken 的非标准响应中提取用户标识"""
    import re
    # 尝试 JSON
    try:
        data = json.loads(text)
        return data.get("loginid") or data.get("username") or data.get("user")
    except Exception:
        pass
    # 尝试 XML 中的 loginid
    m = re.search(r'<loginid>(.*?)</loginid>', text)
    if m: return m.group(1)
    return None
