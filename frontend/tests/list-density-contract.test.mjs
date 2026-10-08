import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = path => readFileSync(new URL('../src/' + path, import.meta.url), 'utf8')
for (const path of ['project/ProjectArchive', 'project/ProjectList', 'system/UserList', 'system/DataDictionaryList', 'system/OperationLogList']) {
  assert.match(read('views/' + path + '.vue'), /pageSize = ref\(DEFAULT_PAGE_SIZE\)/)
}
assert.match(read('config/listUi.ts'), /DEFAULT_PAGE_SIZE = 50/)
const theme = read('styles/pms-theme.css')
for (const [token, value] of Object.entries({ 'header-height': 44, 'page-inset': 6, 'panel-inset': 8, 'query-height': 24, 'pagination-height': 26, 'grid-row-height': 32, 'grid-header-height': 30, 'grid-group-height': 26, 'drawer-width': 460 })) {
  assert.match(theme, new RegExp(`--pms-${token}: ${value}px`))
}
assert.match(read('config/listUi.ts'), /rowHeight: 32/)
assert.match(read('config/listUi.ts'), /headerHeight: 30/)
assert.match(read('config/listUi.ts'), /groupHeaderHeight: 26/)
assert.match(theme, /\.ag-header-group-cell-label\s*\{\s*justify-content: center;/)
assert.match(read('form-system/form-tokens.css'), /\.pms-query-density\s*\{[^}]*--pms-form-control-height-compact: var\(--pms-query-height\)/)
for (const name of ['InventoryList', 'PurchaseProgressList', 'StockDetailList']) {
  assert.doesNotMatch(read(`views/reports/${name}.vue`), /:row-height|:header-height/, `${name} must use shared grid dimensions`)
}
assert.match(read('config/listUi.ts'), /tooltipShowDelay: 200/)
assert.doesNotMatch(read('views/project/ProjectArchive.vue'), /Math.min\(430/)
assert.doesNotMatch(read('views/project/ProjectList.vue'), /domLayout="'autoHeight'"/)
const actions = read('views/project/ProjectArchive.vue').split('const ArchiveActionsRenderer')[1].split('function archiveColumnVisibility')[0]
assert.doesNotMatch(actions, /archiveActionButton\('(删除|禁用|启用)'/)
assert.match(read('views/project/ProjectArchive.vue'), /handleBatchEnabledChange/)
assert.match(read('styles/pms-theme.css'), /pms-actions-cell/)
for (const view of ['EnumList', 'RoleList']) {
  assert.match(read('views/system/' + view + '.vue'), /height="100%"/)
}
console.log('list density contract passed')
