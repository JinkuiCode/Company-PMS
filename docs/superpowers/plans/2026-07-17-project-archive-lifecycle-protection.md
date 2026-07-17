# Project Archive Lifecycle Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让项目档案只有在从未被业务引用且从未成功同步外部系统时才能物理删除，并提供独立的启用/禁用状态、权限、审计和前端交互。

**Architecture:** 在 `PmsProjectArchive` 增加 `is_enabled`，由新的 `project_archive_lifecycle.py` 统一计算引用阻止项、执行启停及校验可写状态。项目、ERP 和删除接口只消费该服务，前端使用列表投影的 `can_delete/delete_blockers` 改善交互，但所有写操作仍由后端实时复核。

**Tech Stack:** FastAPI、SQLAlchemy、SQLite/MSSQL 2017、Vue 3、TypeScript、Element Plus、AG Grid、Node 契约测试。

## Global Constraints

- `status` 数据库列和历史值保留，但从业务页面、字段规则和枚举管理隐藏。
- `is_enabled=1` 为启用，`is_enabled=0` 为禁用；现有档案迁移为启用。
- 禁用档案只读、不可同步、不可被新业务引用，重新启用后才能修改。
- 成功同步历史永久阻止物理删除；仅失败同步历史不阻止。
- 删除与启停分别使用 `project:archive:delete` 和 `project:archive:toggle`。
- 批量删除必须全有或全无，禁止逐条部分提交。
- 所有写路径继续执行实时 RBAC、数据范围和产品类别范围校验。
- 引用、启停、删除和失败原因均使用中文结构化结果并接入统一操作日志。
- SQLite 与 MSSQL 2017 必须使用相同业务语义。

---

## File Map

- Create `backend/app/services/project_archive_lifecycle.py`: 删除阻止项、列表批量投影、禁用写保护和启停服务。
- Create `backend/app/services/project_archive_lifecycle_migration.py`: `is_enabled` 字段及索引的幂等数据库升级。
- Create `backend/tests/project_archive_lifecycle_contract.py`: 后端运行时与结构契约。
- Create `frontend/tests/archive-lifecycle-contract.test.mjs`: 前端筛选、状态、动作和只读抽屉契约。
- Modify `backend/app/models/project.py`: 增加 `is_enabled` 模型字段与索引。
- Modify `backend/app/models/init_db.py`: 调用迁移、创建启停权限并执行一次性模板授权。
- Modify `backend/app/services/project.py`: 列表投影、options 过滤、创建项目保护、更新/删除/批量删除接入生命周期服务。
- Modify `backend/app/services/kingdee.py`: 同步前执行启用状态校验。
- Modify `backend/app/services/role_templates.py`: 业务管理员模板增加启停权限。
- Modify `backend/app/services/enum_registry.py`: 隐藏 `archive_status` 枚举管理入口。
- Modify `backend/app/services/field_policy.py`: 从项目档案字段规则中移除旧 `status`。
- Modify `backend/app/services/field_catalog.py`: 为旧状态增加保留说明，并将 `is_enabled` 标记为系统控制。
- Modify `backend/app/schemas/project.py`: 调整档案请求与响应、启停请求、删除阻止项和批量删除结构。
- Modify `backend/app/api/projects.py`: 增加筛选、启停和批量删除接口。
- Modify `frontend/src/views/project/ProjectArchive.vue`: 状态筛选、列表标签、启停、删除原因、批量操作和禁用抽屉只读。
- Modify `AGENTS.md`: 新模块引用档案时必须注册删除保护检查器。
- Modify `change.md`: 记录实际实现和验证结果。

---

### Task 1: Lifecycle Model, Migration, and Contracts

**Files:**
- Create: `backend/tests/project_archive_lifecycle_contract.py`
- Create: `backend/app/services/project_archive_lifecycle_migration.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/init_db.py`

**Interfaces:**
- Produces: `PmsProjectArchive.is_enabled: int`
- Produces: `upgrade_project_archive_lifecycle(engine: Engine) -> None`

- [ ] **Step 1: Write the failing model and migration contract**

Create a test database, assert `is_enabled` exists with default `1`, and run the migration twice:

```python
def test_archive_enabled_model_and_idempotent_upgrade():
    from sqlalchemy import create_engine, inspect, text
    from app.core.database import Base
    from app.models.project import PmsProjectArchive
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
            "(project_code, project_code_key, project_name, project_name_key) "
            "VALUES ('LC-001', 'lc-001', '生命周期测试', '生命周期测试')"
        ))
        assert connection.execute(text(
            "SELECT is_enabled FROM pms_project_archive WHERE project_code='LC-001'"
        )).scalar_one() == 1
```

- [ ] **Step 2: Run the contract and verify RED**

Run: `cd backend && python tests/project_archive_lifecycle_contract.py`

Expected: FAIL because `is_enabled` and `project_archive_lifecycle_migration` do not exist.

- [ ] **Step 3: Add the model field and idempotent migration**

Add to `PmsProjectArchive`:

```python
is_enabled: Mapped[int] = mapped_column(
    Integer,
    nullable=False,
    default=1,
    server_default=text("1"),
    comment="启用状态: 1启用 0禁用",
)
```

Add an index named `idx_project_archive_enabled`, then implement:

```python
def upgrade_project_archive_lifecycle(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("pms_project_archive"):
        return
    columns = {item["name"] for item in inspector.get_columns("pms_project_archive")}
    with engine.begin() as connection:
        if "is_enabled" not in columns:
            connection.execute(text(
                "ALTER TABLE pms_project_archive "
                "ADD is_enabled INT NOT NULL DEFAULT 1"
            ))
        indexes = {item["name"] for item in inspect(connection).get_indexes("pms_project_archive")}
        if "idx_project_archive_enabled" not in indexes:
            connection.execute(text(
                "CREATE INDEX idx_project_archive_enabled "
                "ON pms_project_archive (is_enabled)"
            ))
```

Call it from `init_db()` immediately after semantic migration.

- [ ] **Step 4: Run model and legacy initialization contracts**

Run:

```bash
cd backend
python tests/project_archive_lifecycle_contract.py
python tests/sqlite_init_contract.py
python tests/legacy_schema_upgrade_contract.py
```

Expected: all scripts print their `passed` message and exit `0`.

- [ ] **Step 5: Commit the migration unit**

```bash
git add backend/app/models/project.py backend/app/models/init_db.py backend/app/services/project_archive_lifecycle_migration.py backend/tests/project_archive_lifecycle_contract.py
git commit -m "Add project archive enabled lifecycle state"
```

---

### Task 2: Central Deletion Guard and Write Protection

**Files:**
- Modify: `backend/tests/project_archive_lifecycle_contract.py`
- Create: `backend/app/services/project_archive_lifecycle.py`
- Modify: `backend/app/schemas/project.py`

**Interfaces:**
- Produces: `ArchiveDeleteBlocker(type: str, source: str, label: str, count: int)`
- Produces: `get_archive_delete_guard(db: Session, archive_id: int) -> dict[str, Any]`
- Produces: `get_archive_delete_guards(db: Session, archive_ids: list[int]) -> dict[int, dict[str, Any]]`
- Produces: `ensure_archive_enabled(archive: PmsProjectArchive, action_label: str) -> None`
- Produces: `set_archive_enabled(db: Session, archive: PmsProjectArchive, enabled: bool, operator_id: int | None, request: Request | None) -> dict`

- [ ] **Step 1: Add failing guard tests**

Cover no blockers, project references, failed-only sync, historical success, pending sync, disabled writes and idempotent enable/disable:

```python
guard = get_archive_delete_guard(db, archive.id)
assert guard == {"can_delete": True, "blockers": []}

db.add(PmsProject(archive_id=archive.id, project_code="LC-001", project_name="引用项目", dept_id=dept.id, pm_id=user.id, status=1))
db.commit()
guard = get_archive_delete_guard(db, archive.id)
assert guard["can_delete"] is False
assert guard["blockers"][0]["source"] == "project_progress"

db.add(ErpSyncLog(source_id=other.id, action="sync", status="failed"))
db.commit()
assert get_archive_delete_guard(db, other.id)["can_delete"] is True
db.add(ErpSyncLog(source_id=other.id, action="sync", status="success"))
db.commit()
assert get_archive_delete_guard(db, other.id)["can_delete"] is False
```

Assert disabled writes raise:

```python
try:
    ensure_archive_enabled(disabled_archive, "编辑")
except HTTPException as exc:
    assert exc.status_code == 409
    assert exc.detail["code"] == "ARCHIVE_DISABLED"
else:
    raise AssertionError("禁用档案必须拒绝编辑")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && python tests/project_archive_lifecycle_contract.py`

Expected: FAIL because lifecycle service symbols are missing.

- [ ] **Step 3: Implement blocker collection without N+1 queries**

Use grouped queries for project references and successful ERP logs. Return dicts in this exact shape:

```python
{
    archive_id: {
        "can_delete": len(blockers) == 0,
        "blockers": blockers,
    }
}
```

The single guard delegates to the batch guard. A pending sync blocker uses `type="operation_pending"`; a successful ERP blocker uses `type="external_sync"`; a project blocker uses `type="business_reference"`.

- [ ] **Step 4: Implement enabled checks and idempotent toggle**

`ensure_archive_enabled` returns for enabled archives and otherwise raises:

```python
HTTPException(status_code=409, detail={
    "code": "ARCHIVE_DISABLED",
    "message": f"项目档案已禁用，无法{action_label}，请先重新启用",
})
```

`set_archive_enabled` receives an archive that the caller has already loaded through `ensure_archive_access`. This keeps the lifecycle service independent from `project.py` and prevents a circular import. It rejects disabling while pending, updates `is_enabled`, writes one operation log with action `enable` or `disable`, and commits only when the value changes.

- [ ] **Step 5: Run the lifecycle contract**

Run: `cd backend && python tests/project_archive_lifecycle_contract.py`

Expected: PASS for all guard and toggle cases.

- [ ] **Step 6: Commit the lifecycle service**

```bash
git add backend/app/services/project_archive_lifecycle.py backend/app/schemas/project.py backend/tests/project_archive_lifecycle_contract.py
git commit -m "Add project archive deletion guards"
```

---

### Task 3: Project, Delete, Batch, and ERP Enforcement

**Files:**
- Modify: `backend/tests/project_archive_lifecycle_contract.py`
- Modify: `backend/app/services/project.py`
- Modify: `backend/app/services/kingdee.py`
- Modify: `backend/app/api/projects.py`
- Modify: `backend/app/schemas/project.py`

**Interfaces:**
- Consumes: `get_archive_delete_guard`, `get_archive_delete_guards`, `ensure_archive_enabled`, `set_archive_enabled`
- Produces: `DELETE /api/projects/archives/{archive_id}` structured `409`
- Produces: `POST /api/projects/archives/batch-delete`
- Produces: `PUT /api/projects/archives/{archive_id}/enabled`
- Produces: `PUT /api/projects/archives/batch-enabled`
- Produces: `change_archive_enabled(db, archive_id, enabled, operator_id, request, scope_context) -> dict`

- [ ] **Step 1: Add failing behavior tests**

Assert:

```python
option_ids = {item.id for item in get_archive_options(db)}
assert enabled_archive.id in option_ids
assert disabled_archive.id not in option_ids

try:
    delete_archive(db, referenced.id, operator_id=user.id)
except HTTPException as exc:
    assert exc.status_code == 409
    assert exc.detail["code"] == "ARCHIVE_DELETE_BLOCKED"
    assert exc.detail["suggested_action"] == "disable"
else:
    raise AssertionError("被引用档案不能删除")
```

Add one test where a two-item batch contains one protected archive and assert both records remain. Add one batch-disable test containing a pending-sync archive and assert no selected archive changes state. Add direct `create_project`, `update_archive` and ERP service calls against disabled archives and assert `ARCHIVE_DISABLED`.

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && python tests/project_archive_lifecycle_contract.py`

Expected: FAIL because write paths do not call lifecycle guards.

- [ ] **Step 3: Enforce active archive usage**

- `get_archive_options` filters `PmsProjectArchive.is_enabled == 1`.
- `get_archive_list` accepts `enabled: bool | None`, applies the filter when non-null, then calls `get_archive_delete_guards` once for the current page.
- `ArchiveResponse` adds `is_enabled`, `can_delete` and `delete_blockers`; service guard key `blockers` is mapped to response key `delete_blockers`.
- `create_project` calls `ensure_archive_enabled(archive, "建立项目进度")` after access validation.
- `update_archive` calls `ensure_archive_enabled(archive, "编辑")` before validating updates.
- `sync_project_archive_to_erp` calls `ensure_archive_enabled(archive, "同步 ERP")` before setting pending.
- Batch ERP sync reports disabled rows as failures without calling Kingdee.

- [ ] **Step 4: Replace delete behavior and add atomic batch delete**

Single delete rechecks the guard and raises:

```python
raise HTTPException(status_code=409, detail={
    "code": "ARCHIVE_DELETE_BLOCKED",
    "message": format_archive_delete_blockers(guard["blockers"]),
    "blockers": guard["blockers"],
    "suggested_action": "disable",
})
```

Before raising a blocked single-delete error, write one failed operation log with `commit=True`, including the blockers. Batch delete first loads all in-scope rows, computes all guards, and raises one structured `409` before any `db.delete`; the blocked batch writes one failed batch log. If all are deletable, delete all and write one log per archive before one commit.

- [ ] **Step 5: Add routes in safe order**

Register static routes before `/{project_id}` routes. Extend `/archives/list` with `enabled: bool | None = Query(True)` and pass it to the service:

```python
@router.post("/archives/batch-delete", summary="批量删除项目档案")
def batch_delete_archives(...): ...

@router.put("/archives/{archive_id}/enabled", summary="启用或禁用项目档案")
def set_archive_enabled_route(...): ...

@router.put("/archives/batch-enabled", summary="批量启用或禁用项目档案")
def batch_set_archives_enabled(...): ...
```

Use `project:archive:delete` for batch delete and `project:archive:toggle` for enable/disable.

- [ ] **Step 6: Run backend behavior regressions**

Run:

```bash
cd backend
python tests/project_archive_lifecycle_contract.py
python tests/project_archive_semantic_contract.py
python tests/project_update_contract.py
python tests/rbac_permission_contract.py
python tests/operation_log_contract.py
```

Expected: all scripts pass.

- [ ] **Step 7: Commit write-path protection**

```bash
git add backend/app/api/projects.py backend/app/schemas/project.py backend/app/services/project.py backend/app/services/kingdee.py backend/tests/project_archive_lifecycle_contract.py
git commit -m "Protect project archive lifecycle operations"
```

---

### Task 4: RBAC, Hidden Legacy Status, and Field Catalog

**Files:**
- Modify: `backend/tests/project_archive_lifecycle_contract.py`
- Modify: `backend/app/models/init_db.py`
- Modify: `backend/app/services/role_templates.py`
- Modify: `backend/app/services/enum_registry.py`
- Modify: `backend/app/services/field_policy.py`
- Modify: `backend/app/services/field_catalog.py`
- Modify: `backend/app/schemas/project.py`

**Interfaces:**
- Produces: `project:archive:toggle`
- Produces: hidden `archive_status` management definition
- Produces: system-controlled field catalog entry for `is_enabled`

- [ ] **Step 1: Add failing metadata and permission assertions**

```python
assert ROLE_TEMPLATES["business_admin"]["permissions"] >= {"project:archive:toggle"}
assert "project:archive:toggle" not in ROLE_TEMPLATES["operator"]["permissions"]
assert ENUM_REGISTRY["archive_status"]["visible"] is False
assert "status" not in ArchiveCreate.model_fields
assert "status" not in ArchiveUpdate.model_fields
assert "status" not in {
    item["key"] for item in get_business_field_registry(MODULE_PROJECT_ARCHIVE)
}
catalog = {(item["module"], item["field_code"]): item for item in build_field_catalog()}
assert "保留字段" in catalog[("project_archive", "status")]["description"]
assert catalog[("project_archive", "is_enabled")]["source_type"] == "system"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && python tests/project_archive_lifecycle_contract.py`

Expected: FAIL on permission and metadata assertions.

- [ ] **Step 3: Add the permission node and one-time grant**

Add button menu ID `226`, parent `22`, name “启用/禁用”, permission `project:archive:toggle`, sort `6`. Track newly created ID in a dedicated set and grant it once to `admin` and `business_admin`, using the same non-replenishing pattern as field-policy permissions.

- [ ] **Step 4: Hide the undefined legacy status**

- Set `ENUM_REGISTRY["archive_status"]["visible"] = False` and description to “项目档案保留状态，暂未启用”.
- Remove the `status` entry from `ARCHIVE_FIELDS`.
- Remove `status` from `ArchiveCreate` and `ArchiveUpdate`; the model default preserves existing storage compatibility.
- Keep the model column and enum values so historical data remains readable.
- Add a focused field-catalog metadata override so `status` is documented as reserved and `is_enabled` as system-controlled.

- [ ] **Step 5: Run metadata and initialization regressions**

Run:

```bash
cd backend
python tests/project_archive_lifecycle_contract.py
python tests/field_catalog_contract.py
python tests/field_policy_contract.py
python tests/enum_management_contract.py
python tests/rbac_permission_contract.py
python tests/sqlite_init_contract.py
```

Expected: all scripts pass and a restart does not restore a revoked toggle permission.

- [ ] **Step 6: Commit RBAC and metadata changes**

```bash
git add backend/app/models/init_db.py backend/app/schemas/project.py backend/app/services/role_templates.py backend/app/services/enum_registry.py backend/app/services/field_policy.py backend/app/services/field_catalog.py backend/tests/project_archive_lifecycle_contract.py
git commit -m "Add archive toggle permission and hide legacy status"
```

---

### Task 5: Project Archive List and Read-Only Drawer UI

**Files:**
- Create: `frontend/tests/archive-lifecycle-contract.test.mjs`
- Modify: `frontend/src/views/project/ProjectArchive.vue`

**Interfaces:**
- Consumes: `is_enabled`, `can_delete`, `delete_blockers`
- Consumes: `PUT /projects/archives/{id}/enabled`
- Consumes: `PUT /projects/archives/batch-enabled`
- Consumes: `POST /projects/archives/batch-delete`

- [ ] **Step 1: Write the failing frontend contract**

Assert the Vue source contains the new default filter, toggle permission, read-only drawer and batch endpoint while excluding legacy archive status:

```javascript
assert.match(archive, /enabled:\s*true/)
assert.match(archive, /project:archive:toggle/)
assert.match(archive, /\/projects\/archives\/\$\{[^}]+\}\/enabled/)
assert.match(archive, /\/projects\/archives\/batch-enabled/)
assert.match(archive, /\/projects\/archives\/batch-delete/)
assert.match(archive, /archiveDrawerReadOnly/)
assert.match(archive, /delete_blockers/)
assert.doesNotMatch(archive, /dictOptions\.archive_status|field\.key === 'status'/)
```

- [ ] **Step 2: Run the contract and verify RED**

Run: `cd frontend && node tests/archive-lifecycle-contract.test.mjs`

Expected: FAIL because lifecycle UI does not exist.

- [ ] **Step 3: Replace status filtering with enabled filtering**

- Initialize query state with `enabled: true`.
- Provide select values `true` for 启用, `false` for 已禁用, and `null` for 全部.
- Send the parameter to `/projects/archives/list`.
- Remove all `archive_status` option fetching, column definitions and drawer editors.
- Add a narrow “启用状态” column and muted disabled-row class.

- [ ] **Step 4: Add single-row actions**

- Enabled: 编辑、同步、禁用、删除.
- Disabled: 查看、启用、删除.
- Compute `archiveDrawerReadOnly = selectedArchive?.is_enabled !== 1`.
- When read-only, never call `startArchiveFieldEdit`, hide save/sync footer actions, and show an “已禁用” badge.
- Render disabled delete as a non-clickable control with a tooltip from `formatDeleteBlockers(row.delete_blockers)`.
- Keep backend `409` details as the authoritative fallback when a stale button state reaches the server.

- [ ] **Step 5: Replace sequential batch delete**

Send selected IDs once:

```typescript
await request.post('/projects/archives/batch-delete', {
  archive_ids: selectedRows.value.map(row => row.id),
})
```

Add batch enable/disable through `/projects/archives/batch-enabled` so the backend validates scope and pending-sync blockers before one transaction. Summarize the returned result without silently skipping protected rows.

- [ ] **Step 6: Run frontend contracts and build**

Run:

```bash
cd frontend
node tests/archive-lifecycle-contract.test.mjs
node tests/archive-edit-drawer-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
npm run build
```

Expected: all contract scripts pass and Vite build exits `0`.

- [ ] **Step 7: Commit the UI unit**

```bash
git add frontend/src/views/project/ProjectArchive.vue frontend/tests/archive-lifecycle-contract.test.mjs
git commit -m "Add archive enable and deletion protection UI"
```

---

### Task 6: Rules, Change Log, Full Regression, and Browser Acceptance

**Files:**
- Modify: `AGENTS.md`
- Modify: `change.md`

**Interfaces:**
- Documents: future archive-reference registration rule
- Verifies: end-to-end lifecycle behavior

- [ ] **Step 1: Add the project rule**

Add under project archive rules:

```markdown
- 后续任何业务模块或外部系统只要引用项目档案，必须在统一项目档案生命周期服务中注册删除阻止检查；禁止仅依靠前端隐藏删除按钮或在模块内重复实现不同判断。
- 禁用项目档案必须保持只读，不得用于新建业务引用或外部同步；后端写接口始终执行最终校验。
```

- [ ] **Step 2: Run the complete backend contract set**

Run every executable backend contract so shared initialization and RBAC regressions are visible:

```bash
cd backend
for test in tests/*_contract.py; do python "$test" || exit 1; done
```

Expected: every script exits `0`; no contract prints a traceback.

- [ ] **Step 3: Run the complete frontend contract set and build**

```bash
cd frontend
for test in tests/*.test.mjs; do node "$test" || exit 1; done
npm run build
```

Expected: every script exits `0`; Vite build exits `0`.

- [ ] **Step 4: Perform browser acceptance on 1366x768 and 1600x900**

Verify with the latest branch services:

1. Default project archive list shows enabled rows only.
2. Switching to 已禁用 or 全部 returns the correct rows.
3. A pristine archive can be physically deleted.
4. A referenced archive has disabled delete with a Chinese reason and can be disabled.
5. A previously successful ERP archive cannot be deleted.
6. Disabled archive drawer is read-only and has no save/sync action.
7. Disabled archive is absent from project-progress creation options.
8. Re-enable restores allowed editing and sync actions.
9. Operation log shows Chinese enable, disable, delete and blocked-delete entries.

- [ ] **Step 5: Record actual results in `change.md`**

Use date `2026-07-17` and include reason, implemented behavior, files, migration, test totals and browser verification. Record only checks actually executed.

- [ ] **Step 6: Commit documentation and verification record**

```bash
git add AGENTS.md change.md
git commit -m "Document archive lifecycle protection rules"
```

- [ ] **Step 7: Final branch review**

Run:

```bash
git status --short
git log --oneline --decorate -8
```

Expected: clean worktree and separate commits for migration, service, enforcement, RBAC metadata, UI and documentation.
