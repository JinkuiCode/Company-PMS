import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const layout = read('src/layout/AppLayout.vue')
const archive = read('src/views/project/ProjectArchive.vue')
const progress = read('src/views/project/ProjectList.vue')
const columnPicker = read('src/components/PmsListColumnPicker.vue')

assert.match(
  layout,
  /:width="isCollapse \? '64px' : '184px'"/,
  'Expanded navigation should use the approved 184px width',
)
assert.match(
  layout,
  /class="submenu-guide"/,
  'Second-level navigation items should opt into the C-style hierarchy guide',
)
assert.match(
  layout,
  /\.el-sub-menu \.el-menu::before[\s\S]*?height:\s*calc\(100% - 8px\)/,
  'Expanded second-level navigation should render a persistent vertical guide line',
)
assert.match(
  layout,
  /\.submenu-guide\.is-active::before[\s\S]*?border-radius:\s*50%/,
  'The active second-level navigation item should mark its position on the guide line',
)

assert.match(
  archive,
  /PmsListColumnPicker/,
  'Project archive should reuse the standard column picker',
)
assert.match(
  archive,
  /pms_project_archive_list_columns_v2/,
  'Project archive should persist column selection and layout with the agreed storage key',
)
assert.match(
  archive,
  /archiveColumnGroups/,
  'Project archive should expose grouped configurable columns',
)
assert.match(
  archive,
  /selectedArchiveColumnKeys/,
  'Project archive should track optional visible columns separately from fixed columns',
)
assert.match(
  archive,
  /fixedArchiveColumnKeys[\s\S]*?reconciledState[\s\S]*?hide:\s*false/,
  'Restored AG Grid state should never hide fixed project archive columns',
)
assert.match(
  archive,
  /availableArchiveColumnKeys\.value\.has\(state\.colId\)[\s\S]*?hide:\s*!selectedKeys\.has\(state\.colId\)/,
  'Restored optional-column visibility should follow the column-picker selection',
)
assert.match(
  archive,
  /headerClass:\s*'archive-list-header-center'/,
  'All ordinary project archive headers should opt into centered alignment',
)
assert.match(
  archive,
  /:deep\(\.archive-list-header-center \.ag-header-cell-label\)[\s\S]*?justify-content:\s*center;/,
  'Project archive header labels should be centered visually',
)
assert.doesNotMatch(
  archive,
  />保存布局</,
  'Project archive should replace the separate save-layout button with automatic column persistence',
)
assert.match(
  columnPicker,
  /ariaLabel\?:\s*string/,
  'The reusable column picker should accept a page-specific accessible label',
)
assert.match(
  columnPicker,
  /'restore-defaults':\s*\[\]/,
  'The reusable column picker should notify pages when all layout preferences must be reset',
)

assert.match(
  progress,
  /const actionColumnWidth = computed\(\(\) => hasPermission\('project:list:delete'\) \? 88 : 60\)/,
  'Project progress operation width should shrink according to available actions',
)
assert.match(
  progress,
  /headerName:\s*'操作',[\s\S]*?width:\s*actionColumnWidth\.value,[\s\S]*?minWidth:\s*actionColumnWidth\.value,[\s\S]*?maxWidth:\s*actionColumnWidth\.value/,
  'Project progress operation column should keep the compact width fixed',
)
assert.match(
  progress,
  /\.progress-row-actions\)[\s\S]*?justify-content:\s*center;[\s\S]*?width:\s*100%;/,
  'Project progress row actions should be centered in the compact column',
)

console.log('list navigation polish contract passed')
