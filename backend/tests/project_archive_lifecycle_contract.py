"""项目档案生命周期字段与迁移契约测试。"""
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-project-archive-lifecycle.db"
LEGACY_DB_PATH = ROOT / "data" / "pms-test-project-archive-lifecycle-legacy.db"

for database_path in (DB_PATH, LEGACY_DB_PATH):
    if database_path.exists():
        database_path.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def test_archive_enabled_model_and_idempotent_upgrade():
    from sqlalchemy import create_engine, inspect, text

    from app.core.database import Base
    from app.models.project import PmsProjectArchive
    from app.models.rbac import SysDept  # noqa: F401
    from app.models.user import SysUser  # noqa: F401
    from app.services.project_archive_lifecycle_migration import upgrade_project_archive_lifecycle

    assert PmsProjectArchive.__table__.columns.is_enabled.type.python_type is int
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(bind=engine)
    upgrade_project_archive_lifecycle(engine)
    upgrade_project_archive_lifecycle(engine)
    columns = {item["name"] for item in inspect(engine).get_columns("pms_project_archive")}
    assert "is_enabled" in columns
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO pms_project_archive "
            "(project_code, project_code_key, project_name, project_name_key, status, erp_synced) "
            "VALUES ('LC-001', 'lc-001', '生命周期测试', '生命周期测试', 1, 0)"
        ))
        assert connection.execute(text(
            "SELECT is_enabled FROM pms_project_archive WHERE project_code='LC-001'"
        )).scalar_one() == 1


def test_archive_lifecycle_upgrades_historical_schema():
    from sqlalchemy import create_engine, inspect, text

    from app.services.project_archive_lifecycle_migration import upgrade_project_archive_lifecycle

    with sqlite3.connect(LEGACY_DB_PATH) as connection:
        connection.executescript("""
            CREATE TABLE pms_project_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_code NVARCHAR(32) NOT NULL UNIQUE,
                project_code_key NVARCHAR(32) NOT NULL,
                project_name NVARCHAR(128) NOT NULL,
                project_name_key NVARCHAR(128) NOT NULL,
                status INTEGER DEFAULT 1,
                erp_synced INTEGER DEFAULT 0
            );
            INSERT INTO pms_project_archive (
                project_code, project_code_key, project_name, project_name_key, status, erp_synced
            ) VALUES ('LEGACY-001', 'legacy-001', '历史档案', '历史档案', 1, 0);
        """)

    engine = create_engine(f"sqlite:///{LEGACY_DB_PATH}")
    assert "is_enabled" not in {
        item["name"] for item in inspect(engine).get_columns("pms_project_archive")
    }

    upgrade_project_archive_lifecycle(engine)
    upgrade_project_archive_lifecycle(engine)

    inspector = inspect(engine)
    columns = {item["name"] for item in inspector.get_columns("pms_project_archive")}
    indexes = {item["name"] for item in inspector.get_indexes("pms_project_archive")}
    assert "is_enabled" in columns
    assert "idx_project_archive_enabled" in indexes
    with engine.begin() as connection:
        assert connection.execute(text(
            "SELECT is_enabled FROM pms_project_archive WHERE project_code='LEGACY-001'"
        )).scalar_one() == 1


def test_archive_delete_guards_and_enabled_lifecycle():
    from fastapi import HTTPException
    from sqlalchemy import event

    from app.core.database import Base, SessionLocal, engine
    from app.models.operation_log import SysOperationLog
    from app.models.project import ErpSyncLog, PmsProject, PmsProjectArchive
    from app.models.rbac import SysDept
    from app.models.user import SysUser
    from app.schemas.project import ArchiveDeleteBlocker
    from app.services.project_archive_lifecycle import (
        ensure_archive_enabled,
        get_archive_delete_guard,
        get_archive_delete_guards,
        set_archive_enabled,
    )

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = SysUser(
            username="archive-lifecycle",
            real_name="生命周期测试",
            password_hash="x",
            status=1,
        )
        dept = SysDept(dept_name="生命周期测试部门", status=1)
        db.add_all([user, dept])
        db.commit()

        def create_archive(
            code: str,
            *,
            enabled: int = 1,
            pending: bool = False,
            erp_synced: int = 0,
        ) -> PmsProjectArchive:
            archive = PmsProjectArchive(
                project_code=code,
                project_name=f"项目档案 {code}",
                is_enabled=enabled,
                erp_synced=erp_synced,
                erp_sync_status="pending" if pending else None,
            )
            db.add(archive)
            db.flush()
            return archive

        available = create_archive("LC-AVAILABLE")
        referenced = create_archive("LC-REFERENCED")
        failed_only = create_archive("LC-FAILED")
        historical_success = create_archive("LC-SUCCESS")
        synced_without_log = create_archive("LC-SYNCED-FLAG", erp_synced=1)
        pending = create_archive("LC-PENDING", pending=True)
        disabled = create_archive("LC-DISABLED", enabled=0)
        disabled_pending = create_archive("LC-DISABLED-PENDING", enabled=0, pending=True)
        db.add_all([
            PmsProject(
                archive_id=referenced.id,
                project_code="LC-001",
                project_name="引用项目",
                dept_id=dept.id,
                pm_id=user.id,
                status=1,
            ),
            ErpSyncLog(source_id=failed_only.id, action="sync", status="failed"),
            ErpSyncLog(source_id=historical_success.id, action="sync", status="failed"),
            ErpSyncLog(source_id=historical_success.id, action="sync", status="success"),
        ])
        db.commit()

        assert ArchiveDeleteBlocker(
            type="business_reference",
            source="project_progress",
            label="项目进度",
            count=1,
        ).model_dump() == {
            "type": "business_reference",
            "source": "project_progress",
            "label": "项目进度",
            "count": 1,
        }
        assert get_archive_delete_guard(db, available.id) == {
            "can_delete": True,
            "blockers": [],
        }

        referenced_guard = get_archive_delete_guard(db, referenced.id)
        assert referenced_guard == {
            "can_delete": False,
            "blockers": [{
                "type": "business_reference",
                "source": "project_progress",
                "label": "项目进度",
                "count": 1,
            }],
        }
        assert get_archive_delete_guard(db, failed_only.id) == {
            "can_delete": True,
            "blockers": [],
        }
        assert get_archive_delete_guard(db, historical_success.id) == {
            "can_delete": False,
            "blockers": [{
                "type": "external_sync",
                "source": "kingdee",
                "label": "金蝶 ERP",
                "count": 1,
            }],
        }
        assert get_archive_delete_guard(db, synced_without_log.id) == {
            "can_delete": False,
            "blockers": [{
                "type": "external_sync",
                "source": "kingdee",
                "label": "金蝶 ERP",
                "count": 1,
            }],
        }
        assert get_archive_delete_guard(db, pending.id) == {
            "can_delete": False,
            "blockers": [{
                "type": "operation_pending",
                "source": "kingdee",
                "label": "ERP 同步中",
                "count": 1,
            }],
        }

        select_statements: list[str] = []

        def track_select(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(engine, "before_cursor_execute", track_select)
        try:
            guards = get_archive_delete_guards(
                db,
                [
                    available.id,
                    referenced.id,
                    historical_success.id,
                    synced_without_log.id,
                    pending.id,
                    available.id,
                ],
            )
        finally:
            event.remove(engine, "before_cursor_execute", track_select)
        assert set(guards) == {
            available.id,
            referenced.id,
            historical_success.id,
            synced_without_log.id,
            pending.id,
        }
        assert len(select_statements) == 3

        try:
            ensure_archive_enabled(disabled, "编辑")
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == {
                "code": "ARCHIVE_DISABLED",
                "message": "项目档案已禁用，无法编辑，请先重新启用",
            }
        else:
            raise AssertionError("禁用档案必须拒绝编辑")
        ensure_archive_enabled(available, "编辑")

        assert set_archive_enabled(db, disabled, False, user.id, None) == {"msg": "禁用成功"}
        assert db.query(SysOperationLog).filter(SysOperationLog.entity_id == str(disabled.id)).count() == 0
        disabled_pending_logs = db.query(SysOperationLog).filter(
            SysOperationLog.entity_id == str(disabled_pending.id)
        ).count()
        with patch.object(db, "commit", wraps=db.commit) as commit:
            assert set_archive_enabled(db, disabled_pending, False, user.id, None) == {"msg": "禁用成功"}
            assert commit.call_count == 0
        assert disabled_pending.is_enabled == 0
        assert db.query(SysOperationLog).filter(
            SysOperationLog.entity_id == str(disabled_pending.id)
        ).count() == disabled_pending_logs
        assert set_archive_enabled(db, disabled, True, user.id, None) == {"msg": "启用成功"}
        assert disabled.is_enabled == 1
        assert [log.action for log in db.query(SysOperationLog).filter(
            SysOperationLog.entity_id == str(disabled.id)
        ).all()] == ["enable"]
        assert set_archive_enabled(db, disabled, True, user.id, None) == {"msg": "启用成功"}
        assert set_archive_enabled(db, disabled, False, user.id, None) == {"msg": "禁用成功"}
        assert disabled.is_enabled == 0
        assert [log.action for log in db.query(SysOperationLog).filter(
            SysOperationLog.entity_id == str(disabled.id)
        ).order_by(SysOperationLog.id).all()] == ["enable", "disable"]

        try:
            set_archive_enabled(db, pending, False, user.id, None)
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_OPERATION_PENDING"
        else:
            raise AssertionError("同步中的档案必须拒绝禁用")
        assert pending.is_enabled == 1
    finally:
        db.close()


def test_archive_lifecycle_is_enforced_by_project_delete_batch_and_erp():
    from fastapi import HTTPException

    from app.core.database import Base, SessionLocal, engine
    from app.models.operation_log import SysOperationLog
    from app.models.project import PmsProject, PmsProjectArchive
    from app.models.rbac import SysDept
    from app.models.user import SysUser
    from app.schemas.project import ArchiveUpdate, ProjectCreate
    from app.services.kingdee import batch_sync_project_archives, sync_project_archive_to_erp
    from app.services.project import (
        batch_change_archives_enabled,
        batch_delete_archives,
        create_project,
        delete_archive,
        get_archive_list,
        get_archive_options,
        update_archive,
    )
    from app.services.project_archive_lifecycle import get_archive_delete_guards

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = SysUser(
            username="archive-lifecycle-enforcement",
            real_name="档案保护测试",
            password_hash="x",
            status=1,
        )
        dept = SysDept(dept_name="档案保护部门", status=1)
        db.add_all([user, dept])
        db.commit()

        def create_archive(
            code: str,
            *,
            enabled: int = 1,
            pending: bool = False,
            product_category: int | None = None,
        ) -> PmsProjectArchive:
            archive = PmsProjectArchive(
                project_code=code,
                project_name=f"项目档案 {code}",
                is_enabled=enabled,
                erp_sync_status="pending" if pending else None,
                product_category=product_category,
            )
            db.add(archive)
            db.flush()
            return archive

        enabled_archive = create_archive("ENF-ENABLED")
        disabled_archive = create_archive("ENF-DISABLED", enabled=0)
        referenced_archive = create_archive("ENF-REFERENCED")
        db.add(PmsProject(
            archive_id=referenced_archive.id,
            project_code="ENF-PROJECT-REFERENCED",
            project_name="已引用项目",
            dept_id=dept.id,
            pm_id=user.id,
            status=1,
        ))
        db.commit()

        option_ids = {item.id for item in get_archive_options(db)}
        assert enabled_archive.id in option_ids
        assert disabled_archive.id not in option_ids

        enabled_list = get_archive_list(db, page=1, page_size=100, enabled=True)
        assert enabled_archive.id in {item.id for item in enabled_list["items"]}
        assert disabled_archive.id not in {item.id for item in enabled_list["items"]}

        disabled_list = get_archive_list(db, page=1, page_size=100, enabled=False)
        assert disabled_archive.id in {item.id for item in disabled_list["items"]}
        assert enabled_archive.id not in {item.id for item in disabled_list["items"]}

        with patch(
            "app.services.project.get_archive_delete_guards",
            wraps=get_archive_delete_guards,
        ) as get_guards:
            all_list = get_archive_list(db, page=1, page_size=100, enabled=None)
        assert get_guards.call_count == 1
        assert get_guards.call_args.args[1] == [item.id for item in all_list["items"]]
        all_items = {item.id: item for item in all_list["items"]}
        assert all_items[disabled_archive.id].is_enabled == 0
        assert all_items[referenced_archive.id].can_delete is False
        assert all_items[referenced_archive.id].delete_blockers[0].type == "business_reference"

        try:
            create_project(
                db,
                ProjectCreate(
                    archive_id=disabled_archive.id,
                    project_code=disabled_archive.project_code,
                    project_name=disabled_archive.project_name,
                    dept_id=dept.id,
                    pm_id=user.id,
                ),
                operator_id=user.id,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_DISABLED"
        else:
            raise AssertionError("禁用档案不得建立项目进度")

        try:
            update_archive(
                db,
                disabled_archive.id,
                ArchiveUpdate(customer="不应写入"),
                user_id=user.id,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_DISABLED"
        else:
            raise AssertionError("禁用档案不得编辑")

        with patch("app.services.kingdee.KingdeeClient") as client_factory:
            try:
                sync_project_archive_to_erp(db, disabled_archive.id, user_id=user.id)
            except HTTPException as exc:
                assert exc.status_code == 409
                assert exc.detail["code"] == "ARCHIVE_DISABLED"
            else:
                raise AssertionError("禁用档案不得同步 ERP")
            assert client_factory.call_count == 0
        db.refresh(disabled_archive)
        assert disabled_archive.erp_sync_status is None

        with patch("app.services.kingdee.KingdeeClient") as client_factory:
            batch_sync = batch_sync_project_archives(db, [disabled_archive.id], user_id=user.id)
        assert batch_sync["success_count"] == 0
        assert batch_sync["failed_count"] == 1
        assert "已禁用" in batch_sync["errors"][0]
        assert client_factory.call_count == 0

        try:
            delete_archive(db, referenced_archive.id, operator_id=user.id)
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_DELETE_BLOCKED"
            assert exc.detail["suggested_action"] == "disable"
            assert exc.detail["blockers"][0]["type"] == "business_reference"
        else:
            raise AssertionError("被引用档案不能删除")
        failed_delete_log = db.query(SysOperationLog).filter(
            SysOperationLog.entity_id == str(referenced_archive.id),
            SysOperationLog.action == "delete",
            SysOperationLog.status == "failed",
        ).order_by(SysOperationLog.id.desc()).first()
        assert failed_delete_log is not None
        assert "business_reference" in (failed_delete_log.after_data or "")

        protected_batch_candidate = create_archive("ENF-BATCH-PROTECTED")
        db.commit()
        try:
            batch_delete_archives(
                db,
                [protected_batch_candidate.id, referenced_archive.id],
                operator_id=user.id,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail["code"] == "ARCHIVE_DELETE_BLOCKED"
        else:
            raise AssertionError("批量删除必须在存在保护项时整体失败")
        assert db.get(PmsProjectArchive, protected_batch_candidate.id) is not None
        assert db.get(PmsProjectArchive, referenced_archive.id) is not None
        failed_batch_delete_log = db.query(SysOperationLog).filter(
            SysOperationLog.action == "batch_delete",
            SysOperationLog.status == "failed",
        ).order_by(SysOperationLog.id.desc()).first()
        assert failed_batch_delete_log is not None

        removable_archive = create_archive("ENF-BATCH-REMOVABLE")
        db.commit()
        with patch.object(db, "commit", wraps=db.commit) as commit:
            deleted = batch_delete_archives(db, [removable_archive.id], operator_id=user.id)
        assert deleted["count"] == 1
        assert commit.call_count == 1
        assert db.get(PmsProjectArchive, removable_archive.id) is None

        pending_archive = create_archive("ENF-BATCH-PENDING", pending=True)
        toggle_target = create_archive("ENF-BATCH-TOGGLE")
        db.commit()
        with patch.object(db, "commit", wraps=db.commit) as commit:
            try:
                batch_change_archives_enabled(
                    db,
                    [toggle_target.id, pending_archive.id],
                    enabled=False,
                    operator_id=user.id,
                    request=None,
                )
            except HTTPException as exc:
                assert exc.status_code == 409
                assert exc.detail["code"] == "ARCHIVE_OPERATION_PENDING"
            else:
                raise AssertionError("包含同步中档案的批量禁用必须整体失败")
        assert commit.call_count == 0
        db.refresh(toggle_target)
        db.refresh(pending_archive)
        assert toggle_target.is_enabled == 1
        assert pending_archive.is_enabled == 1

        scope_allowed = create_archive("ENF-SCOPE-ALLOWED", product_category=1)
        scope_denied = create_archive("ENF-SCOPE-DENIED", product_category=2)
        db.commit()
        restricted_scope = {
            "user_id": user.id,
            "dept_id": None,
            "data_scope": 4,
            "product_category_ids": [1],
        }
        try:
            batch_change_archives_enabled(
                db,
                [scope_allowed.id, scope_denied.id],
                enabled=False,
                operator_id=user.id,
                request=None,
                scope_context=restricted_scope,
            )
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("批量启停不得跳过产品类别数据范围")
        db.refresh(scope_allowed)
        db.refresh(scope_denied)
        assert scope_allowed.is_enabled == 1
        assert scope_denied.is_enabled == 1

        with patch.object(db, "commit", wraps=db.commit) as commit:
            changed = batch_change_archives_enabled(
                db,
                [disabled_archive.id],
                enabled=True,
                operator_id=user.id,
                request=None,
            )
        assert changed["count"] == 1
        assert commit.call_count == 1
        db.refresh(disabled_archive)
        assert disabled_archive.is_enabled == 1
    finally:
        db.close()


def test_batch_archive_routes_enforce_permissions_and_static_order():
    from fastapi.testclient import TestClient

    from app.core.database import Base, SessionLocal, engine
    from app.core.security import create_access_token
    from app.models.project import PmsProjectArchive
    from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole
    from app.models.user import SysUser
    from main import app

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = SysUser(
            username="archive-lifecycle-route",
            real_name="档案路由测试",
            password_hash="x",
            status=1,
        )
        role = SysRole(
            role_name="档案启停测试角色",
            role_code="archive-lifecycle-route",
            data_scope=4,
            status=1,
        )
        toggle_menu = SysMenu(
            parent_id=0,
            menu_name="档案启停",
            menu_type="B",
            permission_code="project:archive:toggle",
            status=1,
        )
        archive = PmsProjectArchive(
            project_code="ENF-ROUTE",
            project_name="路由权限档案",
            is_enabled=0,
        )
        db.add_all([user, role, toggle_menu, archive])
        db.flush()
        db.add_all([
            SysUserRole(user_id=user.id, role_id=role.id),
            SysRoleMenu(role_id=role.id, menu_id=toggle_menu.id),
        ])
        db.commit()
        token = create_access_token(subject=user.id)
        archive_id = archive.id
    finally:
        db.close()

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {token}"}
        enabled = client.put(
            "/api/projects/archives/batch-enabled",
            headers=headers,
            json={"archive_ids": [archive_id], "enabled": True},
        )
        assert enabled.status_code == 200
        denied_delete = client.post(
            "/api/projects/archives/batch-delete",
            headers=headers,
            json={"archive_ids": [archive_id]},
        )
        assert denied_delete.status_code == 403


if __name__ == "__main__":
    test_archive_enabled_model_and_idempotent_upgrade()
    test_archive_lifecycle_upgrades_historical_schema()
    test_archive_delete_guards_and_enabled_lifecycle()
    test_archive_lifecycle_is_enforced_by_project_delete_batch_and_erp()
    test_batch_archive_routes_enforce_permissions_and_static_order()
    print("project archive lifecycle contract passed")
