import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = path => readFileSync(new URL('../src/' + path, import.meta.url), 'utf8')
for (const path of ['project/ProjectArchive', 'project/ProjectList', 'system/UserList', 'system/DataDictionaryList', 'system/OperationLogList']) {
  assert.match(read('views/' + path + '.vue'), /pageSize = ref\(DEFAULT_PAGE_SIZE\)/)
}
assert.match(read('config/listUi.ts'), /DEFAULT_PAGE_SIZE = 50/)
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
