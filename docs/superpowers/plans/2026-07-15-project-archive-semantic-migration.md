# Project Archive Semantic Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目档案、项目进度引用字段、角色产品范围和业务枚举统一迁移到“产品类别 / 设备系列”语义，并补齐客户、序列号及唯一性约束。

**Architecture:** 项目档案继续作为项目主数据唯一来源，项目进度仅保留用于查询的同步副本和只读投影。业务枚举使用分类内独立递增的稳定数字值，数据库兼容升级负责把旧字符串枚举和旧字段迁移到新整数列；字段目录、字段规则、权限上下文和前端均消费同一套新字段名。

**Tech Stack:** FastAPI、SQLAlchemy、SQLite/MSSQL 2017、Vue 3、TypeScript、Element Plus、AG Grid、Node/Python 契约测试。

## Global Constraints

- 项目尚未正式上线，测试数据允许一次性语义迁移；不建设旧 API 字段长期双写。
- ERP 继续只使用当前项目编号和项目名称，不保存或依赖金蝶内码。
- `erp_sync_status` 等系统协议值保持字符串，不参与业务枚举数字化。
- 引用自项目档案的字段在项目进度中只读，修改必须回到项目档案。
- 项目编号、项目名称、序列号写入前去除首尾空格；项目编号和序列号大小写不敏感唯一。
- 产品类别、设备系列分别从 `1` 自动递增，值不可修改且删除后不复用。
- 所有写操作继续接入统一操作日志，并更新 `change.md`。

---

### Task 1: Semantic Contract Tests

**Files:**
- Create: `backend/tests/project_archive_semantic_contract.py`
- Modify: `backend/tests/field_catalog_contract.py`
- Modify: `backend/tests/field_policy_contract.py`
- Modify: `frontend/tests/archive-edit-drawer-contract.test.mjs`

**Interfaces:**
- Consumes: 当前 SQLAlchemy 模型、Pydantic Schema、字段目录和前端页面源码。
- Produces: 新字段名、唯一约束、档案来源只读字段和 UI 文案的可执行契约。

- [ ] **Step 1: Write failing backend model/schema contracts**

```python
assert hasattr(PmsProjectArchive, "customer")
assert hasattr(PmsProjectArchive, "product_category")
assert hasattr(PmsProjectArchive, "equipment_series")
assert hasattr(PmsProjectArchive, "serial_no")
assert not hasattr(PmsProjectArchive, "product_line")
assert "product_category" in ProjectArchiveCreate.model_fields
```

- [ ] **Step 2: Write failing field source contracts**

```python
for key in ("customer", "product_category", "equipment_series", "serial_no"):
    field = PROJECT_SHEET_FIELD_MAP[key]
    assert field.source == "archive"
    assert field.editable is False
```

- [ ] **Step 3: Write failing frontend source contracts**

```javascript
assert.match(source, /产品类别/)
assert.match(source, /设备系列/)
assert.match(source, /序列号/)
assert.doesNotMatch(source, /product_line|product_type/)
```

- [ ] **Step 4: Run tests and confirm expected failures**

Run:

```bash
cd backend
python tests/project_archive_semantic_contract.py
python tests/field_catalog_contract.py
python tests/field_policy_contract.py
cd ../frontend
node tests/archive-edit-drawer-contract.test.mjs
```

Expected: FAIL on missing semantic fields and remaining legacy names.

### Task 2: Stable Numeric Enum Allocation

**Files:**
- Modify: `backend/app/models/dict.py`
- Modify: `backend/app/schemas/dict.py`
- Modify: `backend/app/services/enum_registry.py`
- Modify: `backend/app/services/dict.py`
- Modify: `backend/app/models/init_db.py`
- Modify: `backend/tests/enum_management_contract.py`
- Modify: `frontend/src/views/system/EnumList.vue`
- Modify: `frontend/tests/enum-management-contract.test.mjs`

**Interfaces:**
- Produces: `allocate_next_enum_value(db, dict_id) -> str`，为可配置业务枚举返回分类内稳定数字字符串。
- Produces: `product_category`、`equipment_series` 枚举定义。

- [ ] **Step 1: Add failing allocation and immutability tests**

```python
assert create_item(db, product_category_id, "新类别").item_value == "5"
assert update_item(db, item.id, {"item_value": "99"}).item_value == "5"
delete_item(db, item.id)
assert create_item(db, product_category_id, "下一类别").item_value == "6"
```

- [ ] **Step 2: Verify tests fail because values are still user supplied**

Run: `cd backend && python tests/enum_management_contract.py`

- [ ] **Step 3: Add per-category sequence state and allocation**

Add `next_value` to `SysDict`, initialize it from `MAX(CAST(item_value AS INTEGER)) + 1`, lock the dictionary row during allocation, ignore client storage values on create, and reject storage-value edits.

- [ ] **Step 4: Replace legacy enum definitions and frontend storage-value editor**

Register `product_category` and `equipment_series`; the dialog sends only label, sort and status and renders the generated number read-only after save.

- [ ] **Step 5: Run enum backend/frontend contracts**

Run:

```bash
cd backend && python tests/enum_management_contract.py
cd ../frontend && node tests/enum-management-contract.test.mjs
```

Expected: PASS.

### Task 3: Database Model And Compatibility Upgrade

**Files:**
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/rbac.py`
- Modify: `backend/app/models/init_db.py`
- Modify: `backend/tests/legacy_schema_upgrade_contract.py`
- Modify: `backend/tests/sqlite_init_contract.py`

**Interfaces:**
- Produces: `upgrade_project_archive_semantics(engine) -> None` called before ORM business queries during initialization.
- Produces: archive normalized key columns and database unique indexes.

- [ ] **Step 1: Add failing fresh-schema and legacy-upgrade tests**

Create a legacy SQLite schema with `product_line`, `product_type`, role `product_lines`, and string values; run initialization and assert deterministic numeric migration plus unique indexes.

- [ ] **Step 2: Verify legacy upgrade test fails**

Run: `cd backend && python tests/legacy_schema_upgrade_contract.py`

- [ ] **Step 3: Implement semantic model columns**

Use integer columns for `product_category`, `equipment_series`, and project `product_category`; add archive `customer`, `serial_no`, normalized unique keys; rename role storage to `product_category_ids`.

- [ ] **Step 4: Implement transactional SQLite/MSSQL-compatible upgrade**

Add missing columns, build old-value-to-number maps ordered by `sort_order,id`, scan duplicates before index creation, migrate archive/project/role values, and leave legacy physical columns unused.

- [ ] **Step 5: Verify fresh and upgraded schemas**

Run:

```bash
cd backend
python tests/legacy_schema_upgrade_contract.py
python tests/sqlite_init_contract.py
```

Expected: PASS.

### Task 4: Archive API, Uniqueness And Project Synchronization

**Files:**
- Modify: `backend/app/schemas/project.py`
- Modify: `backend/app/services/project.py`
- Modify: `backend/app/api/projects.py`
- Modify: `backend/tests/project_update_contract.py`
- Modify: `backend/tests/project_archive_semantic_contract.py`

**Interfaces:**
- Produces: `normalize_archive_identity(field_key, value) -> tuple[str | None, str | None]`.
- Produces: structured `409` detail `{ "field_key": str, "message": str }`.
- Consumes: numeric enum validation and normalized unique database columns.

- [ ] **Step 1: Add failing create/update uniqueness tests**

Cover trimmed values, case-insensitive project code/serial number, project-name conflict, empty serial number, and exclusion of the current record during update.

- [ ] **Step 2: Verify expected 409 behavior is absent**

Run: `cd backend && python tests/project_archive_semantic_contract.py`

- [ ] **Step 3: Implement schemas and archive normalization**

Replace legacy request/response fields with `customer`, `product_category: int | None`, `equipment_series: int | None`, and `serial_no`; normalize before validation and persistence.

- [ ] **Step 4: Synchronize linked progress projects in the same transaction**

On archive update, update linked project code, name and product category before commit; any conflict rolls back archive, linked projects and operation-log entry.

- [ ] **Step 5: Run archive and project update contracts**

Run:

```bash
cd backend
python tests/project_archive_semantic_contract.py
python tests/project_update_contract.py
```

Expected: PASS.

### Task 5: Field Governance, Authorization And Read-Only Projection

**Files:**
- Modify: `backend/app/services/project_sheet_fields.py`
- Modify: `backend/app/services/field_policy.py`
- Modify: `backend/app/services/field_catalog.py`
- Modify: `backend/app/services/authorization.py`
- Modify: `backend/app/services/rbac.py`
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/schemas/rbac.py`
- Modify: `backend/app/schemas/user.py`
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/services/operation_log.py`
- Modify: corresponding backend contract tests.

**Interfaces:**
- Produces: authorization context `product_category_ids: list[int] | None`.
- Produces: sheet field projection for six archive-sourced read-only fields.
- Consumes: archive semantic model and numeric enum registry.

- [ ] **Step 1: Add failing contracts for field policy, catalog, projection and RBAC**

Assert Chinese labels, enum codes, archive source, non-editability, numeric authorization responses, and removal of legacy API names.

- [ ] **Step 2: Verify failures**

Run the focused field catalog, field policy, sheet detail and RBAC tests.

- [ ] **Step 3: Implement shared semantic metadata**

Update field definitions and log labels once at the backend source; do not add duplicate frontend translation tables.

- [ ] **Step 4: Implement numeric product-category authorization**

Parse and return category IDs as integers; filter archive/project reads and writes using numeric IDs and keep `None` as unrestricted.

- [ ] **Step 5: Run focused governance and permission tests**

Run:

```bash
cd backend
python tests/field_catalog_contract.py
python tests/field_policy_contract.py
python tests/project_sheet_detail_contract.py
python tests/project_sheet_list_contract.py
python tests/rbac_permission_contract.py
```

Expected: PASS.

### Task 6: Frontend Semantic Migration

**Files:**
- Modify: `frontend/src/views/project/ProjectArchive.vue`
- Modify: `frontend/src/views/project/ProjectList.vue`
- Modify: `frontend/src/views/system/EnumList.vue`
- Modify: `frontend/src/views/system/RoleList.vue`
- Modify: `frontend/src/api/auth.ts`
- Modify: focused frontend contract tests.

**Interfaces:**
- Consumes: archive API semantic fields, numeric enum options, `product_category_ids` authorization response.
- Produces: archive create/edit/list/filter UI and progress read-only projection using only semantic names.

- [ ] **Step 1: Add failing frontend contracts**

Assert customer/serial fields, product-category/equipment-series labels, editable project code, numeric enum payloads, read-only progress fields, and storage key version bump.

- [ ] **Step 2: Verify tests fail on legacy code**

Run focused archive, progress, enum and RBAC Node tests.

- [ ] **Step 3: Update project archive**

Change TypeScript models, forms, filters, columns, drawer fields and API payloads; map structured `409.field_key` to the matching field error and preserve the drawer’s click-value-only edit behavior.

- [ ] **Step 4: Update progress, role and enum pages**

Replace legacy fields, treat archive projections as read-only, consume numeric category IDs, and remove editable enum storage-value controls.

- [ ] **Step 5: Run focused frontend contracts and type build**

Run:

```bash
cd frontend
node tests/archive-edit-drawer-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/project-progress-workbench-contract.test.mjs
node tests/project-sheet-detail-drawer-contract.test.mjs
node tests/enum-management-contract.test.mjs
node tests/rbac-permission-contract.test.mjs
npm run build
```

Expected: PASS.

### Task 7: Full Regression, Browser Verification And Traceability

**Files:**
- Modify: `change.md`

**Interfaces:**
- Consumes: completed backend and frontend semantic migration.
- Produces: verified feature branch ready for user review.

- [ ] **Step 1: Run all relevant backend contracts**

Run every test under `backend/tests/` as standalone scripts, stopping on the first failure.

- [ ] **Step 2: Run all frontend contracts and build**

Run every `frontend/tests/*.test.mjs` plus `npm run build`.

- [ ] **Step 3: Start PMS and verify in browser**

Check archive create/edit drawer, uniqueness errors, category/series filters, column settings, progress read-only values, role category scope and enum automatic numbering at 1366x768 and 1600x900.

- [ ] **Step 4: Record implementation in change log**

Document schema/API/UI changes, migration behavior, tests, browser verification and known non-goals in `change.md`.

- [ ] **Step 5: Review diff and commit intentionally**

Run `git diff --check`, inspect `git status` and `git diff --stat`, then commit only this feature’s files. Do not push or merge until the user explicitly requests it.
