import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const archive = readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')
const listFilters = readFileSync(new URL('../src/components/PmsListFilters.vue', import.meta.url), 'utf8')

assert.match(archive, /archiveFilterFields/, 'Project archive should define configurable filter fields')
assert.match(archive, /customFilters/, 'Project archive should store user-added custom filters')
assert.match(listFilters, /添加筛选/, 'Shared list filter component should expose an add-filter control')
assert.match(listFilters, /清空筛选/, 'Shared list filter component should expose a clear custom filters control')
assert.match(listFilters, /PmsSelectControl/, 'Archive custom filters should receive shared compact select controls')
assert.match(listFilters, /PmsDateControl/, 'Archive custom filters should receive shared compact date controls')
assert.match(listFilters, /value-format="YYYY-MM-DD"/, 'Shared date filters should preserve the archive date protocol')
assert.match(archive, /useListFilters/, 'Project archive should evaluate custom filters through the shared list filter composable')
assert.match(archive, /PmsQueryWorkspace/, 'Project archive should render all conditions through the shared query workspace')

for (const field of [
  'project_code',
  'project_name',
  'product_category',
  'manager_name',
  'equipment_series',
  'contract_signed_date',
  'contract_ship_date',
  'erp_sync_status',
]) {
  assert.match(archive, new RegExp(field), `Project archive custom filters should include ${field}`)
}
assert.doesNotMatch(archive,/plan_start_date|plan_end_date/,'Removed archive plan fields must not remain queryable')

assert.match(archive, /field:'is_enabled',shown:true,operator:'equals',value:1/, 'Enabled-state default belongs to shared three-part conditions')
assert.match(archive, /value:1,label:'启用'/, 'Enabled-state filter should include enabled records')
assert.match(archive, /value:0,label:'已禁用'/, 'Enabled-state filter should include disabled records')
assert.match(archive, /enabled: 'all'/, 'Backend enabled shortcut must not override shared query conditions')
const archiveFilterFields = archive.match(/const archiveFilterFields =[\s\S]*?useListFilters\(archiveFilterFields\)/)?.[0] || ''
assert.doesNotMatch(archiveFilterFields, /field:\s*'status'/, 'Project archive custom filters must not restore the legacy status field')

console.log('archive filter contract passed')
