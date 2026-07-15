"""业务枚举注册、维护边界与历史兼容契约测试。"""
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "pms-test-enum-management.db"
if DB_PATH.exists():
    DB_PATH.unlink()

os.environ["DB_DIALECT"] = "sqlite"
os.environ["SQLITE_DB_PATH"] = str(DB_PATH)


def seed_enum(db, code: str, items: list[tuple[str, str, int]]):
    from app.models.dict import SysDict, SysDictItem

    existing = db.query(SysDict).filter(SysDict.dict_code == code).first()
    if existing:
        db.query(SysDictItem).filter(SysDictItem.dict_id == existing.id).delete()
        db.delete(existing)
        db.commit()
    definition = SysDict(dict_code=code, dict_name=code, status=1)
    db.add(definition)
    db.flush()
    for sort, (value, label, status) in enumerate(items, 1):
        db.add(SysDictItem(
            dict_id=definition.id,
            item_value=value,
            item_label=label,
            sort=sort,
            status=status,
        ))
    db.commit()
    return definition


def test_registry_separates_managed_system_and_legacy_definitions():
    from app.services.enum_registry import (
        LEGACY_DICT_CODES,
        MANAGED_ENUM_CODES,
        SYSTEM_ENUM_CODES,
        ENUM_REGISTRY,
    )

    assert MANAGED_ENUM_CODES == {
        "archive_status",
        "project_status",
        "product_category",
        "equipment_series",
        "task_status",
    }
    assert SYSTEM_ENUM_CODES == {"erp_sync_status", "data_scope"}
    assert LEGACY_DICT_CODES == {
        "user_manage",
        "role_manage",
        "project_list",
        "project_archive",
        "project_task",
    }
    assert ENUM_REGISTRY["product_category"]["mode"] == "configurable"
    assert ENUM_REGISTRY["product_category"]["value_strategy"] == "numeric_sequence"
    assert ENUM_REGISTRY["equipment_series"]["value_strategy"] == "numeric_sequence"
    assert ENUM_REGISTRY["archive_status"]["mode"] == "workflow"


def test_enum_list_hides_unregistered_and_system_definitions():
    from app.models.field_policy import SysBusinessFieldPolicy  # noqa: F401
    from app.core.database import Base, SessionLocal, engine
    from app.services.dict import get_dict_list

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_enum(db, "product_category", [("1", "Bench", 1)])
        seed_enum(db, "data_scope", [("4", "全部", 1)])
        seed_enum(db, "custom_history", [("A", "历史自建", 1)])

        result = get_dict_list(db)
        assert [item["dict_code"] for item in result] == ["product_category"]
        assert result[0]["allow_add"] is True
        assert result[0]["mode"] == "configurable"
        assert result[0]["item_count"] == 1
    finally:
        db.close()


def test_workflow_values_are_locked_but_labels_and_status_can_change():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.dict import SysDictItem
    from app.schemas.dict import DictItemCreate, DictItemUpdate
    from app.services.dict import create_dict_item, update_dict_item

    db = SessionLocal()
    try:
        definition = seed_enum(db, "project_status", [("1", "进行中", 1)])
        item = db.query(SysDictItem).filter(SysDictItem.dict_id == definition.id).one()

        try:
            create_dict_item(
                db,
                definition.id,
                DictItemCreate(item_value="4", item_label="已取消"),
            )
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("固定流程枚举不允许新增存储值")

        try:
            update_dict_item(db, item.id, DictItemUpdate(item_value="9"))
        except HTTPException as exc:
            assert exc.status_code == 400
        else:
            raise AssertionError("固定流程枚举不允许修改存储值")

        update_dict_item(
            db,
            item.id,
            DictItemUpdate(item_label="执行中", sort=2, status=0),
        )
        db.refresh(item)
        assert item.item_label == "执行中"
        assert item.status == 0
    finally:
        db.close()


def test_disabled_values_keep_history_labels_and_new_writes_are_validated():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.services.dict import get_dict_by_code
    from app.services.enum_registry import validate_enum_value

    db = SessionLocal()
    try:
        seed_enum(db, "task_status", [("1", "未开始", 1), ("2", "进行中", 0)])
        result = get_dict_by_code(db, "task_status")
        assert result["items"] == [{"value": "1", "label": "未开始"}]
        assert result["label_map"] == {"1": "未开始", "2": "进行中"}
        assert len(result["all_items"]) == 2

        assert validate_enum_value(db, "task_status", 2, current_value=2) == "2"
        try:
            validate_enum_value(db, "task_status", 2, current_value=1)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("禁用枚举不应允许用于新变更")
    finally:
        db.close()


def test_referenced_configurable_value_cannot_be_deleted():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.dict import SysDictItem
    from app.models.project import PmsProjectArchive
    from app.services.dict import delete_dict_item, get_dict_items

    db = SessionLocal()
    try:
        definition = seed_enum(db, "product_category", [("1", "Bench", 1)])
        item = db.query(SysDictItem).filter(SysDictItem.dict_id == definition.id).one()
        db.add(PmsProjectArchive(
            project_code="ENUM-REF-001",
            project_name="枚举引用项目",
            product_category=1,
            status=1,
        ))
        db.commit()

        listed = get_dict_items(db, definition.id)
        assert listed[0]["reference_count"] == 1
        assert listed[0]["deletable"] is False

        try:
            delete_dict_item(db, item.id)
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("已引用枚举值不可删除")
    finally:
        db.close()


def test_project_writes_reject_unknown_or_disabled_enum_values():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.schemas.project import ArchiveCreate
    from app.services.project import create_archive

    db = SessionLocal()
    try:
        seed_enum(db, "archive_status", [("1", "未启动", 1)])
        seed_enum(db, "product_category", [("1", "Bench", 0)])
        seed_enum(db, "equipment_series", [("1", "链式", 1)])
        for code, payload in [
            (
                "archive_status",
                ArchiveCreate(
                    project_code="ENUM-INVALID-STATUS",
                    project_name="非法状态",
                    status=99,
                    product_category=None,
                    equipment_series=1,
                ),
            ),
            (
                "product_category",
                ArchiveCreate(
                    project_code="ENUM-DISABLED-LINE",
                    project_name="禁用产品线",
                    status=1,
                    product_category=1,
                    equipment_series=1,
                ),
            ),
        ]:
            try:
                create_archive(db, payload, user_id=1, scope_context={"data_scope": 4, "product_category_ids": None})
            except HTTPException as exc:
                assert exc.status_code == 422, code
            else:
                raise AssertionError(f"{code} 未通过统一枚举校验")
    finally:
        db.close()


def test_workflow_migration_cleans_unregistered_values_without_breaking_history():
    from app.core.database import SessionLocal
    from app.models.dict import SysDictItem
    from app.models.project import PmsProject
    from app.services.dict import get_dict_items
    from app.services.enum_registry import initialize_enum_definitions

    db = SessionLocal()
    try:
        definition = seed_enum(
            db,
            "project_status",
            [("1", "进行中", 1), ("legacy", "文本脏值", 1), ("9", "历史状态", 1)],
        )
        db.query(PmsProject).filter(PmsProject.project_code == "ENUM-LEGACY-STATUS").delete()
        db.add(PmsProject(
            project_code="ENUM-LEGACY-STATUS",
            project_name="历史状态项目",
            dept_id=1,
            pm_id=1,
            status=9,
        ))
        db.commit()

        initialize_enum_definitions(db)

        values = {
            item.item_value: item
            for item in db.query(SysDictItem).filter(SysDictItem.dict_id == definition.id).all()
        }
        assert "legacy" not in values
        assert values["9"].status == 0
        assert {"1", "2", "3"}.issubset(values)

        listed = {item["item_value"]: item for item in get_dict_items(db, definition.id)}
        assert listed["9"]["reference_count"] == 1
    finally:
        db.close()


def test_configurable_business_enum_allocates_immutable_non_reused_numbers():
    from fastapi import HTTPException

    from app.core.database import SessionLocal
    from app.models.dict import SysDictItem
    from app.schemas.dict import DictItemCreate, DictItemUpdate
    from app.services.dict import create_dict_item, get_dict_items, update_dict_item

    db = SessionLocal()
    try:
        definition = seed_enum(db, "product_category", [("1", "Bench", 1), ("2", "光伏", 1)])
        definition.next_value = 3
        db.commit()

        first_result = create_dict_item(
            db,
            definition.id,
            DictItemCreate(item_label="Single"),
        )
        first = db.query(SysDictItem).filter(SysDictItem.id == first_result["id"]).one()
        assert first.item_value == "3"

        from app.services.dict import delete_dict_item
        delete_dict_item(db, first.id)
        from app.services.enum_registry import initialize_enum_definitions
        initialize_enum_definitions(db)
        db.refresh(definition)
        assert definition.next_value == 4
        second_result = create_dict_item(
            db,
            definition.id,
            DictItemCreate(item_label="HOTSPM"),
        )
        second = db.query(SysDictItem).filter(SysDictItem.id == second_result["id"]).one()
        assert second.item_value == "4"
        listed = {item["id"]: item for item in get_dict_items(db, definition.id)}
        assert listed[second.id]["value_locked"] is True

        try:
            update_dict_item(db, second.id, DictItemUpdate(item_value="99"))
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "不可修改" in exc.detail
        else:
            raise AssertionError("自动生成的业务枚举存储值必须不可修改")
    finally:
        db.close()


def test_configurable_enum_sequence_uses_atomic_database_increment():
    from app.core.database import SessionLocal
    from app.services.dict import _allocate_next_enum_value

    db = SessionLocal()
    try:
        definition = seed_enum(db, "equipment_series", [("1", "链式", 1)])
        definition.next_value = 20
        db.commit()

        assert _allocate_next_enum_value(db, definition.id) == "20"
        db.commit()
        db.refresh(definition)
        assert definition.next_value == 21
    finally:
        db.close()


def test_enum_permissions_and_no_free_category_api():
    api = (ROOT / "app/api/dicts.py").read_text(encoding="utf-8")
    init_db = (ROOT / "app/models/init_db.py").read_text(encoding="utf-8")
    assert "system:enum:view" in api
    assert "system:enum:add" in api
    assert "system:enum:edit" in api
    assert "system:enum:delete" in api
    assert "def create_dict(" not in api
    assert 'menu_name="枚举管理"' in init_db
    assert 'path="/system/enum"' in init_db


if __name__ == "__main__":
    test_registry_separates_managed_system_and_legacy_definitions()
    test_enum_list_hides_unregistered_and_system_definitions()
    test_workflow_values_are_locked_but_labels_and_status_can_change()
    test_disabled_values_keep_history_labels_and_new_writes_are_validated()
    test_referenced_configurable_value_cannot_be_deleted()
    test_project_writes_reject_unknown_or_disabled_enum_values()
    test_workflow_migration_cleans_unregistered_values_without_breaking_history()
    test_configurable_business_enum_allocates_immutable_non_reused_numbers()
    test_configurable_enum_sequence_uses_atomic_database_increment()
    test_enum_permissions_and_no_free_category_api()
    print("enum management contract passed")
