"""金蝶销售项目期初档案的只读预检规则。"""
from collections import Counter
from collections.abc import Iterable, Mapping
import hashlib
import json
from typing import Any


DATA_ORIGIN_KINGDEE_INITIAL = "kingdee_initial"


def _clean(value: Any) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def preflight_initial_archives(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    existing_codes: Iterable[str] = (),
) -> dict[str, Any]:
    """Classify sales-project rows; never infer a PMS name from Kingdee ProjectName."""
    rows = [
        {
            "project_code": _clean(row.get("ProjectCode")),
            "project_name": _clean(row.get("Remarks")),
            "kingdee_name": _clean(row.get("ProjectName")),
            "source_id": row.get("ProjectID"),
            "data_origin": DATA_ORIGIN_KINGDEE_INITIAL,
        }
        for row in source_rows
        if _clean(row.get("TypeCode")) == "xsxm"
    ]
    code_counts = Counter(row["project_code"].casefold() for row in rows if row["project_code"])
    old_codes = {_clean(code).casefold() for code in existing_codes if _clean(code)}
    ready: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    legacy_name_differences: list[str] = []

    for row in rows:
        code = row["project_code"]
        name = row["project_name"]
        if code and row["kingdee_name"] and code != row["kingdee_name"]:
            legacy_name_differences.append(code)
        reason: str | None = None
        if not code or len(code) > 32 or (name and len(name) > 128):
            reason = "invalid_length_or_code"
        elif code_counts[code.casefold()] > 1:
            reason = "duplicate_code"
        elif code.casefold() in old_codes:
            reason = "existing_code"

        if reason:
            issues.append({**row, "reason": reason})
        else:
            ready.append({
                "project_code": code,
                "project_name": name,
                "source_id": row["source_id"],
                "data_origin": DATA_ORIGIN_KINGDEE_INITIAL,
            })
    return {
        "source_count": len(rows),
        "ready": ready,
        "issues": issues,
        "legacy_name_differences": legacy_name_differences,
    }


def preflight_fingerprint(report: Mapping[str, Any]) -> str:
    payload = {
        "source_count": report["source_count"],
        "ready": sorted(report["ready"], key=lambda row: (row["project_code"], str(row["source_id"]))),
        "issues": sorted(report["issues"], key=lambda row: (row["project_code"] or "", str(row["source_id"]))),
        "legacy_name_differences": sorted(report["legacy_name_differences"]),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def insert_initial_archives(db: Any, ready: Iterable[Mapping[str, Any]], *, operator_id: int | None) -> int:
    """Stage validated rows in the caller's transaction; never call Kingdee."""
    from app.models.project import PmsProjectArchive
    from app.services.operation_log import record_operation_log, serialize_model

    count = 0
    for row in ready:
        archive = PmsProjectArchive(
            project_code=row["project_code"],
            project_name=row["project_name"],
            data_origin=DATA_ORIGIN_KINGDEE_INITIAL,
            is_enabled=1,
            erp_synced=0,
            erp_sync_status="historical",
            erp_sync_time=None,
            erp_sync_by=None,
            created_by=operator_id,
            updated_by=operator_id,
        )
        db.add(archive)
        db.flush()
        record_operation_log(
            db,
            module="项目档案",
            action="import",
            entity_type="pms_project_archive",
            entity_id=archive.id,
            entity_name=archive.project_name or archive.project_code,
            operator_id=operator_id,
            summary=f"导入金蝶期初档案：{archive.project_code}",
            after_data={**serialize_model(archive), "source_project_id": row.get("source_id")},
        )
        count += 1
    return count
