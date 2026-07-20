"""RBAC 运行时授权契约测试。"""
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-rbac.db"

if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_authorization_context_uses_only_active_roles_and_live_permissions():
    from fastapi import HTTPException

    from app.core.database import Base, SessionLocal, engine
    from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole
    from app.models.user import SysUser
    from app.services.authorization import build_authorization_context, enforce_permission

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = SysUser(username="rbac-user", real_name="权限用户", password_hash="x", status=1, dept_id=7)
        active_role = SysRole(
            role_name="有效角色",
            role_code="active-role",
            data_scope=2,
            product_category_ids="1,3",
            status=1,
        )
        disabled_role = SysRole(
            role_name="禁用角色",
            role_code="disabled-role",
            data_scope=4,
            product_category_ids=None,
            status=0,
        )
        edit_menu = SysMenu(
            parent_id=0,
            menu_name="项目编辑",
            menu_type="B",
            permission_code="project:list:edit",
            status=1,
        )
        delete_menu = SysMenu(
            parent_id=0,
            menu_name="项目删除",
            menu_type="B",
            permission_code="project:list:delete",
            status=1,
        )
        db.add_all([user, active_role, disabled_role, edit_menu, delete_menu])
        db.flush()
        db.add_all([
            SysUserRole(user_id=user.id, role_id=active_role.id),
            SysUserRole(user_id=user.id, role_id=disabled_role.id),
            SysRoleMenu(role_id=active_role.id, menu_id=edit_menu.id),
            SysRoleMenu(role_id=disabled_role.id, menu_id=delete_menu.id),
        ])
        db.commit()

        context = build_authorization_context(db, user.id)
        assert context["role_codes"] == ["active-role"]
        assert context["permissions"] == ["project:list:edit"]
        assert context["data_scope"] == 2
        assert set(context["product_category_ids"]) == {1, 3}
        enforce_permission(context, "project:list:edit")

        try:
            enforce_permission(context, "project:list:delete")
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("禁用角色的删除权限不应生效")

        db.query(SysRoleMenu).filter(
            SysRoleMenu.role_id == active_role.id,
            SysRoleMenu.menu_id == edit_menu.id,
        ).delete()
        db.commit()
        refreshed = build_authorization_context(db, user.id)
        assert "project:list:edit" not in refreshed["permissions"]
    finally:
        db.close()


def test_disabled_user_is_rejected_on_every_context_load():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.user import SysUser
    from app.services.authorization import build_authorization_context

    db = SessionLocal()
    try:
        user = SysUser(username="disabled-user", real_name="禁用用户", password_hash="x", status=0)
        db.add(user)
        db.commit()
        try:
            build_authorization_context(db, user.id)
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("禁用用户持有旧 JWT 时也必须被拒绝")
    finally:
        db.close()


def test_multiple_active_roles_merge_permissions_and_widest_scope():
    from app.core.database import SessionLocal
    from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole
    from app.models.user import SysUser
    from app.services.authorization import build_authorization_context

    db = SessionLocal()
    try:
        user = SysUser(username="multi-role-user", real_name="多角色用户", password_hash="x", status=1)
        narrow_role = SysRole(
            role_name="本人角色",
            role_code="scope-self",
            data_scope=1,
            product_category_ids="1",
            status=1,
        )
        wide_role = SysRole(
            role_name="全部角色",
            role_code="scope-all",
            data_scope=4,
            product_category_ids=None,
            status=1,
        )
        view_menu = SysMenu(
            parent_id=0,
            menu_name="项目查看并集",
            menu_type="B",
            permission_code="project:list:view:union-test",
            status=1,
        )
        edit_menu = SysMenu(
            parent_id=0,
            menu_name="项目编辑并集",
            menu_type="B",
            permission_code="project:list:edit:union-test",
            status=1,
        )
        db.add_all([user, narrow_role, wide_role, view_menu, edit_menu])
        db.flush()
        db.add_all([
            SysUserRole(user_id=user.id, role_id=narrow_role.id),
            SysUserRole(user_id=user.id, role_id=wide_role.id),
            SysRoleMenu(role_id=narrow_role.id, menu_id=view_menu.id),
            SysRoleMenu(role_id=wide_role.id, menu_id=edit_menu.id),
        ])
        db.commit()

        context = build_authorization_context(db, user.id)
        assert set(context["permissions"]) == {
            "project:list:view:union-test",
            "project:list:edit:union-test",
        }
        assert context["data_scope"] == 4
        assert context["product_category_ids"] is None
    finally:
        db.close()


def test_project_scope_denies_missing_department_and_uses_archive_product_category():
    from fastapi import HTTPException

    from app.core.database import Base, SessionLocal, engine
    from app.models.project import PmsProject, PmsProjectArchive
    from app.schemas.project import ProjectUpdate
    from app.services.project import ensure_project_access, update_project

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        archive = PmsProjectArchive(
            project_code="RBAC-ARCHIVE",
            project_name="RBAC 档案",
            product_category=1,
            status=1,
        )
        db.add(archive)
        db.flush()
        project = PmsProject(
            project_code="RBAC-PROJECT",
            project_name="RBAC 项目",
            archive_id=archive.id,
            product_category=3,
            dept_id=1,
            pm_id=1,
            status=1,
        )
        db.add(project)
        db.commit()

        no_dept_context = {
            "user_id": 1,
            "dept_id": None,
            "data_scope": 2,
            "product_category_ids": None,
        }
        try:
            ensure_project_access(db, project.id, no_dept_context)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("未绑定部门时不应退化为全部数据")

        stale_fallback_context = {
            "user_id": 1,
            "dept_id": None,
            "data_scope": 4,
            "product_category_ids": [3],
        }
        try:
            ensure_project_access(db, project.id, stale_fallback_context)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("已关联档案时不得用项目旧产品线绕过档案产品线权限")

        unrestricted_context = {
            "user_id": 1,
            "dept_id": None,
            "data_scope": 4,
            "product_category_ids": None,
        }
        try:
            update_project(
                db,
                project.id,
                ProjectUpdate(product_category=3),
                user_id=1,
                scope_context=unrestricted_context,
            )
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("项目编辑权限不得绕过档案权限修改引用产品线")
        db.refresh(archive)
        assert archive.product_category == 1
    finally:
        db.close()


def test_role_menu_normalization_validates_nodes_and_adds_view_and_ancestors():
    from app.core.database import SessionLocal
    from app.models.rbac import SysMenu
    from app.services.rbac import normalize_role_menu_ids

    db = SessionLocal()
    try:
        root = SysMenu(parent_id=0, menu_name="项目管理", menu_type="M", status=1)
        page = SysMenu(parent_id=0, menu_name="项目进度", menu_type="C", status=1)
        db.add_all([root, page])
        db.flush()
        page.parent_id = root.id
        view = SysMenu(
            parent_id=page.id,
            menu_name="查看",
            menu_type="B",
            permission_code="project:list:view",
            status=1,
        )
        delete = SysMenu(
            parent_id=page.id,
            menu_name="删除",
            menu_type="B",
            permission_code="project:list:delete",
            status=1,
        )
        db.add_all([view, delete])
        db.commit()

        normalized = normalize_role_menu_ids(db, [delete.id])
        assert normalized == [root.id, page.id, view.id, delete.id]
        page_only = normalize_role_menu_ids(db, [page.id])
        assert page_only == [root.id, page.id, view.id]
    finally:
        db.close()


def test_init_db_does_not_restore_revoked_admin_permission():
    from app.core.database import SessionLocal
    from app.models.init_db import init_db
    from app.models.rbac import SysMenu, SysRole, SysRoleMenu, SysUserRole
    from app.models.user import SysUser

    db = SessionLocal()
    try:
        admin = db.query(SysUser).filter(SysUser.username == "admin").first()
        if not admin:
            admin = SysUser(username="admin", real_name="系统管理员", password_hash="x", status=1)
            db.add(admin)
        role = db.query(SysRole).filter(SysRole.role_code == "admin").first()
        if not role:
            role = SysRole(role_name="超级管理员", role_code="admin", data_scope=4, status=1)
            db.add(role)
        db.flush()
        if not db.query(SysUserRole).filter_by(user_id=admin.id, role_id=role.id).first():
            db.add(SysUserRole(user_id=admin.id, role_id=role.id))
        db.commit()
    finally:
        db.close()

    init_db()
    db = SessionLocal()
    try:
        role = db.query(SysRole).filter(SysRole.role_code == "admin").one()
        menu = db.query(SysMenu).filter(SysMenu.id == 214).one()
        if not db.query(SysRoleMenu).filter_by(role_id=role.id, menu_id=menu.id).first():
            db.add(SysRoleMenu(role_id=role.id, menu_id=menu.id))
            db.commit()
        db.query(SysRoleMenu).filter(
            SysRoleMenu.role_id == role.id,
            SysRoleMenu.menu_id == menu.id,
        ).delete()
        db.commit()
    finally:
        db.close()

    init_db()
    db = SessionLocal()
    try:
        role = db.query(SysRole).filter(SysRole.role_code == "admin").one()
        menu = db.query(SysMenu).filter(SysMenu.id == 214).one()
        restored = db.query(SysRoleMenu).filter(
            SysRoleMenu.role_id == role.id,
            SysRoleMenu.menu_id == menu.id,
        ).first()
        assert restored is None
    finally:
        db.close()


def test_permission_dependencies_and_matrix_are_wired_to_apis():
    authorization = read("app/services/authorization.py")
    projects = read("app/api/projects.py")
    erp = read("app/api/erp.py")
    operation_logs = read("app/api/operation_logs.py")
    sso = read("app/api/sso.py")
    main = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "def require_permission" in authorization
    assert "def require_any_permission" in authorization
    for permission in [
        "project:list:view",
        "project:list:add",
        "project:list:edit",
        "project:list:delete",
        "project:archive:view",
        "project:archive:add",
        "project:archive:edit",
        "project:archive:delete",
    ]:
        assert permission in projects
    assert "project:archive:sync" in erp
    assert "system:operation-log:view" in operation_logs
    assert "dashboard:view" in main
    assert 'require_permission("system:user:edit")' in sso
    assert "sso_url_generate" in sso


def test_same_jwt_observes_permission_revoke_and_restore_immediately():
    from fastapi.testclient import TestClient

    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.rbac import SysMenu, SysRole, SysRoleMenu
    from app.models.user import SysUser
    from main import app

    db = SessionLocal()
    try:
        admin = db.query(SysUser).filter(SysUser.username == "admin").one()
        role = db.query(SysRole).filter(SysRole.role_code == "admin").one()
        delete_menu = db.query(SysMenu).filter(SysMenu.id == 214).one()
        db.query(SysRoleMenu).filter_by(role_id=role.id, menu_id=delete_menu.id).delete()
        db.commit()
        role_id = role.id
        delete_menu_id = delete_menu.id
        token = create_access_token(subject=admin.id)
    finally:
        db.close()

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {token}"}
        denied = client.delete("/api/projects/999999", headers=headers)
        assert denied.status_code == 403

        db = SessionLocal()
        try:
            db.add(SysRoleMenu(role_id=role_id, menu_id=delete_menu_id))
            db.commit()
        finally:
            db.close()

        restored = client.delete("/api/projects/999999", headers=headers)
        assert restored.status_code == 404


def test_local_recovery_script_contract():
    script = read("scripts/recover_role_permissions.py")
    assert "--role-code" in script
    assert "--all" in script
    assert "normalize_role_menu_ids" in script
    assert "SysRoleMenu" in script


def test_role_data_scope_is_constrained_on_create_update_and_storage():
    from pydantic import ValidationError

    from app.schemas.rbac import RoleUpdate

    for invalid_scope in (0, 5):
        try:
            RoleUpdate(data_scope=invalid_scope)
        except ValidationError:
            pass
        else:
            raise AssertionError("角色更新不得写入 1-4 之外的数据范围")

    role_model = read("app/models/rbac.py")
    authorization = read("app/services/authorization.py")
    assert "ck_sys_role_data_scope" in role_model
    assert "1 <= role.data_scope <= 4" in authorization


def test_role_templates_and_sso_default_are_fail_closed():
    templates = read("app/services/role_templates.py")
    sso = read("app/services/sso.py")

    assert '"business_admin"' in templates
    assert '"operator"' in templates
    assert '"project:archive:sync"' in templates
    assert '"project:archive:toggle"' in templates
    assert '"system:field-policy:edit"' in templates
    assert '"system:operation-log:view"' in templates
    assert 'role_code == "operator"' in sso
    assert "SysRole.status == 1" in sso
    assert "默认操作员角色不存在或已禁用" in sso
    assert "db.query(SysRole).first()" not in sso


def test_sso_new_user_gets_only_active_operator_role():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.rbac import SysRole, SysUserRole
    from app.models.user import SysUser
    from app.services.sso import find_or_create_user

    db = SessionLocal()
    try:
        operator = db.query(SysRole).filter(SysRole.role_code == "operator").first()
        if not operator:
            operator = SysRole(
                role_name="SSO 操作员",
                role_code="operator",
                data_scope=3,
                status=1,
            )
            db.add(operator)
        else:
            operator.status = 1
        db.commit()

        user = find_or_create_user(db, "oa-operator-user", "OA 操作员", "")
        role_ids = {
            role_id for (role_id,) in db.query(SysUserRole.role_id).filter(
                SysUserRole.user_id == user.id
            ).all()
        }
        assert role_ids == {operator.id}

        operator.status = 0
        db.commit()
        try:
            find_or_create_user(db, "oa-role-missing-user", "OA 缺省角色", "")
        except HTTPException as exc:
            assert exc.status_code == 503
        else:
            raise AssertionError("操作员角色禁用时 SSO 自动开户必须失败关闭")
        assert db.query(SysUser).filter(SysUser.username == "oa-role-missing-user").first() is None
    finally:
        db.close()


if __name__ == "__main__":
    test_authorization_context_uses_only_active_roles_and_live_permissions()
    test_disabled_user_is_rejected_on_every_context_load()
    test_multiple_active_roles_merge_permissions_and_widest_scope()
    test_project_scope_denies_missing_department_and_uses_archive_product_category()
    test_role_menu_normalization_validates_nodes_and_adds_view_and_ancestors()
    test_init_db_does_not_restore_revoked_admin_permission()
    test_permission_dependencies_and_matrix_are_wired_to_apis()
    test_same_jwt_observes_permission_revoke_and_restore_immediately()
    test_local_recovery_script_contract()
    test_role_data_scope_is_constrained_on_create_update_and_storage()
    test_role_templates_and_sso_default_are_fail_closed()
    test_sso_new_user_gets_only_active_operator_role()
    print("rbac permission contract passed")
