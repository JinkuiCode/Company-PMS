from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from app.core.security import hash_password, verify_password
from app.models.parameter import SysParameter
from app.services.operation_log import record_operation_log
from app.services.secret_encryption import SecretEncryptionError, decrypt_secret, encrypt_secret

INITIAL_PASSWORD = "user.initial_password"
ARCHIVE_INITIALIZATION_ENABLED = "archive.initialization_enabled"


def validate_initial_password(value):
    if not 1 <= len(value) <= 64:
        raise HTTPException(422, "初始密码须为 1-64 个字符")
    return value


def validate_boolean(value):
    if value not in ('true', 'false'):
        raise HTTPException(422, "布尔参数只能为 true 或 false")
    return value


PARAMETERS = {
    INITIAL_PASSWORD: dict(name="用户初始密码", group="用户管理", description="新增用户和重置密码使用的初始密码",
                          sensitive=True, value_type="text", validator=validate_initial_password),
    ARCHIVE_INITIALIZATION_ENABLED: dict(name="档案初始化模式", group="项目档案", description="开启期初档案整理与产品线分配；关闭后仍可回退已导入批次",
                                        sensitive=False, value_type="boolean", default="true", validator=validate_boolean),
}


def archive_initialization_enabled(db):
    value = db.query(SysParameter.value_text).filter(SysParameter.code == ARCHIVE_INITIALIZATION_ENABLED).scalar()
    return value is None or value == 'true'


def require_archive_initialization(db):
    if not archive_initialization_enabled(db):
        raise HTTPException(409, {"code": "ARCHIVE_INITIALIZATION_DISABLED", "message": "档案初始化模式已关闭"})


def list_parameters(db):
    rows = {row.code: row for row in db.query(SysParameter).all()}
    items = []
    for code, meta in PARAMETERS.items():
        row = rows.get(code)
        stored = (row.secret_hash if meta["sensitive"] else row.value_text) if row else None
        value = None if meta["sensitive"] else stored if stored is not None else meta.get('default')
        reveal_status, reveal_message = "hidden", None
        if code == INITIAL_PASSWORD and stored is not None:
            if not row.secret_ciphertext:
                reveal_status, reveal_message = "legacy", "旧初始密码仅保存不可逆哈希，需重新保存后才能回显"
            else:
                try:
                    revealed = decrypt_secret(row.secret_ciphertext, code)
                    if not verify_password(revealed, stored):
                        raise SecretEncryptionError("Stored password changed")
                    value = revealed
                    reveal_status = "available"
                except SecretEncryptionError:
                    reveal_status, reveal_message = "unavailable", "初始密码无法解密，请检查加密密钥或重新保存"
        items.append(dict(code=code, **{key: meta[key] for key in ("name", "group", "description", "sensitive", "value_type")},
                          configured=stored is not None, version=row.version if row else 0,
                          updated_at=row.updated_at if row else None, value=value,
                          reveal_status=reveal_status, reveal_message=reveal_message))
    return JSONResponse(jsonable_encoder({"items": items}), headers={"Cache-Control": "no-store"})


def update_parameter(db, code, value, version, operator_id, request=None):
    if code not in PARAMETERS:
        raise HTTPException(404, "参数不存在")
    if len(value) > 16384:
        raise HTTPException(422, "参数值过长")
    meta = PARAMETERS[code]
    validator = meta.get("validator")
    if validator:
        value = validator(value)
    ciphertext = None
    if code == INITIAL_PASSWORD:
        try:
            ciphertext = encrypt_secret(value, code)
        except SecretEncryptionError:
            raise HTTPException(503, "初始密码加密密钥不可用，参数未保存", headers={"Cache-Control": "no-store"}) from None
    values = {"secret_hash": hash_password(value) if meta["sensitive"] else None,
              "secret_ciphertext": ciphertext,
              "value_text": None if meta["sensitive"] else value, "version": version + 1}
    row = db.get(SysParameter, code)
    before = {"version": version}
    after = {"version": version + 1, "configured": True}
    if not meta["sensitive"]:
        before["value_text"] = row.value_text if row else None
        after["value_text"] = value
    try:
        if row is None:
            if version != 0:
                raise HTTPException(409, "参数已变化，请刷新后重试")
            db.add(SysParameter(code=code, **values))
            db.flush()
        else:
            changed = db.execute(update(SysParameter).where(SysParameter.code == code, SysParameter.version == version)
                                 .values(**values))
            if changed.rowcount != 1:
                raise HTTPException(409, "参数已变化，请刷新后重试")
        record_operation_log(db, module="系统管理", action="update", entity_type="sys_parameter",
                             entity_name=PARAMETERS[code]["name"], operator_id=operator_id, request=request,
                             summary=f"更新参数：{meta['name']}", before_data=before, after_data=after)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "参数已变化，请刷新后重试")
    except Exception:
        db.rollback()
        raise
    return JSONResponse({"message": "参数已更新", "version": version + 1}, headers={"Cache-Control": "no-store"})


def initial_password_hash(db):
    row = db.get(SysParameter, INITIAL_PASSWORD)
    if not row or not row.secret_hash:
        raise HTTPException(409, "请先配置用户初始密码参数")
    return row.secret_hash
