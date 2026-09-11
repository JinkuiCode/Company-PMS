# PMS Unified Form System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变 PMS 业务接口、保存语义、权限和 OA/ERP 流程的前提下，建立可独立升级的统一表单基础模块，并按项目档案、项目进度、系统管理、认证与辅助页面的顺序分批迁移。

**Architecture:** 在 `frontend/src/form-system/` 建立内部模块，由表单令牌、Element Plus 字段原语、普通表单/抽屉行内编辑/AG Grid 三类场景适配器组成。业务页面仍保留原有表单数据、校验、草稿和保存函数，新模块只统一表示与交互；新样式使用 `.pms-form-*` 命名空间，未迁移页面不受影响。

**Tech Stack:** Vue 3.5、TypeScript 6、Element Plus 2.14、AG Grid 35、原生 CSS 语义令牌、Node 契约测试、Vite 8。

## Global Constraints

- 样稿基线为 `docs/prototypes/pms-form-system-v1.html`，规格基线为 `docs/superpowers/specs/2026-09-11-pms-form-system-design.md`。
- 密集行内字段高度固定为 `32px`，标准表单控件高度固定为 `36px`，水平内边距为 `10px`，文字行高为 `20px`。
- 展示、悬停和编辑状态的字段容器尺寸不变，文字 x/y 坐标差不超过 `1px`。
- 任何字段只能显示一层边界或焦点环，Element Plus 内部输入元素不再继承页面级焦点外框。
- 项目内置 `Noto Sans SC` 继续作为首选字体，不新增第二套字体栈。
- 不更换 Vue、Element Plus 或 AG Grid，不新增前端依赖。
- 不修改后端数据模型、API 语义、RBAC、字段规则、枚举校验、操作日志、OA 或 ERP 流程。
- 项目档案、主数据和外部系统引用字段继续只读；组件不得放宽业务编辑权限。
- 每个迁移批次单独提交、单独验收、可单独回退；验收失败时不进入下一批。
- 本计划只完成开发机实施和验收；服务器部署、GitHub 推送和 `master` 合并需要单独确认。

---

## File Structure

### New form-system module

- `frontend/src/form-system/types.ts`: 统一值、选项、尺寸、状态和公共 props 类型。
- `frontend/src/form-system/form-tokens.css`: 表单专用语义令牌和组件内部的 Element Plus/AG Grid 适配样式。
- `frontend/src/form-system/components/PmsControlShell.vue`: 唯一控件外容器，统一高度、边界、焦点、错误、禁用和加载状态。
- `frontend/src/form-system/components/PmsTextControl.vue`: 文本、密码及可清空输入。
- `frontend/src/form-system/components/PmsSelectControl.vue`: 单选下拉、搜索下拉和统一选项渲染。
- `frontend/src/form-system/components/PmsTreeSelectControl.vue`: 部门等树形选择。
- `frontend/src/form-system/components/PmsDateControl.vue`: 单日期和日期区间。
- `frontend/src/form-system/components/PmsNumberControl.vue`: 数值、进度和精度限制。
- `frontend/src/form-system/components/PmsTextareaControl.vue`: 长文本和自适应高度。
- `frontend/src/form-system/components/PmsSwitchControl.vue`: 立即生效布尔状态。
- `frontend/src/form-system/components/PmsCheckboxControl.vue`: 提交时生效的布尔值和多选项。
- `frontend/src/form-system/components/PmsCheckboxGroupControl.vue`: 角色产品类别等成组选项。
- `frontend/src/form-system/components/PmsSegmentedControl.vue`: 字段规则等小规模互斥视图选择。
- `frontend/src/form-system/components/PmsFormField.vue`: 标签在上的标准表单字段容器。
- `frontend/src/form-system/components/PmsInlineField.vue`: 标签在左的抽屉阅读/编辑容器。
- `frontend/src/form-system/ag-grid.ts`: AG Grid 统一编辑样式类名与 colDef 合并工具。
- `frontend/src/form-system/index.ts`: 模块唯一公共出口。

### New tests

- `frontend/tests/form-system-contract.test.mjs`: 模块文件、对外接口、令牌和内部无重影规则。
- `frontend/tests/form-system-layout-contract.test.mjs`: 标准表单、抽屉和表格容器的 DOM 责任与键盘合同。
- `frontend/tests/form-system-adoption-contract.test.mjs`: 迁移完成后禁止业务页面直接创建基础 Element Plus 表单控件。

### Existing files migrated in batches

- Project pilot: `frontend/src/views/project/ProjectArchive.vue`
- Progress workbench: `frontend/src/views/project/ProjectList.vue`、`frontend/src/views/project/ProjectProgress.vue`
- Shared list controls: `frontend/src/components/PmsListFilters.vue`、`frontend/src/components/PmsListColumnPicker.vue`
- System management: `frontend/src/views/system/UserList.vue`、`RoleList.vue`、`MenuList.vue`、`EnumList.vue`、`FieldPolicyList.vue`、`DataDictionaryList.vue`、`OperationLogList.vue`、`FieldList.vue`
- Authentication and utility: `frontend/src/views/Login.vue`、`frontend/src/views/SsoStart.vue`、`frontend/src/views/TokenGenerator.vue`
- Global entry and documentation: `frontend/src/main.ts`、`frontend/src/styles/pms-theme.css`、`docs/PMS-UI-STANDARD.md`、`change.md`

---

### Task 1: Lock the form-system public contract and tokens

**Files:**
- Create: `frontend/src/form-system/types.ts`
- Create: `frontend/src/form-system/form-tokens.css`
- Create: `frontend/src/form-system/components/PmsControlShell.vue`
- Create: `frontend/src/form-system/index.ts`
- Create: `frontend/tests/form-system-contract.test.mjs`
- Modify: `frontend/src/main.ts`

**Interfaces:**
- Produces: `PmsControlValue`, `PmsControlSize`, `PmsControlVariant`, `PmsOption`, `PmsControlStateProps`, `PmsControlShell`
- Produces CSS contract: `.pms-form-control`, `.pms-form-control--compact`, `.pms-form-control--regular`, `.is-error`, `.is-disabled`, `.is-readonly`, `.is-loading`

- [ ] **Step 1: Write the failing module contract**

```js
// frontend/tests/form-system-contract.test.mjs
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const entry = read('../src/form-system/index.ts')
const tokens = read('../src/form-system/form-tokens.css')
const main = read('../src/main.ts')

assert.match(entry, /export \{ default as PmsControlShell \}/)
assert.match(entry, /export type \{[\s\S]*PmsControlSize[\s\S]*PmsOption/)
assert.match(tokens, /--pms-form-control-height-compact:\s*32px/)
assert.match(tokens, /--pms-form-control-height-regular:\s*36px/)
assert.match(tokens, /--pms-form-control-padding-x:\s*10px/)
assert.match(tokens, /--pms-form-control-line-height:\s*20px/)
assert.match(tokens, /\.pms-form-control[\s\S]*box-sizing:\s*border-box/)
assert.match(main, /import '.\/form-system\/form-tokens\.css'/)
console.log('form system contract passed')
```

- [ ] **Step 2: Run the contract and verify RED**

Run: `cd frontend && node tests/form-system-contract.test.mjs`

Expected: FAIL because `src/form-system/index.ts` does not exist.

- [ ] **Step 3: Define exact public types**

```ts
// frontend/src/form-system/types.ts
export type PmsControlScalar = string | number | boolean | Date | null
export type PmsControlValue = PmsControlScalar | PmsControlScalar[] | undefined
export type PmsControlSize = 'compact' | 'regular'
export type PmsControlVariant = 'field' | 'binary'

export interface PmsOption {
  value: string | number | boolean
  label: string
  disabled?: boolean
}

export interface PmsControlStateProps {
  size?: PmsControlSize
  variant?: PmsControlVariant
  disabled?: boolean
  readonly?: boolean
  loading?: boolean
  error?: string
  ariaLabel?: string
}
```

- [ ] **Step 4: Implement the control shell and scoped tokens**

```vue
<!-- frontend/src/form-system/components/PmsControlShell.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import type { PmsControlStateProps } from '../types'

const props = withDefaults(defineProps<PmsControlStateProps>(), {
  size: 'regular',
  variant: 'field',
  disabled: false,
  readonly: false,
  loading: false,
  error: '',
  ariaLabel: '',
})

const classes = computed(() => ({
  [`pms-form-control--${props.size}`]: true,
  [`pms-form-control--${props.variant}`]: true,
  'is-error': Boolean(props.error),
  'is-disabled': props.disabled,
  'is-readonly': props.readonly,
  'is-loading': props.loading,
}))
</script>

<template>
  <div class="pms-form-control" :class="classes" :aria-label="ariaLabel || undefined">
    <slot />
  </div>
</template>
```

`form-tokens.css` must define the four exact dimensions from Global Constraints and keep all Element Plus internal wrapper overrides under `.pms-form-control`; no bare `.el-input__wrapper` or `.el-select__wrapper` selector is allowed in this file.

- [ ] **Step 5: Export the shell and import tokens once**

```ts
// frontend/src/form-system/index.ts
export { default as PmsControlShell } from './components/PmsControlShell.vue'
export type { PmsControlScalar, PmsControlSize, PmsControlStateProps, PmsControlValue, PmsControlVariant, PmsOption } from './types'
```

Add after the PMS theme import in `frontend/src/main.ts`:

```ts
import './form-system/form-tokens.css'
```

- [ ] **Step 6: Verify GREEN and build**

Run: `cd frontend && node tests/form-system-contract.test.mjs && npm run build`

Expected: contract prints `form system contract passed`; TypeScript and Vite exit `0`.

- [ ] **Step 7: Commit the foundation**

```bash
git add frontend/src/form-system frontend/src/main.ts frontend/tests/form-system-contract.test.mjs
git commit -m "Add PMS form system foundation"
```

---

### Task 2: Add typed Element Plus control adapters

**Files:**
- Create: `frontend/src/form-system/components/PmsTextControl.vue`
- Create: `frontend/src/form-system/components/PmsSelectControl.vue`
- Create: `frontend/src/form-system/components/PmsTreeSelectControl.vue`
- Create: `frontend/src/form-system/components/PmsDateControl.vue`
- Create: `frontend/src/form-system/components/PmsNumberControl.vue`
- Create: `frontend/src/form-system/components/PmsTextareaControl.vue`
- Create: `frontend/src/form-system/components/PmsSwitchControl.vue`
- Create: `frontend/src/form-system/components/PmsCheckboxControl.vue`
- Create: `frontend/src/form-system/components/PmsCheckboxGroupControl.vue`
- Create: `frontend/src/form-system/components/PmsSegmentedControl.vue`
- Modify: `frontend/src/form-system/index.ts`
- Modify: `frontend/tests/form-system-contract.test.mjs`

**Interfaces:**
- Consumes: `PmsControlShell`, `PmsControlStateProps`, `PmsControlValue`, `PmsOption`
- Produces: ten named control components with `v-model` through `modelValue` and `update:modelValue`

- [ ] **Step 1: Extend the failing contract for all adapters**

Add assertions that `index.ts` exports all eight components and each component template contains `PmsControlShell`. Also assert that `PmsSelectControl.vue` renders options from `PmsOption[]` and does not expose raw `<el-option>` slots to business pages.

```js
for (const component of [
  'PmsTextControl', 'PmsSelectControl', 'PmsTreeSelectControl', 'PmsDateControl',
  'PmsNumberControl', 'PmsTextareaControl', 'PmsSwitchControl', 'PmsCheckboxControl',
  'PmsCheckboxGroupControl', 'PmsSegmentedControl',
]) {
  assert.match(entry, new RegExp(`export \\{ default as ${component} \\}`))
  assert.match(read(`../src/form-system/components/${component}.vue`), /<PmsControlShell/)
}
assert.match(read('../src/form-system/components/PmsSelectControl.vue'), /options:\s*PmsOption\[\]/)
```

- [ ] **Step 2: Run the contract and verify RED**

Run: `cd frontend && node tests/form-system-contract.test.mjs`

Expected: FAIL on the first missing adapter export.

- [ ] **Step 3: Implement adapters with one outer visual surface**

Use this exact event contract for every value-bearing adapter:

```ts
defineOptions({ inheritAttrs: false })

const props = defineProps<{ modelValue: PmsControlValue } & PmsControlStateProps>()
const emit = defineEmits<{ 'update:modelValue': [value: PmsControlValue] }>()
const value = computed({
  get: () => props.modelValue,
  set: (next) => emit('update:modelValue', next),
})
```

The select adapter uses this complete option contract:

```vue
<PmsControlShell v-bind="stateProps">
  <el-select v-model="value" v-bind="$attrs" :disabled="disabled" :aria-label="ariaLabel">
    <el-option
      v-for="option in options"
      :key="String(option.value)"
      :label="option.label"
      :value="option.value"
      :disabled="option.disabled"
    />
  </el-select>
</PmsControlShell>
```

`defineOptions({ inheritAttrs: false })` is mandatory so listeners and HTML attributes reach only the inner Element Plus control instead of being duplicated on the shell. `PmsTreeSelectControl` passes tree data through a typed `data: Record<string, unknown>[]` prop. `PmsDateControl` accepts `type: 'date' | 'daterange'` and `valueFormat`. `PmsNumberControl` accepts `min`, `max`, `step`, and `precision`. `PmsTextControl` passes password, clearable and prefix/suffix attributes with `v-bind="$attrs"`. `PmsCheckboxGroupControl` and `PmsSegmentedControl` both consume `PmsOption[]`, but the former emits an array value and the latter emits one scalar value. `PmsSwitchControl`, `PmsCheckboxControl` and `PmsCheckboxGroupControl` pass `variant="binary"` to the shell; `.pms-form-control--binary` keeps the common font, focus, error and disabled semantics but does not create a rectangular 32/36px field surface.

- [ ] **Step 4: Centralize third-party internal selectors**

Add only namespace-scoped rules such as:

```css
.pms-form-control .el-input__wrapper,
.pms-form-control .el-select__wrapper,
.pms-form-control .el-textarea__inner,
.pms-form-control .el-date-editor.el-input__wrapper,
.pms-form-control .el-input-number {
  width: 100%;
  min-height: inherit;
  padding-inline: var(--pms-form-control-padding-x);
  border: 0;
  background: transparent;
  box-shadow: none;
}

.pms-form-control :is(input, textarea):focus-visible {
  outline: none;
}
```

The shell owns the only border and focus ring. Reset Element Plus select search-input negative margins inside the same namespace so selected text and search text use the same x coordinate.

- [ ] **Step 5: Verify adapters and production build**

Run: `cd frontend && node tests/form-system-contract.test.mjs && node tests/style-contract.test.mjs && npm run build`

Expected: all commands exit `0`.

- [ ] **Step 6: Commit control adapters**

```bash
git add frontend/src/form-system frontend/tests/form-system-contract.test.mjs
git commit -m "Add unified PMS form controls"
```

---

### Task 3: Add standard form, inline drawer, and AG Grid adapters

**Files:**
- Create: `frontend/src/form-system/components/PmsFormField.vue`
- Create: `frontend/src/form-system/components/PmsInlineField.vue`
- Create: `frontend/src/form-system/ag-grid.ts`
- Create: `frontend/tests/form-system-layout-contract.test.mjs`
- Modify: `frontend/src/form-system/index.ts`
- Modify: `frontend/src/form-system/form-tokens.css`

**Interfaces:**
- Produces: `PmsFormField`, `PmsInlineField`, `PMS_AG_GRID_FORM_CLASS`, `mergePmsAgCellClass()`
- `PmsInlineField` emits only `edit-request`; business pages continue owning start, commit, cancel and save functions

- [ ] **Step 1: Write the failing layout contract**

```js
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const inline = read('../src/form-system/components/PmsInlineField.vue')
const form = read('../src/form-system/components/PmsFormField.vue')
const grid = read('../src/form-system/ag-grid.ts')

assert.match(inline, /class="pms-inline-field"/)
assert.match(inline, /class="pms-inline-field__value"[\s\S]*@click="emit\('edit-request'\)"/)
assert.doesNotMatch(inline, /class="pms-inline-field"[^>]*@click/)
assert.match(inline, /<slot name="display"/)
assert.match(inline, /<slot name="editor"/)
assert.match(form, /describedBy/)
assert.match(form, /<slot[^>]*:described-by="describedBy"/)
assert.match(grid, /PMS_AG_GRID_FORM_CLASS\s*=\s*'pms-form-grid'/)
console.log('form system layout contract passed')
```

- [ ] **Step 2: Run the contract and verify RED**

Run: `cd frontend && node tests/form-system-layout-contract.test.mjs`

Expected: FAIL because the layout adapters do not exist.

- [ ] **Step 3: Implement the form and inline contracts**

`PmsFormField` props are exactly:

```ts
interface Props {
  fieldId: string
  label: string
  required?: boolean
  hint?: string
  error?: string
  span?: 1 | 2
}
```

It renders a real `<label :for="fieldId">`, hint before the control and error after the control. Its default slot exposes `{ describedBy, invalid }`, where `describedBy` contains the existing hint/error element IDs and `invalid` is `true` only when `error` is non-empty. The slot declaration is `<slot :described-by="describedBy" :invalid="Boolean(error)" />`. Every consumer binds those slot values to the shared control so accessibility is not implied only by the wrapper:

```vue
<PmsFormField v-slot="{ describedBy, invalid }" field-id="archive-project-code" label="项目编号" :error="serverError">
  <PmsTextControl
    id="archive-project-code"
    v-model="form.project_code"
    :aria-describedby="describedBy"
    :aria-invalid="invalid || undefined"
  />
</PmsFormField>
```

`PmsInlineField` props are exactly:

```ts
interface Props {
  label: string
  required?: boolean
  editable?: boolean
  editing?: boolean
  empty?: boolean
  readonlyReason?: string
  error?: string
  longText?: boolean
}
```

Only `.pms-inline-field__value` is a button when `editable && !editing`. The root row and label have no click handler. Editor and display slots occupy the same `.pms-inline-field__surface` geometry.

- [ ] **Step 4: Implement the AG Grid namespace adapter**

```ts
// frontend/src/form-system/ag-grid.ts
import type { CellClassParams, ColDef } from 'ag-grid-community'

export const PMS_AG_GRID_FORM_CLASS = 'pms-form-grid'

export function mergePmsAgCellClass<TData>(definition: ColDef<TData>): ColDef<TData> {
  const existing = definition.cellClass
  return {
    ...definition,
    cellClass: (params: CellClassParams<TData>) => {
      const base = typeof existing === 'function' ? existing(params) : existing
      return [base, 'pms-form-grid__cell'].filter(Boolean).join(' ')
    },
  }
}
```

`form-tokens.css` must make `.pms-form-grid .ag-cell-inline-editing` the only visual editing boundary and remove borders, shadows and padding from built-in input/select wrappers inside that cell.

- [ ] **Step 5: Verify layout adapters and build**

Run: `cd frontend && node tests/form-system-contract.test.mjs && node tests/form-system-layout-contract.test.mjs && npm run build`

Expected: all commands exit `0`.

- [ ] **Step 6: Commit layout adapters**

```bash
git add frontend/src/form-system frontend/tests/form-system-layout-contract.test.mjs
git commit -m "Add PMS form layout adapters"
```

---

### Task 4: Migrate Project Archive as the pilot page

**Files:**
- Modify: `frontend/src/views/project/ProjectArchive.vue`
- Modify: `frontend/tests/archive-edit-drawer-contract.test.mjs`
- Modify: `frontend/tests/archive-filter-contract.test.mjs`
- Modify: `frontend/tests/form-system-layout-contract.test.mjs`
- Modify: `change.md`

**Interfaces:**
- Consumes: all control adapters, `PmsFormField`, `PmsInlineField`
- Preserves: `archivePendingChanges`, `startArchiveFieldEdit`, `commitArchiveFieldEdit`, `cancelArchiveFieldEdit`, `saveArchiveChanges`, `saveAndSyncArchive`

- [ ] **Step 1: Replace the old product-category-only contract with the shared-system contract**

Remove the assertion that only `product_category` has `pms-inline-field-editor`. Add assertions that Project Archive imports `PmsInlineField`, `PmsTextControl`, `PmsSelectControl`, and `PmsDateControl`; every drawer field is rendered through `PmsInlineField`; and no `.archive-drawer-field-editor .el-*` override remains in the page style.

```js
assert.match(archive, /import \{[\s\S]*PmsInlineField[\s\S]*PmsTextControl[\s\S]*PmsSelectControl/)
assert.match(archive, /<PmsInlineField[\s\S]*@edit-request="startArchiveFieldEdit\(field\)"/)
assert.doesNotMatch(archive, /pms-inline-field-editor|archive-drawer-field-editor\s+\.el-/)
```

- [ ] **Step 2: Run Project Archive contracts and verify RED**

Run: `cd frontend && node tests/archive-edit-drawer-contract.test.mjs && node tests/form-system-layout-contract.test.mjs`

Expected: FAIL because Project Archive still uses its private field rows.

- [ ] **Step 3: Migrate the creation dialog without changing form state**

Keep the existing `form`, `rules`, enum options, user options and submit functions. Replace direct controls with shared controls:

```vue
<PmsFormField field-id="archive-project-code" label="项目编号" :required="archiveFieldRequired('project_code')" :error="archiveCreateServerErrors.project_code">
  <template #default="{ describedBy, invalid }">
    <PmsTextControl
      id="archive-project-code"
      v-model="form.project_code"
      placeholder="请输入项目编号"
      :disabled="!archiveFieldEditable('project_code')"
      :aria-describedby="describedBy"
      :aria-invalid="invalid || undefined"
      @update:model-value="clearArchiveServerError(archiveCreateServerErrors, 'project_code')"
    />
  </template>
</PmsFormField>
```

Use `PmsSelectControl` with normalized `PmsOption[]` for product category, manager and equipment series. Use `PmsDateControl` for plan dates. Keep `el-form` validation and the existing server-error mapping.

- [ ] **Step 4: Migrate the drawer while preserving draft behavior**

Add one page-boundary normalizer; the shared component must not know archive field keys:

```ts
function archiveDrawerSelectOptions(fieldKey: string): PmsOption[] {
  if (fieldKey === 'product_category') {
    return filteredProductCategoryOptions.value.map((item) => ({
      value: Number(item.value),
      label: String(item.label),
      disabled: Boolean(item.disabled),
    }))
  }
  if (fieldKey === 'manager_id') {
    return userList.value.map((user) => ({
      value: user.id,
      label: user.real_name || user.username,
      disabled: user.status === 0,
    }))
  }
  if (fieldKey === 'equipment_series') {
    return (dictOptions.equipment_series || []).map((item) => ({
      value: Number(item.value),
      label: String(item.label),
      disabled: Boolean(item.disabled),
    }))
  }
  return []
}

function archiveDrawerSelectPlaceholder(fieldKey: string) {
  if (fieldKey === 'product_category') return '选择产品类别'
  if (fieldKey === 'manager_id') return '选择负责人'
  return '选择设备系列'
}
```

```vue
<PmsInlineField
  v-for="field in group.fields"
  :key="field.key"
  :label="field.label"
  :required="archiveDrawerFieldRequired(field)"
  :editable="archiveDrawerFieldEditable(field)"
  :editing="archiveEditingField === field.key"
  :empty="archiveDrawerValueEmpty(field)"
  :readonly-reason="archiveDrawerReadonlyReason(field)"
  :error="archiveDrawerServerErrors[field.key]"
  @edit-request="startArchiveFieldEdit(field)"
>
  <template #display>{{ formatArchiveDrawerValue(field) }}</template>
  <template #editor>
    <PmsSelectControl
      v-if="['product_category', 'manager_id', 'equipment_series'].includes(field.key)"
      v-model="archiveDrawerForm[field.key]"
      size="compact"
      :options="archiveDrawerSelectOptions(field.key)"
      :clearable="field.key !== 'product_category'"
      filterable
      :placeholder="archiveDrawerSelectPlaceholder(field.key)"
      @change="commitArchiveFieldEdit"
      @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
    />
    <PmsDateControl
      v-else-if="field.value_type === 'date'"
      v-model="archiveDrawerForm[field.key]"
      size="compact"
      type="date"
      value-format="YYYY-MM-DD"
      placeholder="选择日期"
      @change="commitArchiveFieldEdit"
      @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
    />
    <PmsTextControl
      v-else
      v-model="archiveDrawerForm[field.key]"
      size="compact"
      :placeholder="`输入${field.label}`"
      @keydown.enter.exact.prevent="commitArchiveFieldEdit"
      @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
    />
  </template>
</PmsInlineField>
```

The editor slot must use `PmsSelectControl` for product category/manager/equipment series, `PmsDateControl` for dates, and `PmsTextControl` for text. Preserve all existing Enter/Escape handlers and do not attach an edit handler to the row or label.

- [ ] **Step 5: Remove only migrated private CSS**

Delete page-local input/select wrapper overrides, `.pms-inline-field-editor`, `.archive-drawer-field-editor` geometry and duplicate hover/focus rules. Keep drawer width, header, section, scroll, fixed footer and business-specific status styles.

- [ ] **Step 6: Run the Project Archive regression set**

Run:

```bash
cd frontend
node tests/form-system-contract.test.mjs
node tests/form-system-layout-contract.test.mjs
node tests/archive-edit-drawer-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/archive-lifecycle-contract.test.mjs
node tests/archive-lifecycle-conflict-contract.test.mjs
node tests/style-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
npm run build
```

Expected: all commands exit `0`.

- [ ] **Step 7: Perform pilot browser acceptance on the development Mac**

Verify in Edge at browser zoom 100% and viewports `1366x768` and `1600x900`:

- customer and product category keep identical x/y/width/height across display, hover and edit;
- only the clicked field value enters edit;
- select search text and selected text start at the same x coordinate;
- there is one focus ring, no nested box, and the dropdown is not clipped;
- Enter/Escape, fixed save footer, unsaved confirmation, save-and-sync, readonly and disabled states still work;
- unique conflict and required errors appear below the correct field without covering the next row.

Stop here for the user's Project Archive acceptance before Task 5.

- [ ] **Step 8: Record and commit the pilot**

```bash
git add frontend/src/views/project/ProjectArchive.vue frontend/tests change.md
git commit -m "Migrate project archive to PMS form system"
```

---

### Task 5: Migrate Project Progress drawer and grid editing

**Files:**
- Modify: `frontend/src/views/project/ProjectList.vue`
- Modify: `frontend/src/views/project/ProjectProgress.vue`
- Modify: `frontend/tests/project-progress-workbench-contract.test.mjs`
- Modify: `frontend/tests/project-sheet-detail-drawer-contract.test.mjs`
- Modify: `frontend/tests/project-list-column-preferences-contract.test.mjs`
- Modify: `frontend/tests/form-system-layout-contract.test.mjs`
- Modify: `change.md`

**Interfaces:**
- Consumes: `PmsInlineField`, typed controls, `PMS_AG_GRID_FORM_CLASS`, `mergePmsAgCellClass()`
- Preserves: list double-click editing, seven stage fields, auto-save, drawer drafts, unified drawer save, dynamic columns and field policies

- [ ] **Step 1: Add failing migration assertions**

Assert that both project progress pages import the shared controls, drawer field rows use `PmsInlineField`, the grid wrapper includes `PMS_AG_GRID_FORM_CLASS`, and page-local `.ag-cell-inline-editing .el-*` overrides are absent.

- [ ] **Step 2: Run progress contracts and verify RED**

Run: `cd frontend && node tests/project-progress-workbench-contract.test.mjs && node tests/project-sheet-detail-drawer-contract.test.mjs && node tests/form-system-layout-contract.test.mjs`

Expected: FAIL on missing shared adapters.

- [ ] **Step 3: Migrate drawer fields without moving save logic**

Keep `drawerPendingChanges`, `drawerDraftValue`, `startSheetFieldEdit`, `commitSheetFieldEdit`, `cancelSheetFieldEdit` and `saveDrawerChanges` in `ProjectList.vue`. Replace only the field presentation and editors with `PmsInlineField` plus typed controls. Progress fields continue using existing progress normalization and colored display bar.

- [ ] **Step 4: Move grid visual adaptation into the form system**

Attach `PMS_AG_GRID_FORM_CLASS` to the existing AG Grid wrapper. Pass editable column definitions through `mergePmsAgCellClass()` without changing `cellEditor`, `cellEditorParams`, `valueParser`, `onCellValueChanged` or permission checks. Remove only the equivalent page-local nested editor CSS.

- [ ] **Step 5: Run the progress regression set**

Run:

```bash
cd frontend
node tests/form-system-contract.test.mjs
node tests/form-system-layout-contract.test.mjs
node tests/project-progress-workbench-contract.test.mjs
node tests/project-sheet-detail-drawer-contract.test.mjs
node tests/project-list-column-preferences-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/style-contract.test.mjs
npm run build
```

Expected: all commands exit `0`.

- [ ] **Step 6: Perform development-browser acceptance**

Verify double-click editing for node, plan date, seven progress fields, manager and department. Confirm the editor fills the original cell, old values remain visible on entry, `0%` remains distinct from empty, failed saves restore old values, readonly archive references do not enter edit, drawer scrolling is isolated, and its save footer stays fixed.

Stop here for the user's Project Progress acceptance before Task 6.

- [ ] **Step 7: Record and commit Project Progress migration**

```bash
git add frontend/src/views/project/ProjectList.vue frontend/src/views/project/ProjectProgress.vue frontend/tests change.md
git commit -m "Migrate project progress to PMS form system"
```

---

### Task 6: Migrate shared list filters and column picker

**Files:**
- Modify: `frontend/src/components/PmsListFilters.vue`
- Modify: `frontend/src/components/PmsListColumnPicker.vue`
- Modify: `frontend/tests/list-standard-contract.test.mjs`
- Modify: `frontend/tests/archive-filter-contract.test.mjs`
- Modify: `frontend/tests/form-system-contract.test.mjs`
- Modify: `change.md`

**Interfaces:**
- Consumes: compact typed controls and checkbox adapter
- Preserves: `useListFilters` values, events, dynamic field definitions, column preference persistence and accessibility labels

- [ ] **Step 1: Add failing shared-list assertions**

Assert that `PmsListFilters.vue` uses `PmsTextControl`, `PmsSelectControl`, and `PmsDateControl` with `size="compact"`; `PmsListColumnPicker.vue` uses the shared text and checkbox controls; both files retain existing defineProps/defineEmits names.

- [ ] **Step 2: Run list contracts and verify RED**

Run: `cd frontend && node tests/list-standard-contract.test.mjs && node tests/archive-filter-contract.test.mjs`

Expected: FAIL on direct Element Plus controls.

- [ ] **Step 3: Replace controls while preserving public component APIs**

Convert current option arrays to `PmsOption[]` at the component boundary. Keep existing filter types, update events, Enter-to-search behavior, date value formats and column selection state unchanged.

- [ ] **Step 4: Verify all consumers together**

Run:

```bash
cd frontend
node tests/form-system-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
node tests/project-progress-workbench-contract.test.mjs
npm run build
```

Expected: all commands exit `0`.

- [ ] **Step 5: Record and commit shared list migration**

```bash
git add frontend/src/components frontend/tests change.md
git commit -m "Migrate shared list controls to form system"
```

---

### Task 7: Migrate System Management write forms

**Files:**
- Modify: `frontend/src/views/system/UserList.vue`
- Modify: `frontend/src/views/system/RoleList.vue`
- Modify: `frontend/src/views/system/MenuList.vue`
- Modify: `frontend/src/views/system/EnumList.vue`
- Modify: `frontend/src/views/system/FieldPolicyList.vue`
- Modify: `frontend/tests/system-ui-consistency-contract.test.mjs`
- Modify: `frontend/tests/enum-management-contract.test.mjs`
- Modify: `frontend/tests/field-policy-contract.test.mjs`
- Modify: `change.md`

**Interfaces:**
- Consumes: standard controls, form field container, tree select, switch, checkbox, checkbox-group and segmented adapters
- Preserves: role permissions, role data scope, product category ranges, enum storage values, field-policy concurrency timestamp and structured server errors

- [ ] **Step 1: Add failing per-page adoption assertions**

For each page, assert imports from `@/form-system` and assert absence of direct `<el-input>`, `<el-select>`, `<el-tree-select>`, `<el-switch>` and `<el-checkbox>` tags.

- [ ] **Step 2: Run system contracts and verify RED**

Run: `cd frontend && node tests/system-ui-consistency-contract.test.mjs && node tests/enum-management-contract.test.mjs && node tests/field-policy-contract.test.mjs`

Expected: FAIL on the first page that still renders raw controls.

- [ ] **Step 3: Migrate User and Role forms**

Use `PmsTreeSelectControl` for departments, `PmsSelectControl` for roles/data scope, `PmsSwitchControl` for active status, `PmsCheckboxGroupControl` for role product-category ranges and the existing checked-tree mechanism for menu permissions. Keep current payload types and convert UI option objects to `PmsOption[]` without converting stored IDs to labels.

- [ ] **Step 4: Migrate Menu, Enum and Field Policy forms**

Use shared controls while preserving menu type routing, immutable enum storage value, enabled/disabled behavior, reference-count delete protection, field-policy valid-combination disabling and optimistic concurrency `updated_at` checks. Replace Field Policy's direct `el-segmented` with `PmsSegmentedControl` while keeping the existing module values and switching behavior unchanged.

- [ ] **Step 5: Verify System Management regressions**

Run:

```bash
cd frontend
node tests/form-system-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
node tests/enum-management-contract.test.mjs
node tests/field-policy-contract.test.mjs
node tests/style-contract.test.mjs
npm run build
```

Expected: all commands exit `0`.

- [ ] **Step 6: Browser acceptance and checkpoint**

Verify create/edit/disable flows for one user, one role, one enum value and one field policy. Confirm labels, required marks, errors, switches, tree selection and disabled controls use the shared style without changing runtime permissions or numeric enum values.

Stop here for the user's System Management acceptance before Task 8.

- [ ] **Step 7: Record and commit write-form migration**

```bash
git add frontend/src/views/system frontend/tests change.md
git commit -m "Migrate system management forms"
```

---

### Task 8: Migrate read-only queries, authentication, and utility forms

**Files:**
- Modify: `frontend/src/views/system/DataDictionaryList.vue`
- Modify: `frontend/src/views/system/OperationLogList.vue`
- Modify: `frontend/src/views/system/FieldList.vue`
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/views/SsoStart.vue`
- Modify: `frontend/src/views/TokenGenerator.vue`
- Modify: `frontend/tests/data-dictionary-contract.test.mjs`
- Modify: `frontend/tests/login-security-contract.test.mjs`
- Modify: `frontend/tests/system-ui-consistency-contract.test.mjs`
- Modify: `change.md`

**Interfaces:**
- Consumes: compact/regular text, select, date, checkbox and form-field adapters
- Preserves: field-catalog filters, operation-log query semantics, empty login credentials, OA SSO behavior and token generation permissions

- [ ] **Step 1: Add failing adoption assertions**

Assert each listed page imports the form system and does not instantiate direct Element Plus base controls. Retain explicit assertions that Login has no prefilled username/password and SSO callback/security behavior is unchanged.

- [ ] **Step 2: Run contracts and verify RED**

Run: `cd frontend && node tests/data-dictionary-contract.test.mjs && node tests/login-security-contract.test.mjs && node tests/system-ui-consistency-contract.test.mjs`

Expected: FAIL on missing shared controls.

- [ ] **Step 3: Migrate query and legacy pages**

Convert Data Dictionary and Operation Log filters to compact shared controls. Keep query parameter names, pagination, Chinese `diff_items`, technical-field expansion and permission checks unchanged. Convert the legacy Field page without reactivating hidden legacy classifications.

- [ ] **Step 4: Migrate Login, SSO Start and Token Generator**

Use regular shared controls, preserve password visibility behavior and browser autofill attributes, keep Login values empty on mount, keep the OA portal instruction, and retain all existing authentication endpoints and permission checks. `SsoStart.vue` checkbox uses `PmsCheckboxControl`; no credentials or tokens are written into placeholder text.

- [ ] **Step 5: Verify security and query regressions**

Run:

```bash
cd frontend
node tests/form-system-contract.test.mjs
node tests/data-dictionary-contract.test.mjs
node tests/login-security-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
node tests/style-contract.test.mjs
npm run build
```

Expected: all commands exit `0`.

- [ ] **Step 6: Record and commit remaining page migration**

```bash
git add frontend/src/views frontend/tests change.md
git commit -m "Finish PMS form system page migration"
```

---

### Task 9: Enforce future adoption, remove legacy overrides, and complete development acceptance

**Files:**
- Create: `frontend/tests/form-system-adoption-contract.test.mjs`
- Modify: `frontend/src/styles/pms-theme.css`
- Modify: `frontend/tests/style-contract.test.mjs`
- Modify: `docs/PMS-UI-STANDARD.md`
- Modify: `change.md`

**Interfaces:**
- Consumes: completed form-system exports and all migrated pages
- Produces: permanent guard preventing future raw base-control drift

- [ ] **Step 1: Write the failing adoption guard**

```js
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(new URL('../src', import.meta.url).pathname)
const allowed = `${root}/form-system/`
const rawControls = /<el-(input|select|tree-select|date-picker|input-number|switch|checkbox|checkbox-group|segmented)(?:\s|>)/

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = resolve(dir, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
}

for (const path of walk(root).filter((path) => path.endsWith('.vue') && !path.startsWith(allowed))) {
  assert.doesNotMatch(readFileSync(path, 'utf8'), rawControls, `${path} must use @/form-system controls`)
}
console.log('form system adoption contract passed')
```

- [ ] **Step 2: Run adoption guard and verify RED if any page was missed**

Run: `cd frontend && node tests/form-system-adoption-contract.test.mjs`

Expected before cleanup: FAIL with the exact remaining source path, or PASS if every page was migrated in Tasks 4-8.

- [ ] **Step 3: Remove remaining page/global form exceptions**

Replace any missed raw control through `@/form-system`. Remove legacy global `.el-input__wrapper`, `.el-select__wrapper`, `.el-textarea__inner` visual overrides from `pms-theme.css` only after the adoption guard proves that all base controls pass through the new shell. Keep non-form Element Plus theme variables and component styles.

- [ ] **Step 4: Document the permanent development rule**

Add to `docs/PMS-UI-STANDARD.md`:

```markdown
## 统一表单系统

- 业务页面必须从 `@/form-system` 导入基础字段组件，不得直接使用 Element Plus 的 input/select/date/number/textarea/tree-select/switch/checkbox。
- 普通表单使用 `PmsFormField`，抽屉行内编辑使用 `PmsInlineField`，AG Grid 编辑使用 `PMS_AG_GRID_FORM_CLASS` 和 `mergePmsAgCellClass()`。
- 业务页面不得覆盖 Element Plus 控件内部 DOM 类名；第三方兼容修复只能放在 `form-system/form-tokens.css`。
- 新增字段必须同时验证默认、悬停、编辑、焦点、错误、禁用和只读状态。
```

- [ ] **Step 5: Run the complete frontend gate**

Run:

```bash
cd frontend
node tests/form-system-contract.test.mjs
node tests/form-system-layout-contract.test.mjs
node tests/form-system-adoption-contract.test.mjs
node tests/style-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/archive-edit-drawer-contract.test.mjs
node tests/archive-lifecycle-contract.test.mjs
node tests/archive-lifecycle-conflict-contract.test.mjs
node tests/project-progress-workbench-contract.test.mjs
node tests/project-sheet-detail-drawer-contract.test.mjs
node tests/project-list-column-preferences-contract.test.mjs
node tests/data-dictionary-contract.test.mjs
node tests/enum-management-contract.test.mjs
node tests/field-policy-contract.test.mjs
node tests/login-security-contract.test.mjs
npm run build
```

Expected: every contract prints its pass message and exits `0`; `vue-tsc -b` and `vite build` exit `0`.

- [ ] **Step 6: Complete cross-platform development acceptance**

On macOS Edge and Windows Edge, verify browser zoom 100%; on Windows additionally verify display scaling 100% and 125%. At `1366x768` and `1600x900`, compare Project Archive, Project Progress, User, Role, Enum, Field Policy and Login for:

- no nested borders, focus shadows or text jumps;
- dropdown, date picker, tree select and validation popovers are not clipped;
- keyboard focus is visible exactly once;
- labels, required marks, placeholders, disabled and readonly states remain readable;
- list pagination, drawers and fixed action bars do not move the whole page;
- business save, auto-save, ERP sync, RBAC and field-policy behavior matches the pre-migration baseline.

Stop for the user's final development-machine acceptance. Do not deploy the server in this task.

- [ ] **Step 7: Record and commit final cleanup**

```bash
git add frontend/src frontend/tests docs/PMS-UI-STANDARD.md change.md
git commit -m "Enforce unified PMS form system"
```

---

## Final Development Deliverables

- A versioned internal form module under `frontend/src/form-system/`.
- Project Archive and Project Progress migrated and separately accepted.
- Shared list controls, System Management, Login/SSO and utility forms migrated.
- No direct base Element Plus field controls outside the form-system module.
- Existing API, RBAC, field-policy, enum, OA, ERP and operation-log behavior preserved.
- Complete contract/build evidence plus Mac and Windows visual acceptance evidence.
- No server deployment, GitHub push or `master` merge until separately approved.
