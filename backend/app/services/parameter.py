from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from app.core.security import hash_password
from app.models.parameter import SysParameter
from app.services.operation_log import record_operation_log

INITIAL_PASSWORD = "user.initial_password"


def validate_initial_password(value):
    if not 1 <= len(value) <= 64:
        raise HTTPException(422, "初始密码须为 1-64 个字符")
    return value


PARAMETERS = {INITIAL_PASSWORD: dict(name="用户初始密码", group="用户管理", description="新增用户和重置密码使用的初始密码",
                                    sensitive=True, value_type="text", validator=validate_initial_password)}


def list_parameters(db):
    rows = {row.code: row for row in db.query(SysParameter).all()}
    items = []
    for code, meta in PARAMETERS.items():
        row = rows.get(code)
        stored = (row.secret_hash if meta["sensitive"] else row.value_text) if row else None
        items.append(dict(code=code, **{key: meta[key] for key in ("name", "group", "description", "sensitive")},
                          configured=stored is not None, version=row.version if row else 0,
                          updated_at=row.updated_at if row else None, value=None if meta["sensitive"] else stored))
    return {"items": items}


def update_parameter(db, code, value, version, operator_id, request=None):
    if code not in PARAMETERS:
        raise HTTPException(404, "参数不存在")
    if len(value) > 16384:
        raise HTTPException(422, "参数值过长")
    meta = PARAMETERS[code]
    validator = meta.get("validator")
    if validator:
        value = validator(value)
    values = {"secret_hash": hash_password(value) if meta["sensitive"] else None,
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
    return {"message": "参数已更新", "version": version + 1}


def initial_password_hash(db):
    row = db.get(SysParameter, INITIAL_PASSWORD)
    if not row or not row.secret_hash:
        raise HTTPException(409, "请先配置用户初始密码参数")
    return row.secret_hash
