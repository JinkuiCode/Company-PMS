import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const projectList = read('src/views/project/ProjectList.vue')

assert.match(
  projectList,
  /project-progress-workbench/,
  'Project progress entry should use the confirmed workbench layout shell',
)
assert.match(
  projectList,
  /currentViewName/,
  'Project progress workbench should show the one active view as static context',
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
assert.match(
  projectList,
  /materializeStageProgressDefaults/,
  'Stage progress rows should materialize display defaults before editing',
)
assert.match(
  projectList,
  /rowData\.value = res\.items\.map\(materializeStageProgressDefaults\)/,
  'Fetched rows should expose the visible stage progress value to AG Grid editors',
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
  /field:\s*'design_progress'[\s\S]*?editable:\s*true/,
  'Design progress should be editable from the progress table',
)
assert.match(
  projectList,
  /field:\s*'test_progress'[\s\S]*?editable:\s*true/,
  'Test progress should be editable from the progress table',
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

console.log('project progress workbench contract passed')
