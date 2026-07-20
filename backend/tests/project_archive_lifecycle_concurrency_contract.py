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
    from app.models.operation_log import SysOperationLog  # noqa: F401
    from app.models.project import PmsProjectArchive  # noqa: F401
    from app.models.rbac import SysDept, SysMenu, SysRole  # noqa: F401
    from app.models.user import SysUser  # noqa: F401

    Base.metadata.create_all(bind=engine)


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
    from sqlalchemy.dialects import mssql

    from app.core.database import SessionLocal
    from app.models.project import PmsProjectArchive
    from app.services.project_archive_lifecycle import apply_archive_lifecycle_lock

    db = SessionLocal()
    try:
        query = apply_archive_lifecycle_lock(
            db.query(PmsProjectArchive),
            [9, 3, 7, 3],
        )
        compiled = str(query.statement.compile(dialect=mssql.dialect())).upper()
    finally:
        db.close()

    assert "WITH (UPDLOCK, ROWLOCK, HOLDLOCK)" in compiled
    assert "ORDER BY PMS_PROJECT_ARCHIVE.ID" in compiled


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
    test_blocked_lifecycle_operations_release_database_transaction()
    test_delete_winner_prevents_sync_from_calling_external_system()
    test_disable_winner_prevents_sync_and_sync_winner_blocks_delete_and_disable()
    print("project archive lifecycle concurrency contract passed")
