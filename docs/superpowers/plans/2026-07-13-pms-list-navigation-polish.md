# PMS List And Navigation Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收窄并分层左侧导航，为项目档案增加可持久化列设置并统一表头，同时收紧项目进度操作列。

**Architecture:** 保留现有 `PmsDataList`、AG Grid 和权限消费模式。扩展共享列选择器的通用接口，由项目档案维护自己的列元数据和浏览器偏好；导航和项目进度仅做局部布局调整。

**Tech Stack:** Vue 3、TypeScript、Element Plus、AG Grid、Node.js 契约测试、CSS scoped styles。

## Global Constraints

- PMS UI 保持浅色、紧凑、冷灰背景和克制靛蓝主色。
- 引用字段、RBAC、OA、ERP 与后端接口不在本次修改范围内。
- 项目编号、项目名称、选择列和操作列不得从项目档案列表隐藏。
- 列偏好仅保存到当前用户、当前浏览器。
- 所有调整追加记录到 `change.md`。

---

### Task 1: Add Failing UI Contract

**Files:**
- Create: `frontend/tests/list-navigation-polish-contract.test.mjs`

**Interfaces:**
- Consumes: `AppLayout.vue`、`ProjectArchive.vue`、`ProjectList.vue` 和 `PmsListColumnPicker.vue` 的源码契约。
- Produces: 后续三个实现任务必须满足的静态行为断言。

- [ ] **Step 1: Write the failing contract**

```js
assert.match(layout, /isCollapse \? '64px' : '184px'/)
assert.match(layout, /submenu-guide/)
assert.match(archive, /PmsListColumnPicker/)
assert.match(archive, /archive-list-header-center/)
assert.doesNotMatch(archive, /保存布局/)
assert.match(projectList, /hasPermission\('project:list:delete'\) \? 88 : 60/)
assert.match(columnPicker, /restore-defaults/)
```

- [ ] **Step 2: Run the contract and verify RED**

Run: `cd frontend && node tests/list-navigation-polish-contract.test.mjs`

Expected: FAIL because the sidebar still uses `220px`, archive has no shared column picker, and the operation column still uses `118px`.

- [ ] **Step 3: Commit the failing contract**

```bash
git add frontend/tests/list-navigation-polish-contract.test.mjs
git commit -m "test: define list and navigation polish contract"
```

### Task 2: Generalize The Column Picker And Add Archive Column Preferences

**Files:**
- Modify: `frontend/src/components/PmsListColumnPicker.vue`
- Modify: `frontend/src/views/project/ProjectArchive.vue`
- Test: `frontend/tests/list-navigation-polish-contract.test.mjs`

**Interfaces:**
- Consumes: `PmsListColumnPicker` existing `modelValue`, `groups` and `defaultKeys` props.
- Produces: `ariaLabel?: string` prop and `restore-defaults` event; archive column preference state stored under `pms_project_archive_list_columns_v1:<user-id>`.

- [ ] **Step 1: Extend the shared picker**

Add `ariaLabel?: string` and emit `restore-defaults` before restoring `defaultKeys`. Use `props.ariaLabel || '项目进度列设置'` for the panel accessible name.

- [ ] **Step 2: Replace archive layout buttons with the picker**

Render `PmsListColumnPicker` in `toolbar-right`, bind configurable archive column keys, and handle `restore-defaults` by resetting AG Grid column state.

- [ ] **Step 3: Add archive column metadata and persistence**

Define grouped metadata for business, plan, audit and ERP fields. Persist this shape:

```ts
type ArchiveColumnPreferenceState = {
  selected_column_keys: string[]
  column_state: ColumnState[]
}
```

Apply visibility through AG Grid column state, automatically persist move/resize/pin/visibility events, and migrate the legacy `pms_archive_grid_layout_v2` array when no new preference exists.

- [ ] **Step 4: Center archive headers**

Set `headerClass: 'archive-list-header-center'` in `defaultColDef` and add a scoped deep selector that centers `.ag-header-cell-label`.

- [ ] **Step 5: Run the focused contract**

Run: `cd frontend && node tests/list-navigation-polish-contract.test.mjs`

Expected: archive and picker assertions PASS; navigation and operation width assertions may still fail until Task 3.

- [ ] **Step 6: Commit the archive behavior**

```bash
git add frontend/src/components/PmsListColumnPicker.vue frontend/src/views/project/ProjectArchive.vue frontend/tests/list-navigation-polish-contract.test.mjs
git commit -m "feat: add project archive column settings"
```

### Task 3: Implement Navigation Scheme C And Tighten Progress Actions

**Files:**
- Modify: `frontend/src/layout/AppLayout.vue`
- Modify: `frontend/src/views/project/ProjectList.vue`
- Test: `frontend/tests/list-navigation-polish-contract.test.mjs`

**Interfaces:**
- Consumes: current Element Plus nested menu DOM and existing `hasPermission()` helper.
- Produces: `184px` expanded sidebar, guided submenu styling, and a permission-aware operation column width.

- [ ] **Step 1: Implement the 184px sidebar**

Change the expanded aside width to `184px`. Add a `submenu-guide` class to child menu regions and style a neutral vertical guide line, `36px` child rows and an accent dot for the active child. Keep the collapsed width at `64px` and exclude collapsed menus from guide styling.

- [ ] **Step 2: Implement the compact operation column**

Set operation column `width`, `minWidth` and `maxWidth` from:

```ts
const actionColumnWidth = hasPermission('project:list:delete') ? 88 : 60
```

Center `.progress-row-actions` and retain the current permission-controlled more button.

- [ ] **Step 3: Run the focused contract and verify GREEN**

Run: `cd frontend && node tests/list-navigation-polish-contract.test.mjs`

Expected: `list navigation polish contract passed`.

- [ ] **Step 4: Commit navigation and action layout**

```bash
git add frontend/src/layout/AppLayout.vue frontend/src/views/project/ProjectList.vue frontend/tests/list-navigation-polish-contract.test.mjs
git commit -m "feat: polish navigation and list actions"
```

### Task 4: Traceability, Regression Verification And Visual QA

**Files:**
- Modify: `change.md`

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: traceable change record and verified production build.

- [ ] **Step 1: Append the change record**

Record the selected navigation scheme C, archive column preference behavior, centered headers, action width rules and validation commands in `change.md`.

- [ ] **Step 2: Run all relevant contracts**

```bash
cd frontend
node tests/list-navigation-polish-contract.test.mjs
node tests/style-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/project-progress-workbench-contract.test.mjs
npm run build
```

Expected: all contracts print `passed`; build exits `0` with only the existing chunk-size advisory.

- [ ] **Step 3: Run visual QA**

Start the worktree frontend on a free port, inspect project archive and project progress at 1366×768 and 1600×900, and verify navigation hierarchy, column picker, header centering, operation width, scrolling and pagination.

- [ ] **Step 4: Commit traceability updates**

```bash
git add change.md docs/superpowers/specs/2026-07-13-pms-list-navigation-polish-design.md docs/superpowers/plans/2026-07-13-pms-list-navigation-polish.md
git commit -m "docs: record list and navigation polish"
```

