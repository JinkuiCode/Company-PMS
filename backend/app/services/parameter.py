from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from app.core.security import hash_password, verify_password
from app.models.parameter import SysParameter
from app.services.operation_log import record_operation_log
from app.services.secret_encryption import SecretEncryptionError, decrypt_secret, encrypt_secret
from app.services.mail_transport_policy import MAIL_TRANSPORT_MODES, transport_allowed
import re

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


def _mail_text(value):
    value = value.strip()
    if not value or len(value) > 254 or any(character.isspace() for character in value):
        raise HTTPException(422, '邮件参数须为不含空白的有效文本，最多254字符')
    return value


def _mail_port(value):
    if not value.isdigit() or not 1 <= int(value) <= 65535:
        raise HTTPException(422, 'SMTP端口须为1-65535')
    return str(int(value))


def _mail_security(value):
    if value not in MAIL_TRANSPORT_MODES:
        raise HTTPException(422, '请选择SSL、STARTTLS或已批准的内网模式')
    return value


def _mail_sender(value):
    value = _mail_text(value)
    if not re.fullmatch(r'[^@<>]+@[^@<>]+\.[^@<>]+', value):
        raise HTTPException(422, '请输入有效发件邮箱')
    return value


def _mail_password(value):
    if not 1 <= len(value) <= 256:
        raise HTTPException(422, '邮件授权密码须为1-256字符')
    return value


for _code, _name, _description, _validator, _default in (
    ('enabled', '邮件通知启用', '配置完成后开启；关闭不影响提报保存', validate_boolean, 'false'),
    ('host', 'SMTP服务地址', '公司邮件服务域名或内网地址', _mail_text, None),
    ('port', 'SMTP端口', '以公司配置为准；已批准的SRM内网入口仅允许25', _mail_port, '465'),
    ('security', 'SMTP连接方式', 'SSL/STARTTLS验证证书；内网模式仅限10.10.1.150:25，账号密码及邮件内容传输不加密，须使用专用账号', _mail_security, 'ssl'),
    ('sender', '邮件发件邮箱', '通知管理员和提报人使用的发件邮箱', _mail_sender, None),
    ('username', 'SMTP登录账号', '需要认证的邮件服务登录账号', _mail_text, None),
    ('password', 'SMTP授权密码', '加密保存、不回显；可使用邮件服务授权码', _mail_password, None),
):
    PARAMETERS['mail.' + _code] = dict(name=_name, group='邮件通知', description=_description,
        sensitive=_code == 'password', recoverable=_code == 'password',
        value_type='boolean' if _code == 'enabled' else 'text', validator=_validator,
        default=_default, max_length=256 if _code == 'password' else 254)
PARAMETERS['mail.security']['options'] = [{'value': 'ssl', 'label': 'SSL'}, {'value': 'starttls', 'label': 'STARTTLS'},
                                       {'value': 'internal', 'label': '内网专用（不加密）'}]


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
        stored = (row.secret_ciphertext if meta.get('recoverable') else row.secret_hash if meta["sensitive"] else row.value_text) if row else None
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
                          reveal_status=reveal_status, reveal_message=reveal_message, max_length=meta.get('max_length', 64), options=meta.get('options', [])))
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
    if code in ('mail.host', 'mail.port', 'mail.security'):
        connection = {key: db.get(SysParameter, 'mail.' + key) for key in ('host', 'port', 'security')}
        effective = {key: row.value_text if row and row.value_text is not None else PARAMETERS['mail.' + key].get('default')
                     for key, row in connection.items()}
        effective[code.removeprefix('mail.')] = value
        if not transport_allowed(effective['host'], effective['port'], effective['security']):
            raise HTTPException(422, '内网模式仅允许10.10.1.150:25；请先设置地址和端口，或先切换为SSL/STARTTLS')
    ciphertext = None
    if code == INITIAL_PASSWORD or meta.get('recoverable'):
        try:
            ciphertext = encrypt_secret(value, code)
        except SecretEncryptionError:
            raise HTTPException(503, "参数加密密钥不可用，参数未保存", headers={"Cache-Control": "no-store"}) from None
    values = {"secret_hash": hash_password(value) if meta["sensitive"] and not meta.get('recoverable') else None,
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
