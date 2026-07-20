"""项目档案生命周期并发、事务与 HTTP 三态契约测试。"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-project-archive-lifecycle-concurrency.db"

if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def _prepare_database():
    from app.core.database import Base, engine
    from app.models.dict import SysDict, SysDictItem  # noqa: F401
    from app.models.field_policy import SysBusinessFieldPolicy  # noqa: F401
    from app.models.operation_log import SysOperationLog  # noqa: F401
    from app.models.project import PmsProjectArchive  # noqa: F401
    from app.models.rbac import SysDept, SysMenu, SysRole  # noqa: F401
    from app.models.user import SysUser  # noqa: F401
    from app.services.enum_registry import initialize_enum_definitions

    Base.metadata.create_all(bind=engine)
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        initialize_enum_definitions(db)
    finally:
        db.close()


_prepare_database()


def _create_archive(code: str, *, enabled: int = 1) -> int:
    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive

    db = SessionLocal()
    try:
        archive = PmsProjectArchive(
            project_code=code,
            project_name=f"并发档案 {code}",
            is_enabled=enabled,
        )
        db.add(archive)
        db.commit()
        return archive.id
    finally:
        db.close()


def _create_project_context(code: str) -> tuple[int, int, int]:
    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.models.rbac import SysDept
    from app.models.user import SysUser

    db = SessionLocal()
    try:
        dept = SysDept(dept_name=f"并发部门 {code}", status=1)
        user = SysUser(
            username=f"concurrency-{code.lower()}",
            real_name=f"并发用户 {code}",
            password_hash="x",
            status=1,
        )
        db.add_all([dept, user])
        db.flush()
        archive = PmsProjectArchive(
            project_code=code,
            project_name=f"并发档案 {code}",
            manager_id=user.id,
            is_enabled=1,
        )
        db.add(archive)
        db.commit()
        return archive.id, dept.id, user.id
    finally:
        db.close()


def _project_create_data(archive_id: int, dept_id: int, user_id: int):
    from app.schemas.project import ProjectCreate

    return ProjectCreate(
        archive_id=archive_id,
        project_code=f"placeholder-{archive_id}",
        project_name=f"placeholder-{archive_id}",
        dept_id=dept_id,
        pm_id=user_id,
        status=1,
    )


class _SuccessfulKingdeeClient:
    constructed = threading.Event()
    external_release: threading.Event | None = None

    def __init__(self):
        self.constructed.set()

    def login(self) -> bool:
        if self.external_release is not None:
            assert self.external_release.wait(5), "测试未释放 ERP 外部调用"
        return True

    def query_assistant_data(self, **_kwargs):
        return None

    def save_assistant_data(self, **_kwargs):
        return {"success": True, "message": "ok"}

    def close(self):
        return None


class _AmbiguousKingdeeClient(_SuccessfulKingdeeClient):
    def save_assistant_data(self, **_kwargs):
        raise TimeoutError("ERP save response timed out")


def _run_in_thread(target):
    result: dict[str, object] = {}

    def runner():
        try:
            result["value"] = target()
        except Exception as exc:  # pragma: no cover - 由主线程断言异常类型
            result["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread, result


def test_archive_list_enabled_filter_has_explicit_http_tri_state():
    from fastapi.testclient import TestClient

    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.project import PmsProjectArchive
    from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole
    from app.models.user import SysUser
    from main import app

    db = SessionLocal()
    try:
        user = SysUser(
            username="archive-tristate-user",
            real_name="档案三态测试",
            password_hash="x",
            status=1,
        )
        role = SysRole(
            role_name="档案三态角色",
            role_code="archive-tristate-role",
            data_scope=1,
            status=1,
        )
        view_menu = SysMenu(
            parent_id=0,
            menu_name="档案查看三态",
            menu_type="B",
            permission_code="project:archive:view",
            status=1,
        )
        db.add_all([user, role, view_menu])
        db.flush()
        enabled_archive = PmsProjectArchive(
            project_code="TRISTATE-ENABLED",
            project_name="三态启用档案",
            manager_id=user.id,
            is_enabled=1,
        )
        disabled_archive = PmsProjectArchive(
            project_code="TRISTATE-DISABLED",
            project_name="三态禁用档案",
            manager_id=user.id,
            is_enabled=0,
        )
        db.add_all([enabled_archive, disabled_archive])
        db.flush()
        db.add_all([
            SysUserRole(user_id=user.id, role_id=role.id),
            SysRoleMenu(role_id=role.id, menu_id=view_menu.id),
        ])
        db.commit()
        token = create_access_token(subject=user.id)
        expected_enabled_id = enabled_archive.id
        expected_disabled_id = disabled_archive.id
    finally:
        db.close()

    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        omitted = client.get("/api/projects/archives/list", headers=headers)
        explicit_true = client.get(
            "/api/projects/archives/list?enabled=true", headers=headers
        )
        explicit_false = client.get(
            "/api/projects/archives/list?enabled=false", headers=headers
        )
        all_archives = client.get(
            "/api/projects/archives/list?enabled=all", headers=headers
        )
        invalid = client.get(
            "/api/projects/archives/list?enabled=sometimes", headers=headers
        )

    assert omitted.status_code == 200
    assert explicit_true.status_code == 200
    assert explicit_false.status_code == 200
    assert all_archives.status_code == 200
    assert invalid.status_code == 422

    omitted_ids = {item["id"] for item in omitted.json()["items"]}
    true_ids = {item["id"] for item in explicit_true.json()["items"]}
    false_ids = {item["id"] for item in explicit_false.json()["items"]}
    all_ids = {item["id"] for item in all_archives.json()["items"]}
    assert expected_enabled_id in omitted_ids == true_ids
    assert expected_disabled_id not in omitted_ids
    assert expected_disabled_id in false_ids
    assert expected_enabled_id not in false_ids
    assert {expected_enabled_id, expected_disabled_id}.issubset(all_ids)
    assert invalid.json()["detail"] == {
        "code": "ARCHIVE_ENABLED_FILTER_INVALID",
        "field": "enabled",
        "message": "enabled 仅支持 true、false 或 all",
    }


def test_lifecycle_mutations_rollback_when_commit_fails():
    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.services.project import (
        batch_change_archives_enabled,
        batch_delete_archives,
        change_archive_enabled,
        delete_archive,
    )

    single_delete_id = _create_archive("ROLLBACK-SINGLE-DELETE")
    batch_delete_ids = [
        _create_archive("ROLLBACK-BATCH-DELETE-1"),
        _create_archive("ROLLBACK-BATCH-DELETE-2"),
    ]
    single_toggle_id = _create_archive("ROLLBACK-SINGLE-TOGGLE")
    batch_toggle_ids = [
        _create_archive("ROLLBACK-BATCH-TOGGLE-1"),
        _create_archive("ROLLBACK-BATCH-TOGGLE-2"),
    ]

    operations = [
        lambda db: delete_archive(db, single_delete_id),
        lambda db: batch_delete_archives(db, batch_delete_ids),
        lambda db: change_archive_enabled(db, single_toggle_id, False),
        lambda db: batch_change_archives_enabled(db, batch_toggle_ids, False),
    ]
    for operation in operations:
        db = SessionLocal()
        try:
            with patch.object(db, "commit", side_effect=RuntimeError("commit failed")), patch.object(
                db, "rollback", wraps=db.rollback
            ) as rollback:
                try:
                    operation(db)
                except RuntimeError as exc:
                    assert str(exc) == "commit failed"
                else:
                    raise AssertionError("提交失败必须向上抛出")
                assert rollback.call_count == 1
        finally:
            db.close()

    verify = SessionLocal()
    try:
        assert verify.get(PmsProjectArchive, single_delete_id) is not None
        assert all(verify.get(PmsProjectArchive, item_id) is not None for item_id in batch_delete_ids)
        assert verify.get(PmsProjectArchive, single_toggle_id).is_enabled == 1
        assert all(
            verify.get(PmsProjectArchive, item_id).is_enabled == 1
            for item_id in batch_toggle_ids
        )
    finally:
        verify.close()


def test_batch_lifecycle_mutations_process_rows_in_fixed_id_order():
    from app.core.database import SessionLocal
    from app.services.project import batch_change_archives_enabled

    archive_ids = [
        _create_archive("ORDER-1"),
        _create_archive("ORDER-2"),
        _create_archive("ORDER-3"),
    ]
    observed_ids: list[int] = []

    def capture_log(_db, **kwargs):
        observed_ids.append(int(kwargs["entity_id"]))

    db = SessionLocal()
    try:
        with patch("app.services.project.record_operation_log", side_effect=capture_log):
            result = batch_change_archives_enabled(
                db,
                list(reversed(archive_ids)),
                enabled=False,
            )
        assert result["count"] == 3
        assert observed_ids == sorted(archive_ids)
    finally:
        db.close()


def test_mssql_lifecycle_query_uses_update_row_lock_and_fixed_order():
    from sqlalchemy import event
    from sqlalchemy.dialects import mssql

    from app.core.database import SessionLocal, engine
    from app.models.project import PmsProjectArchive
    from app.services.project_archive_lifecycle import (
        apply_archive_lifecycle_lock,
        load_archive_lifecycle_rows,
    )

    archive_ids = [
        _create_archive("MSSQL-ORDER-1"),
        _create_archive("MSSQL-ORDER-2"),
        _create_archive("MSSQL-ORDER-3"),
    ]
    selected_ids: list[int] = []

    def capture_select(_connection, _cursor, statement, parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT") and "pms_project_archive" in statement.lower():
            values = parameters if isinstance(parameters, (tuple, list)) else tuple(parameters.values())
            matching = [value for value in values if value in archive_ids]
            if matching:
                selected_ids.append(int(matching[-1]))

    event.listen(engine, "before_cursor_execute", capture_select)

    db = SessionLocal()
    try:
        query = apply_archive_lifecycle_lock(
            db.query(PmsProjectArchive),
            [archive_ids[0]],
        )
        compiled = str(query.statement.compile(dialect=mssql.dialect())).upper()
        rows = load_archive_lifecycle_rows(
            db.query(PmsProjectArchive), list(reversed(archive_ids))
        )
    finally:
        db.close()
        event.remove(engine, "before_cursor_execute", capture_select)

    assert "WITH (UPDLOCK, ROWLOCK, HOLDLOCK)" in compiled
    assert [row.id for row in rows] == sorted(archive_ids)
    assert selected_ids == sorted(archive_ids)


def test_sqlite_lifecycle_claim_does_not_change_archive_timestamp():
    import datetime

    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.services.project_archive_lifecycle import claim_archive_lifecycle_rows

    archive_id = _create_archive("CLAIM-TIMESTAMP")
    expected = datetime.datetime(2000, 1, 2, 3, 4, 5)
    setup = SessionLocal()
    try:
        archive = setup.get(PmsProjectArchive, archive_id)
        archive.updated_at = expected
        setup.commit()
    finally:
        setup.close()

    db = SessionLocal()
    try:
        assert claim_archive_lifecycle_rows(
            db.query(PmsProjectArchive), [archive_id]
        )[0].id == archive_id
        db.commit()
    finally:
        db.close()

    verify = SessionLocal()
    try:
        assert verify.get(PmsProjectArchive, archive_id).updated_at == expected
    finally:
        verify.close()


def test_delete_mutations_recheck_project_references_with_correlated_not_exists():
    from sqlalchemy import event

    from app.core.database import SessionLocal, engine
    from app.services.project import batch_delete_archives, delete_archive

    single_id = _create_archive("DELETE-NOT-EXISTS-SINGLE")
    batch_ids = [
        _create_archive("DELETE-NOT-EXISTS-BATCH-1"),
        _create_archive("DELETE-NOT-EXISTS-BATCH-2"),
    ]
    delete_sql: list[str] = []

    def capture_delete(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.strip().upper()
        if normalized.startswith("DELETE") and "PMS_PROJECT_ARCHIVE" in normalized:
            delete_sql.append(normalized)

    event.listen(engine, "before_cursor_execute", capture_delete)
    db = SessionLocal()
    try:
        delete_archive(db, single_id)
        batch_delete_archives(db, batch_ids)
    finally:
        db.close()
        event.remove(engine, "before_cursor_execute", capture_delete)

    assert len(delete_sql) == 2
    for statement in delete_sql:
        assert "EXISTS" in statement
        assert "PMS_PROJECT.ARCHIVE_ID" in statement


def test_blocked_delete_keeps_structured_conflict_when_operation_log_fails():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.project import PmsProject
    from app.services.project import batch_delete_archives, delete_archive

    single_archive_id, dept_id, user_id = _create_project_context("LOG-FAIL-SINGLE")
    batch_archive_id, _, _ = _create_project_context("LOG-FAIL-BATCH")
    db = SessionLocal()
    try:
        db.add_all([
            PmsProject(
                archive_id=single_archive_id,
                project_code="LOG-FAIL-SINGLE-PROJECT",
                project_name="日志失败单删引用",
                dept_id=dept_id,
                pm_id=user_id,
                status=1,
            ),
            PmsProject(
                archive_id=batch_archive_id,
                project_code="LOG-FAIL-BATCH-PROJECT",
                project_name="日志失败批删引用",
                dept_id=dept_id,
                pm_id=user_id,
                status=1,
            ),
        ])
        db.commit()

        for operation in (
            lambda: delete_archive(db, single_archive_id),
            lambda: batch_delete_archives(db, [batch_archive_id]),
        ):
            with patch("app.services.project.record_operation_log", side_effect=RuntimeError("log failed")):
                try:
                    operation()
                except HTTPException as exc:
                    assert exc.status_code == 409
                    assert exc.detail["code"] == "ARCHIVE_DELETE_BLOCKED"
                else:
                    raise AssertionError("日志失败不能覆盖删除保护响应")
            assert db.query(PmsProject).count() >= 2
    finally:
        db.close()


def test_pending_archive_edit_is_rejected_and_releases_transaction():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.schemas.project import ArchiveUpdate
    from app.services.project import update_archive

    archive_id = _create_archive("EDIT-PENDING")
    setup = SessionLocal()
    try:
        archive = setup.get(PmsProjectArchive, archive_id)
        archive.erp_sync_status = "pending"
        setup.commit()
    finally:
        setup.close()

    db = SessionLocal()
    try:
        try:
            update_archive(db, archive_id, ArchiveUpdate(project_name="不应写入"), user_id=1)
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_OPERATION_PENDING"
        else:
            raise AssertionError("同步结果不确定时必须拒绝编辑")
        assert not db.in_transaction()
    finally:
        db.close()


def test_blocked_lifecycle_operations_release_database_transaction():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.services.kingdee import sync_project_archive_to_erp
    from app.services.project import batch_change_archives_enabled, change_archive_enabled

    disabled_id = _create_archive("LOCK-RELEASE-DISABLED", enabled=0)
    pending_id = _create_archive("LOCK-RELEASE-PENDING")
    setup = SessionLocal()
    try:
        pending = setup.get(PmsProjectArchive, pending_id)
        pending.erp_sync_status = "pending"
        setup.commit()
    finally:
        setup.close()

    sync_db = SessionLocal()
    try:
        try:
            sync_project_archive_to_erp(sync_db, disabled_id)
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("禁用档案必须拒绝同步")
        assert not sync_db.in_transaction()
    finally:
        sync_db.close()

    toggle_db = SessionLocal()
    try:
        try:
            change_archive_enabled(toggle_db, pending_id, False)
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("同步中档案必须拒绝禁用")
        assert not toggle_db.in_transaction()
    finally:
        toggle_db.close()

    no_op_id = _create_archive("LOCK-RELEASE-NO-OP")
    no_op_db = SessionLocal()
    try:
        assert change_archive_enabled(no_op_db, no_op_id, True) == {"msg": "启用成功"}
        assert not no_op_db.in_transaction()
    finally:
        no_op_db.close()

    no_op_batch_db = SessionLocal()
    try:
        assert batch_change_archives_enabled(
            no_op_batch_db, [no_op_id], True
        ) == {"msg": "批量启用成功", "count": 0}
        assert not no_op_batch_db.in_transaction()
    finally:
        no_op_batch_db.close()


def test_project_create_and_delete_are_serialized_in_both_winner_orders():
    from fastapi import HTTPException
    from sqlalchemy import event

    from app.core.database import SessionLocal, engine
    from app.models.project import PmsProject, PmsProjectArchive
    from app.services.operation_log import record_operation_log as real_record_operation_log
    from app.services.project import create_project, delete_archive

    create_wins_id, create_wins_dept, create_wins_user = _create_project_context(
        "CREATE-WINS-DELETE"
    )
    create_reached_log = threading.Event()
    release_create = threading.Event()
    delete_write_started = threading.Event()

    def hold_create_log(db, **kwargs):
        if kwargs.get("module") == "项目进度" and kwargs.get("action") == "create":
            create_reached_log.set()
            assert release_create.wait(5), "测试未释放项目创建事务"
            return None
        return real_record_operation_log(db, **kwargs)

    def observe_delete_write(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lstrip().upper()
        if normalized.startswith(("UPDATE", "DELETE")) and "PMS_PROJECT_ARCHIVE" in normalized:
            delete_write_started.set()

    def run_create(archive_id: int, dept_id: int, user_id: int):
        db = SessionLocal()
        try:
            return create_project(
                db,
                _project_create_data(archive_id, dept_id, user_id),
                operator_id=user_id,
            )
        finally:
            db.close()

    def run_delete(archive_id: int):
        db = SessionLocal()
        try:
            return delete_archive(db, archive_id)
        finally:
            db.close()

    try:
        with patch("app.services.project.record_operation_log", side_effect=hold_create_log):
            create_thread, create_result = _run_in_thread(
                lambda: run_create(create_wins_id, create_wins_dept, create_wins_user)
            )
            assert create_reached_log.wait(5), "项目创建未到达提交前检查点"
            event.listen(engine, "before_cursor_execute", observe_delete_write)
            delete_thread, delete_result = _run_in_thread(lambda: run_delete(create_wins_id))
            assert delete_write_started.wait(5), "删除未尝试获取档案生命周期声明"
            release_create.set()
            create_thread.join(5)
            delete_thread.join(5)
    finally:
        release_create.set()
        try:
            event.remove(engine, "before_cursor_execute", observe_delete_write)
        except Exception:
            pass

    assert "error" not in create_result
    assert not create_thread.is_alive()
    assert not delete_thread.is_alive()
    delete_error = delete_result.get("error")
    assert isinstance(delete_error, HTTPException)
    assert delete_error.status_code == 409
    assert delete_error.detail["code"] == "ARCHIVE_DELETE_BLOCKED"

    verify = SessionLocal()
    try:
        assert verify.get(PmsProjectArchive, create_wins_id) is not None
        assert verify.query(PmsProject).filter(PmsProject.archive_id == create_wins_id).count() == 1
    finally:
        verify.close()

    delete_wins_id, delete_wins_dept, delete_wins_user = _create_project_context(
        "DELETE-WINS-CREATE"
    )
    delete_reached_log = threading.Event()
    release_delete = threading.Event()
    create_claim_started = threading.Event()

    def hold_delete_log(db, **kwargs):
        if kwargs.get("module") == "项目档案" and kwargs.get("action") == "delete":
            delete_reached_log.set()
            assert release_delete.wait(5), "测试未释放档案删除事务"
            return None
        return real_record_operation_log(db, **kwargs)

    def observe_create_claim(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lstrip().upper()
        if normalized.startswith("UPDATE") and "PMS_PROJECT_ARCHIVE" in normalized:
            create_claim_started.set()

    try:
        with patch("app.services.project.record_operation_log", side_effect=hold_delete_log):
            delete_thread, delete_result = _run_in_thread(lambda: run_delete(delete_wins_id))
            assert delete_reached_log.wait(5), "档案删除未到达提交前检查点"
            event.listen(engine, "before_cursor_execute", observe_create_claim)
            create_thread, create_result = _run_in_thread(
                lambda: run_create(delete_wins_id, delete_wins_dept, delete_wins_user)
            )
            assert create_claim_started.wait(5), "项目创建未声明档案生命周期"
            release_delete.set()
            delete_thread.join(5)
            create_thread.join(5)
    finally:
        release_delete.set()
        try:
            event.remove(engine, "before_cursor_execute", observe_create_claim)
        except Exception:
            pass

    assert "error" not in delete_result
    assert delete_result["value"] == {"msg": "删除成功"}
    create_error = create_result.get("error")
    assert isinstance(create_error, HTTPException)
    assert create_error.status_code == 404
    verify = SessionLocal()
    try:
        assert verify.get(PmsProjectArchive, delete_wins_id) is None
        assert verify.query(PmsProject).filter(PmsProject.archive_id == delete_wins_id).count() == 0
    finally:
        verify.close()


def test_project_create_and_disable_are_serialized_in_both_winner_orders():
    from fastapi import HTTPException
    from sqlalchemy import event

    from app.core.database import SessionLocal, engine
    from app.models.project import PmsProject, PmsProjectArchive
    from app.services.operation_log import record_operation_log as real_record_operation_log
    from app.services.project import change_archive_enabled, create_project

    def run_create(archive_id: int, dept_id: int, user_id: int):
        db = SessionLocal()
        try:
            return create_project(
                db,
                _project_create_data(archive_id, dept_id, user_id),
                operator_id=user_id,
            )
        finally:
            db.close()

    def run_disable(archive_id: int):
        db = SessionLocal()
        try:
            return change_archive_enabled(db, archive_id, False)
        finally:
            db.close()

    create_wins_id, create_wins_dept, create_wins_user = _create_project_context(
        "CREATE-WINS-DISABLE"
    )
    create_reached_log = threading.Event()
    release_create = threading.Event()
    disable_write_started = threading.Event()

    def hold_create_log(db, **kwargs):
        if kwargs.get("module") == "项目进度" and kwargs.get("action") == "create":
            create_reached_log.set()
            assert release_create.wait(5), "测试未释放项目创建事务"
            return None
        return real_record_operation_log(db, **kwargs)

    def observe_disable_write(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lstrip().upper()
        if normalized.startswith("UPDATE") and "PMS_PROJECT_ARCHIVE" in normalized:
            disable_write_started.set()

    try:
        with patch("app.services.project.record_operation_log", side_effect=hold_create_log):
            create_thread, create_result = _run_in_thread(
                lambda: run_create(create_wins_id, create_wins_dept, create_wins_user)
            )
            assert create_reached_log.wait(5), "项目创建未到达提交前检查点"
            event.listen(engine, "before_cursor_execute", observe_disable_write)
            disable_thread, disable_result = _run_in_thread(lambda: run_disable(create_wins_id))
            assert disable_write_started.wait(5), "禁用未尝试获取档案生命周期声明"
            release_create.set()
            create_thread.join(5)
            disable_thread.join(5)
    finally:
        release_create.set()
        try:
            event.remove(engine, "before_cursor_execute", observe_disable_write)
        except Exception:
            pass

    assert "error" not in create_result
    assert "error" not in disable_result
    verify = SessionLocal()
    try:
        assert verify.get(PmsProjectArchive, create_wins_id).is_enabled == 0
        assert verify.query(PmsProject).filter(PmsProject.archive_id == create_wins_id).count() == 1
    finally:
        verify.close()

    disable_wins_id, disable_wins_dept, disable_wins_user = _create_project_context(
        "DISABLE-WINS-CREATE"
    )
    disable_reached_log = threading.Event()
    release_disable = threading.Event()
    create_claim_started = threading.Event()

    def hold_disable_log(db, **kwargs):
        if kwargs.get("action") == "disable":
            disable_reached_log.set()
            assert release_disable.wait(5), "测试未释放档案禁用事务"
            return None
        return real_record_operation_log(db, **kwargs)

    def observe_create_claim(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lstrip().upper()
        if normalized.startswith("UPDATE") and "PMS_PROJECT_ARCHIVE" in normalized:
            create_claim_started.set()

    try:
        with patch(
            "app.services.project_archive_lifecycle.record_operation_log",
            side_effect=hold_disable_log,
        ):
            disable_thread, disable_result = _run_in_thread(lambda: run_disable(disable_wins_id))
            assert disable_reached_log.wait(5), "档案禁用未到达提交前检查点"
            event.listen(engine, "before_cursor_execute", observe_create_claim)
            create_thread, create_result = _run_in_thread(
                lambda: run_create(disable_wins_id, disable_wins_dept, disable_wins_user)
            )
            assert create_claim_started.wait(5), "项目创建未声明档案生命周期"
            release_disable.set()
            disable_thread.join(5)
            create_thread.join(5)
    finally:
        release_disable.set()
        try:
            event.remove(engine, "before_cursor_execute", observe_create_claim)
        except Exception:
            pass

    assert "error" not in disable_result
    create_error = create_result.get("error")
    assert isinstance(create_error, HTTPException)
    assert create_error.status_code == 409
    assert create_error.detail["code"] == "ARCHIVE_DISABLED"
    verify = SessionLocal()
    try:
        assert verify.get(PmsProjectArchive, disable_wins_id).is_enabled == 0
        assert verify.query(PmsProject).filter(PmsProject.archive_id == disable_wins_id).count() == 0
    finally:
        verify.close()


def test_disable_winner_prevents_concurrent_archive_edit():
    from fastapi import HTTPException
    from sqlalchemy import event

    from app.core.database import SessionLocal, engine
    from app.models.project import PmsProjectArchive
    from app.schemas.project import ArchiveUpdate
    from app.services.operation_log import record_operation_log as real_record_operation_log
    from app.services.project import change_archive_enabled, update_archive

    archive_id = _create_archive("DISABLE-WINS-EDIT")
    disable_reached_log = threading.Event()
    release_disable = threading.Event()
    edit_claim_started = threading.Event()

    def hold_disable_log(db, **kwargs):
        if kwargs.get("action") == "disable":
            disable_reached_log.set()
            assert release_disable.wait(5), "测试未释放档案禁用事务"
            return None
        return real_record_operation_log(db, **kwargs)

    def observe_edit_claim(_connection, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lstrip().upper()
        if normalized.startswith("UPDATE") and "PMS_PROJECT_ARCHIVE" in normalized:
            edit_claim_started.set()

    def run_disable():
        db = SessionLocal()
        try:
            return change_archive_enabled(db, archive_id, False)
        finally:
            db.close()

    def run_edit():
        db = SessionLocal()
        try:
            return update_archive(
                db,
                archive_id,
                ArchiveUpdate(project_name="竞态编辑不应成功"),
                user_id=1,
            )
        finally:
            db.close()

    try:
        with patch(
            "app.services.project_archive_lifecycle.record_operation_log",
            side_effect=hold_disable_log,
        ):
            disable_thread, disable_result = _run_in_thread(run_disable)
            assert disable_reached_log.wait(5), "档案禁用未到达提交前检查点"
            event.listen(engine, "before_cursor_execute", observe_edit_claim)
            edit_thread, edit_result = _run_in_thread(run_edit)
            assert edit_claim_started.wait(5), "档案编辑未声明生命周期"
            release_disable.set()
            disable_thread.join(5)
            edit_thread.join(5)
    finally:
        release_disable.set()
        try:
            event.remove(engine, "before_cursor_execute", observe_edit_claim)
        except Exception:
            pass

    assert "error" not in disable_result
    edit_error = edit_result.get("error")
    assert isinstance(edit_error, HTTPException)
    assert edit_error.status_code == 409
    assert edit_error.detail["code"] == "ARCHIVE_DISABLED"
    verify = SessionLocal()
    try:
        archive = verify.get(PmsProjectArchive, archive_id)
        assert archive.is_enabled == 0
        assert archive.project_name != "竞态编辑不应成功"
    finally:
        verify.close()


def test_erp_claim_rechecks_scope_and_latest_field_policy_before_client_creation():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.services.kingdee import sync_project_archive_to_erp
    from app.services.project import ensure_archive_access

    archive_id = _create_archive("ERP-SCOPE-TOCTOU")
    setup = SessionLocal()
    try:
        archive = setup.get(PmsProjectArchive, archive_id)
        archive.product_category = 1
        archive.customer = "授权时客户"
        setup.commit()
    finally:
        setup.close()

    scope_context = {
        "user_id": 1,
        "dept_id": None,
        "data_scope": 4,
        "product_category_ids": [1],
    }
    stale_authorization = SessionLocal()
    try:
        assert ensure_archive_access(stale_authorization, archive_id, scope_context).id == archive_id
        stale_authorization.rollback()

        mutate = SessionLocal()
        try:
            archive = mutate.get(PmsProjectArchive, archive_id)
            archive.product_category = 2
            mutate.commit()
        finally:
            mutate.close()

        _SuccessfulKingdeeClient.constructed = threading.Event()
        with patch("app.services.kingdee.KingdeeClient", _SuccessfulKingdeeClient):
            result = sync_project_archive_to_erp(
                stale_authorization,
                archive_id,
                scope_context=scope_context,
            )
        assert result == {"success": False, "message": "项目档案不存在"}
        assert not _SuccessfulKingdeeClient.constructed.is_set()
    finally:
        stale_authorization.close()

    manager_archive_id, _, allowed_user_id = _create_project_context("ERP-MANAGER-TOCTOU")
    manager_scope = {
        "user_id": allowed_user_id,
        "dept_id": None,
        "data_scope": 1,
        "product_category_ids": None,
    }
    manager_authorization = SessionLocal()
    try:
        assert ensure_archive_access(
            manager_authorization, manager_archive_id, manager_scope
        ).id == manager_archive_id
        manager_authorization.rollback()

        mutate = SessionLocal()
        try:
            archive = mutate.get(PmsProjectArchive, manager_archive_id)
            archive.manager_id = None
            mutate.commit()
        finally:
            mutate.close()

        _SuccessfulKingdeeClient.constructed = threading.Event()
        with patch("app.services.kingdee.KingdeeClient", _SuccessfulKingdeeClient):
            result = sync_project_archive_to_erp(
                manager_authorization,
                manager_archive_id,
                scope_context=manager_scope,
            )
        assert result == {"success": False, "message": "项目档案不存在"}
        assert not _SuccessfulKingdeeClient.constructed.is_set()
    finally:
        manager_authorization.close()

    latest_id = _create_archive("ERP-LATEST-POLICY")
    latest = SessionLocal()
    try:
        seen_customer: list[str | None] = []

        def reject_latest(_db, archive):
            seen_customer.append(archive.customer)
            raise HTTPException(status_code=422, detail="latest policy rejected")

        mutate = SessionLocal()
        try:
            archive = mutate.get(PmsProjectArchive, latest_id)
            archive.customer = "声明时最新客户"
            mutate.commit()
        finally:
            mutate.close()

        _SuccessfulKingdeeClient.constructed = threading.Event()
        with patch(
            "app.services.kingdee.validate_archive_for_business_operation",
            side_effect=reject_latest,
        ), patch("app.services.kingdee.KingdeeClient", _SuccessfulKingdeeClient):
            try:
                sync_project_archive_to_erp(latest, latest_id)
            except HTTPException as exc:
                assert exc.status_code == 422
            else:
                raise AssertionError("最新字段规则失败必须阻止 ERP 调用")
        assert seen_customer == ["声明时最新客户"]
        assert not _SuccessfulKingdeeClient.constructed.is_set()
        latest.expire_all()
        assert latest.get(PmsProjectArchive, latest_id).erp_sync_status is None
    finally:
        latest.close()


def test_erp_ambiguous_network_outcome_stays_pending_and_blocks_delete():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.services.kingdee import sync_project_archive_to_erp
    from app.services.project import delete_archive

    archive_id = _create_archive("ERP-NETWORK-AMBIGUOUS")
    db = SessionLocal()
    try:
        with patch("app.services.kingdee.KingdeeClient", _AmbiguousKingdeeClient):
            result = sync_project_archive_to_erp(db, archive_id)
        assert result["success"] is False
        db.expire_all()
        assert db.get(PmsProjectArchive, archive_id).erp_sync_status == "pending"
    finally:
        db.close()

    delete_db = SessionLocal()
    try:
        try:
            delete_archive(delete_db, archive_id)
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_DELETE_BLOCKED"
        else:
            raise AssertionError("ERP 网络结果不明时必须阻止物理删除")
    finally:
        delete_db.close()


def test_erp_success_with_local_commit_failure_stays_pending_and_blocks_delete():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.services.kingdee import sync_project_archive_to_erp
    from app.services.project import delete_archive

    archive_id = _create_archive("ERP-SUCCESS-COMMIT-FAIL")
    db = SessionLocal()
    real_commit = db.commit
    commit_count = 0

    def fail_success_commit():
        nonlocal commit_count
        commit_count += 1
        if commit_count == 2:
            raise RuntimeError("local success commit failed")
        return real_commit()

    try:
        _SuccessfulKingdeeClient.constructed = threading.Event()
        _SuccessfulKingdeeClient.external_release = None
        with patch("app.services.kingdee.KingdeeClient", _SuccessfulKingdeeClient), patch.object(
            db, "commit", side_effect=fail_success_commit
        ):
            result = sync_project_archive_to_erp(db, archive_id)
        assert result["success"] is False
        assert commit_count >= 2
        db.expire_all()
        assert db.get(PmsProjectArchive, archive_id).erp_sync_status == "pending"
    finally:
        db.close()

    delete_db = SessionLocal()
    try:
        try:
            delete_archive(delete_db, archive_id)
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_DELETE_BLOCKED"
        else:
            raise AssertionError("ERP 已成功但本地提交失败时必须阻止物理删除")
    finally:
        delete_db.close()


def test_delete_winner_prevents_sync_from_calling_external_system():
    from sqlalchemy import event

    from app.core.database import SessionLocal, engine
    from app.models.project import PmsProjectArchive
    from app.services.kingdee import sync_project_archive_to_erp
    from app.services.operation_log import record_operation_log as real_record_operation_log
    from app.services.project import delete_archive

    archive_id = _create_archive("RACE-DELETE-WINS")
    delete_reached_log = threading.Event()
    release_delete = threading.Event()
    sync_write_started = threading.Event()
    _SuccessfulKingdeeClient.constructed = threading.Event()
    _SuccessfulKingdeeClient.external_release = None

    def hold_delete_log(db, **kwargs):
        if kwargs.get("action") == "delete":
            delete_reached_log.set()
            assert release_delete.wait(5), "测试未释放删除事务"
            return None
        return real_record_operation_log(db, **kwargs)

    def observe_pending_write(
        _connection, _cursor, statement, parameters, _context, _executemany
    ):
        if (
            statement.lstrip().upper().startswith("UPDATE")
            and "pms_project_archive" in statement.lower()
            and "pending" in repr(parameters)
        ):
            sync_write_started.set()

    def run_delete():
        db = SessionLocal()
        try:
            return delete_archive(db, archive_id)
        finally:
            db.close()

    def run_sync():
        db = SessionLocal()
        try:
            return sync_project_archive_to_erp(db, archive_id)
        finally:
            db.close()

    event.listen(engine, "before_cursor_execute", observe_pending_write)
    try:
        with patch("app.services.project.record_operation_log", side_effect=hold_delete_log), patch(
            "app.services.kingdee.KingdeeClient", _SuccessfulKingdeeClient
        ):
            delete_thread, delete_result = _run_in_thread(run_delete)
            assert delete_reached_log.wait(5), "删除未到达提交前检查点"
            sync_thread, sync_result = _run_in_thread(run_sync)
            assert sync_write_started.wait(5), "同步未尝试声明 pending"
            assert not _SuccessfulKingdeeClient.constructed.wait(0.3)
            release_delete.set()
            delete_thread.join(5)
            sync_thread.join(5)
    finally:
        release_delete.set()
        event.remove(engine, "before_cursor_execute", observe_pending_write)

    assert not delete_thread.is_alive()
    assert not sync_thread.is_alive()
    assert "error" not in delete_result
    assert delete_result["value"] == {"msg": "删除成功"}
    assert not _SuccessfulKingdeeClient.constructed.is_set()
    assert "error" not in sync_result
    assert sync_result["value"]["success"] is False

    verify = SessionLocal()
    try:
        assert verify.get(PmsProjectArchive, archive_id) is None
    finally:
        verify.close()


def test_disable_winner_prevents_sync_and_sync_winner_blocks_delete_and_disable():
    from fastapi import HTTPException
    from sqlalchemy import event

    from app.core.database import SessionLocal, engine
    from app.models.project import PmsProjectArchive
    from app.services.kingdee import sync_project_archive_to_erp
    from app.services.operation_log import record_operation_log as real_record_operation_log
    from app.services.project import change_archive_enabled, delete_archive

    disable_winner_id = _create_archive("RACE-DISABLE-WINS")
    disable_reached_log = threading.Event()
    release_disable = threading.Event()
    sync_write_started = threading.Event()
    _SuccessfulKingdeeClient.constructed = threading.Event()
    _SuccessfulKingdeeClient.external_release = None

    def hold_disable_log(db, **kwargs):
        if kwargs.get("action") == "disable":
            disable_reached_log.set()
            assert release_disable.wait(5), "测试未释放禁用事务"
            return None
        return real_record_operation_log(db, **kwargs)

    def observe_pending_write(
        _connection, _cursor, statement, parameters, _context, _executemany
    ):
        if (
            statement.lstrip().upper().startswith("UPDATE")
            and "pms_project_archive" in statement.lower()
            and "pending" in repr(parameters)
        ):
            sync_write_started.set()

    def run_disable():
        db = SessionLocal()
        try:
            return change_archive_enabled(db, disable_winner_id, False)
        finally:
            db.close()

    def run_sync(archive_id: int):
        db = SessionLocal()
        try:
            return sync_project_archive_to_erp(db, archive_id)
        finally:
            db.close()

    event.listen(engine, "before_cursor_execute", observe_pending_write)
    try:
        with patch(
            "app.services.project_archive_lifecycle.record_operation_log",
            side_effect=hold_disable_log,
        ), patch("app.services.kingdee.KingdeeClient", _SuccessfulKingdeeClient):
            disable_thread, disable_result = _run_in_thread(run_disable)
            assert disable_reached_log.wait(5), "禁用未到达提交前检查点"
            sync_thread, sync_result = _run_in_thread(
                lambda: run_sync(disable_winner_id)
            )
            assert sync_write_started.wait(5), "同步未尝试声明 pending"
            assert not _SuccessfulKingdeeClient.constructed.wait(0.3)
            release_disable.set()
            disable_thread.join(5)
            sync_thread.join(5)
    finally:
        release_disable.set()
        event.remove(engine, "before_cursor_execute", observe_pending_write)

    assert "error" not in disable_result
    assert disable_result["value"] == {"msg": "禁用成功"}
    assert not _SuccessfulKingdeeClient.constructed.is_set()
    if error := sync_result.get("error"):
        assert isinstance(error, HTTPException)
        assert error.status_code in {404, 409}
    else:
        assert sync_result["value"]["success"] is False

    verify = SessionLocal()
    try:
        assert verify.get(PmsProjectArchive, disable_winner_id).is_enabled == 0
    finally:
        verify.close()

    sync_winner_id = _create_archive("RACE-SYNC-WINS")
    external_release = threading.Event()
    _SuccessfulKingdeeClient.constructed = threading.Event()
    _SuccessfulKingdeeClient.external_release = external_release
    with patch("app.services.kingdee.KingdeeClient", _SuccessfulKingdeeClient):
        sync_thread, sync_result = _run_in_thread(lambda: run_sync(sync_winner_id))
        assert _SuccessfulKingdeeClient.constructed.wait(5)

        delete_db = SessionLocal()
        try:
            try:
                delete_archive(delete_db, sync_winner_id)
            except HTTPException as exc:
                assert exc.status_code == 409
                assert exc.detail["code"] == "ARCHIVE_DELETE_BLOCKED"
            else:
                raise AssertionError("同步先赢时删除必须被阻止")
        finally:
            delete_db.close()

        disable_db = SessionLocal()
        try:
            try:
                change_archive_enabled(disable_db, sync_winner_id, False)
            except HTTPException as exc:
                assert exc.status_code == 409
                assert exc.detail["code"] == "ARCHIVE_OPERATION_PENDING"
            else:
                raise AssertionError("同步先赢时禁用必须被阻止")
        finally:
            disable_db.close()

        external_release.set()
        sync_thread.join(5)

    assert not sync_thread.is_alive()
    assert "error" not in sync_result
    assert sync_result["value"]["success"] is True


if __name__ == "__main__":
    test_archive_list_enabled_filter_has_explicit_http_tri_state()
    test_lifecycle_mutations_rollback_when_commit_fails()
    test_batch_lifecycle_mutations_process_rows_in_fixed_id_order()
    test_mssql_lifecycle_query_uses_update_row_lock_and_fixed_order()
    test_sqlite_lifecycle_claim_does_not_change_archive_timestamp()
    test_delete_mutations_recheck_project_references_with_correlated_not_exists()
    test_blocked_delete_keeps_structured_conflict_when_operation_log_fails()
    test_pending_archive_edit_is_rejected_and_releases_transaction()
    test_blocked_lifecycle_operations_release_database_transaction()
    test_project_create_and_delete_are_serialized_in_both_winner_orders()
    test_project_create_and_disable_are_serialized_in_both_winner_orders()
    test_disable_winner_prevents_concurrent_archive_edit()
    test_erp_claim_rechecks_scope_and_latest_field_policy_before_client_creation()
    test_erp_ambiguous_network_outcome_stays_pending_and_blocks_delete()
    test_erp_success_with_local_commit_failure_stays_pending_and_blocks_delete()
    test_delete_winner_prevents_sync_from_calling_external_system()
    test_disable_winner_prevents_sync_and_sync_winner_blocks_delete_and_disable()
    print("project archive lifecycle concurrency contract passed")
