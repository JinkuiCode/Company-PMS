import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const archive = readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')
const listFilters = readFileSync(new URL('../src/components/PmsListFilters.vue', import.meta.url), 'utf8')

assert.match(archive, /archiveFilterFields/, 'Project archive should define configurable filter fields')
assert.match(archive, /customFilters/, 'Project archive should store user-added custom filters')
assert.match(listFilters, /添加筛选/, 'Shared list filter component should expose an add-filter control')
assert.match(listFilters, /清空筛选/, 'Shared list filter component should expose a clear custom filters control')
assert.match(archive, /useListFilters/, 'Project archive should evaluate custom filters through the shared list filter composable')
assert.match(archive, /PmsListFilters/, 'Project archive should render custom filters through the shared filter component')

for (const field of [
  'project_code',
  'project_name',
  'product_category',
  'status',
  'manager_name',
  'equipment_series',
  'plan_start_date',
  'plan_end_date',
  'erp_sync_status',
]) {
  assert.match(archive, new RegExp(field), `Project archive custom filters should include ${field}`)
}

console.log('archive filter contract passed')
