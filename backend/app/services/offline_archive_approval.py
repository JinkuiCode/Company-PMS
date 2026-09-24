"""Bind the initial import to the approved V4 file and its server-parsed payload."""
import hashlib
import hmac
import json
from fastapi import HTTPException
from app.core.config import settings
from app.schemas.offline_archive import ImportPayload

APPROVED_FILE_HASH = "eb36f2f854bad50f63dee06d88dfa91efd863779f43f5c6a4e0de5da8ea98ca4"
APPROVED_ROW_COUNT = 3024

def _signature(payload, file_hash):
    if len(settings.SECRET_KEY) < 32:
        raise HTTPException(503, "导入验证密钥未配置，请联系管理员")
    normalized = ImportPayload.model_validate(payload).model_dump(mode="json")
    message = json.dumps({"purpose": "pms-approved-offline-v4", "file_hash": file_hash,
                          "payload": normalized}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(settings.SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()

def approve_payload(payload, file_hash):
    if file_hash != APPROVED_FILE_HASH or len(payload["rows"]) != APPROVED_ROW_COUNT:
        raise HTTPException(422, "仅支持已确认的第四版3024条档案，请选择原修订文件")
    return {**payload, "file_hash": file_hash, "approval_signature": _signature(payload, file_hash)}

def verify_payload(data):
    payload = {"rows": [row.model_dump(mode="json") for row in data.rows]}
    if data.file_hash != APPROVED_FILE_HASH or len(payload["rows"]) != APPROVED_ROW_COUNT:
        raise HTTPException(422, "导入来源不是已确认的第四版")
    if not hmac.compare_digest(data.approval_signature, _signature(payload, data.file_hash)):
        raise HTTPException(422, "导入内容已变化，请重新上传修订表预检")
    return payload
