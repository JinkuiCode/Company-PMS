import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const exists = (path) => existsSync(new URL(`../${path}`, import.meta.url))

assert.ok(exists('src/components/PmsDataList.vue'), 'PmsDataList should provide the standard list page shell')
assert.ok(exists('src/components/PmsListFilters.vue'), 'PmsListFilters should provide the standard filter area')
assert.ok(exists('src/composables/useListFilters.ts'), 'useListFilters should centralize list filter behavior')

const dataList = exists('src/components/PmsDataList.vue') ? read('src/components/PmsDataList.vue') : ''
const listFilters = exists('src/components/PmsListFilters.vue') ? read('src/components/PmsListFilters.vue') : ''
const filterComposable = exists('src/composables/useListFilters.ts') ? read('src/composables/useListFilters.ts') : ''

assert.match(dataList, /GridHorizontalScrollbar/, 'PmsDataList should own the shared visible grid scrollbar')
assert.match(dataList, /defineExpose\(\{\s*refreshScrollbar/, 'PmsDataList should expose refreshScrollbar for AG Grid events')
assert.match(listFilters, /添加筛选/, 'PmsListFilters should render the shared add-filter control')
assert.match(listFilters, /清空筛选/, 'PmsListFilters should render the shared clear-filter control')
assert.match(filterComposable, /matchesListFilter/, 'useListFilters should expose a shared filter matcher')
assert.match(filterComposable, /applyCustomFilters/, 'useListFilters should expose reusable custom filter application')

for (const path of [
  'src/views/project/ProjectArchive.vue',
  'src/views/project/ProjectList.vue',
  'src/views/project/ProjectProgress.vue',
]) {
  const source = read(path)
  assert.match(source, /PmsDataList/, `${path} should use the standard list shell`)
  assert.match(source, /PmsListFilters/, `${path} should use the standard filter component`)
  assert.match(source, /useListFilters/, `${path} should use the shared list filter behavior`)
}

const archive = read('src/views/project/ProjectArchive.vue')
assert.doesNotMatch(archive, /function matchesCustomFilter/, 'Project archive should not own custom filter matching')
assert.doesNotMatch(archive, /archive-custom-filters/, 'Project archive should not own custom filter layout styles')

console.log('list standard contract passed')
