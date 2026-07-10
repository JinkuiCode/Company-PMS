"""统一操作日志服务。"""
from __future__ import annotations

import datetime
import decimal
import json
from typing import Any

from fastapi import Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.operation_log import SysOperationLog
from app.models.user import SysUser


SENSITIVE_KEYWORDS = (
    "password",
    "password_hash",
    "token",
    "remember_token",
    "secret",
    "sign",
    "key",
)
MASK_VALUE = "***"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(word in lowered for word in SENSITIVE_KEYWORDS)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value


def sanitize_data(data: Any) -> Any:
    """递归脱敏并转换为可 JSON 化的数据。"""
    if data is None:
        return None
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            result[key] = MASK_VALUE if _is_sensitive_key(str(key)) else sanitize_data(value)
        return result
    if isinstance(data, (list, tuple, set)):
        return [sanitize_data(item) for item in data]
    return _normalize_value(data)


def serialize_model(model: Any, exclude: set[str] | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """把 SQLAlchemy 模型快照为字典，供 before/after 使用。"""
    if model is None:
        return {}
    exclude = exclude or set()
    result: dict[str, Any] = {}
    for column in model.__table__.columns:
        if column.name in exclude:
            continue
        result[column.name] = _normalize_value(getattr(model, column.name))
    if extra:
        result.update({key: _normalize_value(value) for key, value in extra.items()})
    return result


def diff_data(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """计算字段级差异。"""
    before_raw = before or {}
    after_raw = after or {}
    diff: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before_raw.keys()) | set(after_raw.keys())):
        old_raw = before_raw.get(key)
        new_raw = after_raw.get(key)
        if old_raw != new_raw:
            diff[key] = {
                "before": sanitize_data({key: old_raw})[key],
                "after": sanitize_data({key: new_raw})[key],
            }
    return diff


def _json_dumps(data: Any) -> str | None:
    if data is None:
        return None
    return json.dumps(sanitize_data(data), ensure_ascii=False, default=str)


def _request_meta(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {"ip_address": None, "user_agent": None, "request_path": None, "request_method": None}
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else None)
    return {
        "ip_address": ip_address,
        "user_agent": request.headers.get("user-agent"),
        "request_path": request.url.path,
        "request_method": request.method,
    }


def _operator_name(db: Session, operator_id: int | None) -> str | None:
    if operator_id is None:
        return None
    user = db.query(SysUser).filter(SysUser.id == operator_id).first()
    if not user:
        return None
    return user.real_name or user.username


def record_operation_log(
    db: Session,
    *,
    module: str,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    entity_name: str | None = None,
    operator_id: int | None = None,
    request: Request | None = None,
    status: str = "success",
    summary: str | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    error_msg: str | None = None,
    commit: bool = False,
) -> SysOperationLog:
    """写入系统操作日志。

    调用方在业务事务中记录时保持 commit=False；认证/同步等独立场景可传 commit=True。
    """
    before_clean = sanitize_data(before_data)
    after_clean = sanitize_data(after_data)
    diff_clean = diff_data(before_data, after_data) if before_data is not None or after_data is not None else None
    meta = _request_meta(request)
    resolved_summary = summary or f"{module}{action}"

    log = SysOperationLog(
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        entity_name=entity_name,
        operator_id=operator_id,
        operator_name=_operator_name(db, operator_id),
        ip_address=meta["ip_address"],
        user_agent=meta["user_agent"],
        request_path=meta["request_path"],
        request_method=meta["request_method"],
        status=status,
        summary=resolved_summary,
        error_msg=error_msg,
        before_data=_json_dumps(before_clean),
        after_data=_json_dumps(after_clean),
        diff_data=_json_dumps(diff_clean),
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    return log


def get_operation_logs(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 15,
    module: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    operator_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    start_time: datetime.datetime | None = None,
    end_time: datetime.datetime | None = None,
) -> dict[str, Any]:
    query = db.query(SysOperationLog)

    if module:
        query = query.filter(SysOperationLog.module == module)
    if action:
        query = query.filter(SysOperationLog.action == action)
    if entity_type:
        query = query.filter(SysOperationLog.entity_type == entity_type)
    if operator_id is not None:
        query = query.filter(SysOperationLog.operator_id == operator_id)
    if status:
        query = query.filter(SysOperationLog.status == status)
    if start_time:
        query = query.filter(SysOperationLog.created_at >= start_time)
    if end_time:
        query = query.filter(SysOperationLog.created_at <= end_time)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                SysOperationLog.summary.like(like),
                SysOperationLog.entity_name.like(like),
                SysOperationLog.entity_id.like(like),
                SysOperationLog.operator_name.like(like),
                SysOperationLog.request_path.like(like),
            )
        )

    total = query.count()
    items = (
        query.order_by(SysOperationLog.created_at.desc(), SysOperationLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": items}
