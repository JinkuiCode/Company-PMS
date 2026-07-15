"""项目档案语义化字段的一次性数据库兼容升级。"""
from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Engine, inspect, text


PRODUCT_CATEGORY_DEFAULTS = ["Bench", "光伏", "Single", "HOTSPM"]
EQUIPMENT_SERIES_DEFAULTS = ["链式", "槽式"]


def _column_names(connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def _add_column(connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name in _column_names(connection, table_name):
        return
    connection.execute(text(f"ALTER TABLE {table_name} ADD {column_name} {ddl}"))


def _legacy_enum_rows(connection, code: str) -> list[dict[str, Any]]:
    if not inspect(connection).has_table("sys_dict") or not inspect(connection).has_table("sys_dict_item"):
        return []
    return list(connection.execute(text("""
        SELECT i.item_value, i.item_label
        FROM sys_dict_item i
        JOIN sys_dict d ON d.id = i.dict_id
        WHERE d.dict_code = :code
        ORDER BY i.sort, i.id
    """), {"code": code}).mappings())


def _distinct_legacy_values(connection, sources: Iterable[tuple[str, str]]) -> list[str]:
    values: list[str] = []
    for table_name, column_name in sources:
        inspector = inspect(connection)
        if not inspector.has_table(table_name) or column_name not in _column_names(connection, table_name):
            continue
        rows = connection.execute(text(
            f"SELECT DISTINCT {column_name} AS value FROM {table_name} "
            f"WHERE {column_name} IS NOT NULL AND {column_name} <> ''"
        )).mappings()
        for row in rows:
            raw = str(row["value"]).strip()
            if raw and raw not in values:
                values.append(raw)
    return values


def _enum_mapping(
    connection,
    legacy_code: str,
    defaults: list[str],
    sources: Iterable[tuple[str, str]],
) -> tuple[dict[str, int], list[tuple[int, str]]]:
    rows = _legacy_enum_rows(connection, legacy_code)
    ordered: list[tuple[str, str]] = []
    for row in rows:
        value = str(row["item_value"]).strip()
        label = str(row["item_label"] or value).strip()
        if value and value not in {item[0] for item in ordered}:
            ordered.append((value, label))
    if not ordered:
        ordered.extend((value, value) for value in defaults)
    for value in _distinct_legacy_values(connection, sources):
        if value not in {item[0] for item in ordered}:
            ordered.append((value, value))
    mapping = {value: index for index, (value, _label) in enumerate(ordered, 1)}
    labels = [(index, label) for index, (_value, label) in enumerate(ordered, 1)]
    return mapping, labels


def _upsert_numeric_enum(
    connection,
    *,
    code: str,
    name: str,
    field_name: str,
    sort_order: int,
    labels: list[tuple[int, str]],
) -> None:
    row = connection.execute(
        text("SELECT id, next_value FROM sys_dict WHERE dict_code = :code"),
        {"code": code},
    ).first()
    created = row is None
    if row:
        dict_id = int(row[0])
        existing_next_value = int(row[1] or 1)
        connection.execute(text("""
            UPDATE sys_dict
            SET dict_name = :name, table_name = 'pms_project_archive', field_name = :field_name,
                page_name = '枚举管理', sort = :sort_order, status = 1
            WHERE id = :dict_id
        """), {
            "name": name,
            "field_name": field_name,
            "sort_order": sort_order,
            "dict_id": dict_id,
        })
    else:
        existing_next_value = 1
        connection.execute(text("""
            INSERT INTO sys_dict (dict_code, dict_name, table_name, field_name, page_name, sort, status, next_value)
            VALUES (:code, :name, 'pms_project_archive', :field_name, '枚举管理', :sort_order, 1, :next_value)
        """), {
            "code": code,
            "name": name,
            "field_name": field_name,
            "sort_order": sort_order,
            "next_value": len(labels) + 1,
        })
        dict_id = int(connection.execute(
            text("SELECT id FROM sys_dict WHERE dict_code = :code"),
            {"code": code},
        ).scalar_one())

    if created:
        for value, label in labels:
            connection.execute(text("""
                INSERT INTO sys_dict_item (dict_id, item_value, item_label, sort, status)
                VALUES (:dict_id, :item_value, :item_label, :sort_order, 1)
            """), {
                "dict_id": dict_id,
                "item_value": str(value),
                "item_label": label,
                "sort_order": value,
            })
    existing_numeric_values = [
        int(value)
        for value in connection.execute(
            text("SELECT item_value FROM sys_dict_item WHERE dict_id = :dict_id"),
            {"dict_id": dict_id},
        ).scalars()
        if str(value).isdigit()
    ]
    connection.execute(
        text("UPDATE sys_dict SET next_value = :next_value WHERE id = :dict_id"),
        {
            "next_value": max(
                existing_next_value,
                max(existing_numeric_values, default=0) + 1,
                len(labels) + 1,
            ),
            "dict_id": dict_id,
        },
    )


def _delete_legacy_enum(connection, code: str) -> None:
    row = connection.execute(
        text("SELECT id FROM sys_dict WHERE dict_code = :code"), {"code": code}
    ).first()
    if not row:
        return
    connection.execute(text("DELETE FROM sys_dict_item WHERE dict_id = :dict_id"), {"dict_id": row[0]})
    connection.execute(text("DELETE FROM sys_dict WHERE id = :dict_id"), {"dict_id": row[0]})


def _migrate_legacy_value_column(
    connection,
    *,
    table_name: str,
    old_column: str,
    new_column: str,
    mapping: dict[str, int],
) -> None:
    if old_column not in _column_names(connection, table_name):
        return
    for old_value, new_value in mapping.items():
        connection.execute(text(
            f"UPDATE {table_name} SET {new_column} = :new_value "
            f"WHERE {new_column} IS NULL AND {old_column} = :old_value"
        ), {"new_value": new_value, "old_value": old_value})
    unmapped = connection.execute(text(
        f"SELECT DISTINCT {old_column} FROM {table_name} "
        f"WHERE {new_column} IS NULL AND {old_column} IS NOT NULL AND {old_column} <> ''"
    )).scalars().all()
    if unmapped:
        raise RuntimeError(f"{table_name}.{old_column} 存在无法迁移的枚举值：{', '.join(map(str, unmapped))}")


def _migrate_role_categories(connection, mapping: dict[str, int]) -> None:
    columns = _column_names(connection, "sys_role")
    if "product_lines" not in columns:
        return
    rows = connection.execute(text(
        "SELECT id, product_lines, product_category_ids FROM sys_role WHERE product_lines IS NOT NULL"
    )).mappings()
    for row in rows:
        if row["product_category_ids"]:
            continue
        values = [value.strip() for value in str(row["product_lines"]).split(",") if value.strip()]
        unknown = [value for value in values if value not in mapping]
        if unknown:
            raise RuntimeError(f"sys_role.product_lines 存在无法迁移的值：{', '.join(unknown)}")
        migrated = ",".join(str(mapping[value]) for value in values)
        connection.execute(
            text("UPDATE sys_role SET product_category_ids = :value WHERE id = :role_id"),
            {"value": migrated or None, "role_id": row["id"]},
        )


def _coerce_legacy_enum_value(value: Any, mapping: dict[str, int], field_label: str) -> int | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    if normalized in mapping:
        return mapping[normalized]
    if normalized.isdigit():
        return int(normalized)
    raise RuntimeError(f"项目总表字段 {field_label} 存在无法迁移的值：{normalized}")


def _migrate_detail_archive_fields(
    connection,
    category_mapping: dict[str, int],
    series_mapping: dict[str, int],
) -> None:
    inspector = inspect(connection)
    if not inspector.has_table("pms_project_sheet_detail"):
        return
    rows = list(connection.execute(text("""
        SELECT d.id AS detail_id, d.detail_data, p.archive_id,
               a.customer, a.product_category, a.equipment_series, a.serial_no
        FROM pms_project_sheet_detail d
        JOIN pms_project p ON p.id = d.project_id
        JOIN pms_project_archive a ON a.id = p.archive_id
        WHERE p.archive_id IS NOT NULL
        ORDER BY d.id
    """)).mappings())
    merged: dict[int, dict[str, Any]] = {}
    cleaned_details: list[tuple[int, str]] = []
    reference_keys = {
        "project_code",
        "project_name",
        "customer",
        "product_category",
        "product_line",
        "equipment_series",
        "serial_no",
    }
    for row in rows:
        try:
            detail = json.loads(row["detail_data"] or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"项目总表明细 {row['detail_id']} 不是有效 JSON") from exc
        if not isinstance(detail, dict):
            raise RuntimeError(f"项目总表明细 {row['detail_id']} 必须是 JSON 对象")
        archive_id = int(row["archive_id"])
        target = merged.setdefault(archive_id, {
            "customer": str(row["customer"] or "").strip() or None,
            "product_category": row["product_category"],
            "equipment_series": row["equipment_series"],
            "serial_no": str(row["serial_no"] or "").strip() or None,
        })
        candidates = {
            "customer": str(detail.get("customer") or "").strip() or None,
            "product_category": _coerce_legacy_enum_value(
                detail.get("product_category", detail.get("product_line")),
                category_mapping,
                "产品类别",
            ),
            "equipment_series": _coerce_legacy_enum_value(
                detail.get("equipment_series"),
                series_mapping,
                "设备系列",
            ),
            "serial_no": str(detail.get("serial_no") or "").strip() or None,
        }
        for field_key, candidate in candidates.items():
            if candidate in (None, ""):
                continue
            existing = target.get(field_key)
            if existing not in (None, "") and existing != candidate:
                raise RuntimeError(
                    f"档案 {archive_id} 的 {field_key} 在项目总表明细中存在冲突：{existing} / {candidate}"
                )
            target[field_key] = candidate
        for key in reference_keys:
            detail.pop(key, None)
        cleaned_details.append((int(row["detail_id"]), json.dumps(detail, ensure_ascii=False)))

    for archive_id, values in merged.items():
        connection.execute(text("""
            UPDATE pms_project_archive
            SET customer = :customer, product_category = :product_category,
                equipment_series = :equipment_series, serial_no = :serial_no
            WHERE id = :archive_id
        """), {**values, "archive_id": archive_id})
    for detail_id, detail_data in cleaned_details:
        connection.execute(
            text("UPDATE pms_project_sheet_detail SET detail_data = :detail_data WHERE id = :detail_id"),
            {"detail_data": detail_data, "detail_id": detail_id},
        )


def _normalize_archive_identity_rows(connection) -> None:
    rows = list(connection.execute(text("""
        SELECT id, project_code, project_name, serial_no
        FROM pms_project_archive
        ORDER BY id
    """)).mappings())
    seen: dict[str, dict[str, int]] = {
        "project_code": {},
        "project_name": {},
        "serial_no": {},
    }
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        project_code = str(row["project_code"] or "").strip()
        project_name = str(row["project_name"] or "").strip()
        serial_no = str(row["serial_no"] or "").strip() or None
        if not project_code or not project_name:
            raise RuntimeError(f"档案 {row['id']} 的项目编号或项目名称为空，无法迁移")
        keys = {
            "project_code": project_code.casefold(),
            "project_name": project_name,
            "serial_no": serial_no.casefold() if serial_no else None,
        }
        for field_key, key in keys.items():
            if key is None:
                continue
            if key in seen[field_key]:
                raise RuntimeError(
                    f"档案字段 {field_key} 存在重复：ID {seen[field_key][key]} 与 {row['id']}"
                )
            seen[field_key][key] = int(row["id"])
        normalized_rows.append({
            "id": row["id"],
            "project_code": project_code,
            "project_name": project_name,
            "serial_no": serial_no,
            "project_code_key": keys["project_code"],
            "project_name_key": keys["project_name"],
            "serial_no_key": keys["serial_no"],
        })
    for row in normalized_rows:
        connection.execute(text("""
            UPDATE pms_project_archive
            SET project_code = :project_code, project_name = :project_name, serial_no = :serial_no,
                project_code_key = :project_code_key, project_name_key = :project_name_key,
                serial_no_key = :serial_no_key
            WHERE id = :id
        """), row)


def _sync_linked_projects_from_archives(connection) -> None:
    inspector = inspect(connection)
    if not inspector.has_table("pms_project") or not inspector.has_table("pms_project_archive"):
        return
    rows = connection.execute(text("""
        SELECT p.id AS project_id, a.project_code, a.project_name, a.product_category
        FROM pms_project p
        JOIN pms_project_archive a ON a.id = p.archive_id
        WHERE p.archive_id IS NOT NULL
        ORDER BY p.id
    """)).mappings()
    for row in rows:
        connection.execute(text("""
            UPDATE pms_project
            SET project_code = :project_code, project_name = :project_name,
                product_category = :product_category
            WHERE id = :project_id
        """), row)


def _ensure_unique_indexes(connection) -> None:
    existing = {item["name"] for item in inspect(connection).get_indexes("pms_project_archive")}
    statements = {
        "ux_pms_project_archive_project_code_key": (
            "CREATE UNIQUE INDEX ux_pms_project_archive_project_code_key "
            "ON pms_project_archive (project_code_key)"
        ),
        "ux_pms_project_archive_project_name_key": (
            "CREATE UNIQUE INDEX ux_pms_project_archive_project_name_key "
            "ON pms_project_archive (project_name_key)"
        ),
        "ux_pms_project_archive_serial_no_key": (
            "CREATE UNIQUE INDEX ux_pms_project_archive_serial_no_key "
            "ON pms_project_archive (serial_no_key) WHERE serial_no_key IS NOT NULL"
        ),
    }
    for name, statement in statements.items():
        if name not in existing:
            connection.execute(text(statement))


def upgrade_project_archive_semantics(engine: Engine) -> None:
    """在任何新模型 ORM 查询前完成旧结构升级；整个过程使用单事务。"""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if inspector.has_table("sys_dict"):
            _add_column(connection, "sys_dict", "next_value", "INT NOT NULL DEFAULT 1")
        if inspector.has_table("sys_role"):
            _add_column(connection, "sys_role", "product_category_ids", "NVARCHAR(256) NULL")
        if inspector.has_table("pms_project_archive"):
            for column_name, ddl in (
                ("project_code_key", "NVARCHAR(32) NULL"),
                ("project_name_key", "NVARCHAR(128) NULL"),
                ("customer", "NVARCHAR(128) NULL"),
                ("product_category", "INT NULL"),
                ("equipment_series", "INT NULL"),
                ("serial_no", "NVARCHAR(64) NULL"),
                ("serial_no_key", "NVARCHAR(64) NULL"),
            ):
                _add_column(connection, "pms_project_archive", column_name, ddl)
        if inspector.has_table("pms_project"):
            _add_column(connection, "pms_project", "product_category", "INT NULL")

        if not (
            inspector.has_table("sys_dict")
            and inspector.has_table("sys_dict_item")
            and inspector.has_table("pms_project_archive")
        ):
            return

        category_mapping, category_labels = _enum_mapping(
            connection,
            "product_line",
            PRODUCT_CATEGORY_DEFAULTS,
            (
                ("pms_project_archive", "product_line"),
                ("pms_project", "product_line"),
            ),
        )
        series_mapping, series_labels = _enum_mapping(
            connection,
            "product_type",
            EQUIPMENT_SERIES_DEFAULTS,
            (("pms_project_archive", "product_type"),),
        )
        _upsert_numeric_enum(
            connection,
            code="product_category",
            name="产品类别",
            field_name="product_category",
            sort_order=12,
            labels=category_labels,
        )
        _upsert_numeric_enum(
            connection,
            code="equipment_series",
            name="设备系列",
            field_name="equipment_series",
            sort_order=13,
            labels=series_labels,
        )
        _migrate_legacy_value_column(
            connection,
            table_name="pms_project_archive",
            old_column="product_line",
            new_column="product_category",
            mapping=category_mapping,
        )
        _migrate_legacy_value_column(
            connection,
            table_name="pms_project_archive",
            old_column="product_type",
            new_column="equipment_series",
            mapping=series_mapping,
        )
        if inspector.has_table("pms_project"):
            _migrate_legacy_value_column(
                connection,
                table_name="pms_project",
                old_column="product_line",
                new_column="product_category",
                mapping=category_mapping,
            )
        if inspector.has_table("sys_role"):
            _migrate_role_categories(connection, category_mapping)
        _migrate_detail_archive_fields(connection, category_mapping, series_mapping)
        _normalize_archive_identity_rows(connection)
        _sync_linked_projects_from_archives(connection)
        _ensure_unique_indexes(connection)
        _delete_legacy_enum(connection, "product_line")
        _delete_legacy_enum(connection, "product_type")
