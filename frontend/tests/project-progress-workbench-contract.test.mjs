import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const projectList = read('src/views/project/ProjectList.vue')

assert.match(
  projectList,
  /project-progress-workbench/,
  'Project progress entry should use the confirmed workbench layout shell',
)
assert.doesNotMatch(
  projectList,
  /currentViewName|当前只开放总进度视图|单击选中；双击进度\/计划字段自动保存；点右侧详情展开抽屉/,
  'Project progress workbench should not reserve business space for inactive-view or operation-guide copy',
)
assert.doesNotMatch(
  projectList,
  /progressViews|v-for="view in progressViews"/,
  'Project progress workbench should not expose fake multi-view tabs before real views exist',
)
assert.doesNotMatch(
  projectList,
  /fieldGroups|activeFieldGroup|v-for="group in fieldGroups"/,
  'Project progress workbench should not expose fake field-group chips that only change highlight state',
)
assert.match(
  projectList,
  /progress-detail-drawer/,
  'Project progress workbench should include an explicit detail drawer',
)
assert.match(
  projectList,
  /selectedProject/,
  'Project progress workbench should keep selected row state for the drawer',
)
assert.match(
  projectList,
  /PmsListColumnPicker/,
  'Project progress toolbar should expose the reusable column picker',
)
assert.match(
  projectList,
  /pms_project_progress_list_columns_v1/,
  'Project progress list should persist selected columns and grid state with the agreed storage key',
)
assert.match(
  projectList,
  /selectedSheetFieldKeys/,
  'Project progress list should track selected dynamic sheet columns separately from fixed columns',
)
assert.match(
  projectList,
  /const defaultSelectedSheetFieldKeys = computed<string\[\]>\(\(\) => \[\]\)/,
  'Fixed core columns should stay the default while optional sheet columns start unselected',
)
assert.match(
  projectList,
  /sheet_field_keys/,
  'Project progress list requests should include dynamic sheet field keys when needed',
)
assert.match(
  projectList,
  /currentFilterSheetFieldKeys|filterSheetFieldKeys/,
  'Project progress list should union selected columns with sheet-backed custom filters before fetching data',
)
assert.match(
  projectList,
  /@cell-double-clicked="onProjectCellDoubleClicked"/,
  'Double-clicking an editable progress cell should enter edit mode',
)
assert.doesNotMatch(
  projectList,
  /field === 'product_line'/,
  'Progress page should not save archive-derived product line edits',
)
assert.doesNotMatch(
  projectList,
  /stageProgressOffsets|materializeStageProgressDefaults|total_progress\) \+ stageProgressOffsets/,
  'Stage columns should not fabricate values from the legacy task-based total progress',
)
assert.match(
  projectList,
  /function renderProgressBar\(value: number \| null \| undefined\)[\s\S]*?if \(value == null\) return/,
  'An unmaintained stage should render as an explicit empty value instead of a synthetic 0%',
)
assert.match(
  projectList,
  /<el-collapse/,
  'Project detail drawer should switch to vertical collapse sections',
)
assert.match(
  projectList,
  /drawerOpenGroups/,
  'Project detail drawer should allow multiple groups to stay expanded',
)
assert.match(
  projectList,
  /basic[\s\S]*stage[\s\S]*plan|stage[\s\S]*basic[\s\S]*plan|plan[\s\S]*basic[\s\S]*stage/,
  'Project detail drawer should default-open the basic, stage, and plan groups',
)
assert.doesNotMatch(
  projectList,
  /drawer-hint|drawer-tabs|activeDrawerTab|drawerTabs/,
  'Project detail drawer should remove the old hint banner and horizontal tab state',
)
assert.match(
  projectList,
  /sheetProjectFieldMap/,
  'Progress detail drawer should route editable project-backed fields through an explicit mapping',
)
assert.match(
  projectList,
  /design_progress:\s*'design_progress'/,
  'Design progress should remain editable from the dynamic sheet-detail drawer',
)
assert.match(
  projectList,
  /progressFieldKeys/,
  'Stage progress fields should share an explicit save path',
)
assert.match(
  projectList,
  /field:\s*'design_progress'[\s\S]*?editable:\s*\(\)\s*=>\s*hasPermission\('project:list:edit'\)/,
  'Design progress should be editable from the progress table only with edit permission',
)
assert.match(
  projectList,
  /field:\s*'test_progress'[\s\S]*?editable:\s*\(\)\s*=>\s*hasPermission\('project:list:edit'\)/,
  'Test progress should be editable from the progress table only with edit permission',
)
assert.match(
  projectList,
  /const projectStatusEditorValues = computed\(\(\) => projectStatusOptions\.map\(item => item\.value\)\)/,
  'Node editor options should keep the numeric project-status values used by the row data',
)
assert.match(
  projectList,
  /field:\s*'status'[\s\S]*?valueFormatter:\s*\(params: any\) => statusLabel\(params\.value\)[\s\S]*?cellEditorParams:\s*\(\) => \(\{ values: projectStatusEditorValues\.value \}\)/,
  'Node editor should display Chinese labels while matching and saving numeric status values',
)
assert.match(
  projectList,
  /:defaultColGroupDef="defaultColGroupDef"/,
  'Project progress group headers should receive the same alignment rule as ordinary headers',
)
assert.match(
  projectList,
  /const defaultColDef: ColDef = \{[\s\S]*?headerClass:\s*'progress-list-header-center'/,
  'All ordinary project-progress headers should opt into centered alignment',
)
assert.match(
  projectList,
  /const defaultColGroupDef: Partial<ColGroupDef<ProjectRow>> = \{[\s\S]*?headerClass:\s*'progress-list-header-center'/,
  'All project-progress group headers should opt into centered alignment',
)
assert.match(
  projectList,
  /:deep\(\.progress-list-header-center \.ag-header-cell-label\),[\s\S]*?:deep\(\.progress-list-header-center \.ag-header-group-cell-label\)[\s\S]*?justify-content:\s*center;/,
  'Centered header styling should cover both ordinary and grouped column labels',
)
assert.match(
  projectList,
  /:deep\(\.progress-workbench-grid \.ag-cell-inline-editing\) \{[\s\S]*?border:\s*0;[\s\S]*?border-radius:\s*0;[\s\S]*?box-shadow:\s*inset 0 0 0 1px rgba\(79, 70, 229, 0\.42\);/,
  'Inline editing should keep one full-cell focus boundary instead of an additional card frame',
)
assert.match(
  projectList,
  /:deep\(\.progress-workbench-grid \.ag-cell-inline-editing \.ag-cell-edit-wrapper\),[\s\S]*?:deep\(\.progress-workbench-grid \.ag-cell-inline-editing \.ag-picker-field-wrapper\) \{[\s\S]*?border:\s*0 !important;[\s\S]*?border-radius:\s*0 !important;[\s\S]*?box-shadow:\s*none !important;/,
  'Editors inside the project progress grid should not render a second nested input border',
)
assert.doesNotMatch(
  projectList,
  /colId:\s*'design_progress'/,
  'Stage progress columns should use real fields rather than display-only colIds',
)
assert.match(
  projectList,
  /openProjectDrawer/,
  'Project progress drawer should open through an explicit detail action',
)
assert.match(
  projectList,
  /aria-expanded/,
  'Project detail collapse triggers should expose expanded state for accessibility',
)
assert.match(
  projectList,
  /详情/,
  'Project progress table should expose a visible detail affordance',
)
assert.doesNotMatch(
  projectList,
  /@row-clicked="onProjectRowClicked"/,
  'Single-clicking a project row should not open the drawer',
)
assert.match(
  projectList,
  /closeProjectDrawer/,
  'Project progress drawer should provide an explicit close action',
)
assert.doesNotMatch(
  projectList,
  /drawer-legend|legend-dot/,
  'Progress drawer should not show misleading static editable/read-only/saved legend chips',
)
assert.doesNotMatch(
  projectList,
  /router\.push\(\{\s*name:\s*['"]ProjectProgress['"]/,
  'Project progress list should not navigate to the old task-list detail page from the row',
)
assert.doesNotMatch(
  projectList,
  /summary-strip|summary-card|metric-card/,
  'Project progress workbench should not reserve first-screen space for statistic cards',
)
assert.doesNotMatch(
  projectList,
  /headerName:\s*'关联任务'/,
  'The legacy related-task count should not occupy the current project progress list',
)
assert.doesNotMatch(
  projectList,
  /\{ field: 'task_count', label: '任务数'/,
  'The legacy related-task count should not remain a custom filter in the current progress workbench',
)

const savedTextFunction = projectList.match(/function setSavedText\([\s\S]*?\n}\n\nasync function openProjectDrawer/)
assert.ok(savedTextFunction, 'Project progress workbench should keep auto-save feedback in a dedicated helper')
assert.doesNotMatch(
  savedTextFunction[0],
  /selectedProject\.value/,
  'Auto-saving a grid cell must not open or replace the explicit detail drawer selection',
)

const pmSaveBranch = projectList.match(/if \(field === 'pm_name'\) \{[\s\S]*?\n  }\n\n  await request\.put/)
assert.ok(pmSaveBranch, 'Project manager edits should keep their dedicated save branch')
assert.equal(
  (pmSaveBranch[0].match(/await request\.put/g) || []).length,
  2,
  'Project manager edits should issue exactly one request in their branch before the generic save path',
)

assert.match(
  projectList,
  /const columnPreferencesReady = ref\(false\)/,
  'Project list should expose an explicit readiness gate before restoring column preferences',
)
assert.match(
  projectList,
  /columnPreferencesReady\.value \? requestedSheetFieldKeys\.value\.join\(','\) : '__pending__'/,
  'Initial list loading should wait for restored selected-field preferences',
)
assert.match(
  projectList,
  /if \(!columnPreferenceWritesEnabled\.value\) return\n    persistColumnPreferences\(\)/,
  'Selected-field persistence should wait until selected fields and AG Grid state have been restored',
)
assert.match(
  projectList,
  /if \(!columnPreferenceWritesEnabled\.value \|\| restoringColumnState\.value\) return/,
  'Initial AG Grid structure events should not overwrite restored preferences',
)
assert.match(
  projectList,
  /const listRequestSerial = ref\(0\)/,
  'Project list should version concurrent list requests',
)
assert.match(
  projectList,
  /const requestSerial = \+\+listRequestSerial\.value[\s\S]*?if \(requestSerial !== listRequestSerial\.value\) return/,
  'An older list response must not overwrite a later selected-field request',
)

console.log('project progress workbench contract passed')
