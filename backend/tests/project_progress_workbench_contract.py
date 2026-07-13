"""项目进度工作台统一保存契约测试。"""
import os
from pathlib import Path
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DB_DIALECT", "sqlite")
os.environ.setdefault("SQLITE_DB_PATH", "data/pms-test-progress-workbench.db")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_workbench_save_contract_uses_one_transaction_and_one_log():
    schema = read("app/schemas/project.py")
    service = read("app/services/project.py")
    api = read("app/api/projects.py")

    assert "ProjectProgressDrawerUpdate" in schema
    assert "project_values" in schema
    assert "class ProjectSheetDetailUpdate" in schema
    assert "update_project_sheet_detail" in service
    assert "validate_project_progress_workbench_updates" in service
    assert 'entity_type="pms_project"' in service
    assert "db.rollback()" in service
    assert '@router.put("/{project_id}/sheet-detail"' in api


def test_workbench_save_only_accepts_editable_project_sheet_fields():
    from app.services.project import validate_project_progress_workbench_updates

    accepted = validate_project_progress_workbench_updates(
        {"status": 1, "end_date": "2026-08-31", "design_progress": 0}
    )
    assert accepted == {"status": 1, "end_date": "2026-08-31", "design_progress": 0}

    for payload in [{"product_line": "Bench"}, {"project_name": "不可从进度页修改"}, {"unknown": "x"}]:
        try:
            validate_project_progress_workbench_updates(payload)
        except ValueError as exc:
            assert "不可编辑" in str(exc) or "未知字段" in str(exc)
        else:
            raise AssertionError(f"{payload} should be rejected")


def test_workbench_save_updates_both_sources_once_and_rejects_partial_writes():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.init_db import init_db
    from app.models.operation_log import SysOperationLog
    from app.models.project import PmsProject, PmsProjectSheetDetail
    from app.schemas.project import ProjectSheetDetailUpdate
    from app.services.project import update_project_sheet_detail

    init_db()
    db = SessionLocal()
    try:
        project = db.query(PmsProject).first()
        assert project is not None
        old_log_count = db.query(SysOperationLog).count()
        customer = f"原子保存-{uuid4().hex}"
        saved_progress = 17 if project.design_progress != 17 else 18

        update_project_sheet_detail(
            db,
            project.id,
            ProjectSheetDetailUpdate(
                values={"customer": customer},
                project_values={"design_progress": saved_progress},
            ),
            operator_id=1,
            scope_context={"data_scope": 4, "product_lines": None},
        )

        db.refresh(project)
        detail = db.query(PmsProjectSheetDetail).filter(PmsProjectSheetDetail.project_id == project.id).first()
        log = db.query(SysOperationLog).order_by(SysOperationLog.id.desc()).first()
        assert project.design_progress == saved_progress
        assert detail is not None and customer in (detail.detail_data or "")
        assert db.query(SysOperationLog).count() == old_log_count + 1
        assert log is not None and '"project.design_progress"' in (log.diff_data or "")
        assert '"detail.customer"' in (log.diff_data or "")

        try:
            update_project_sheet_detail(
                db,
                project.id,
                ProjectSheetDetailUpdate(
                    values={"product_line": "不允许从进度页修改"},
                    project_values={"design_progress": 57},
                ),
                operator_id=1,
                scope_context={"data_scope": 4, "product_lines": None},
            )
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("invalid detail values should reject the whole workbench save")

        db.refresh(project)
        assert project.design_progress == saved_progress
    finally:
        db.close()


if __name__ == "__main__":
    test_workbench_save_contract_uses_one_transaction_and_one_log()
    test_workbench_save_only_accepts_editable_project_sheet_fields()
    test_workbench_save_updates_both_sources_once_and_rejects_partial_writes()
    print("project progress workbench contract passed")
