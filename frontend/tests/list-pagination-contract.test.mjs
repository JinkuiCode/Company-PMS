import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = p => readFileSync(new URL(`../src/${p}`, import.meta.url), 'utf8')
const archive = read('views/project/ProjectArchive.vue')
assert.match(archive, /page_size: pageSize.value/, 'Archive API must use the selected page size')
assert.match(archive, /page: page.value/, 'Archive API must use the current page')
assert.match(archive, /filters: JSON.stringify/, 'Custom filters must apply on the server before pagination')
assert.match(archive, /@sort-changed="handleArchiveSortChanged"/, 'Restored and interactive sort must update the server query')
assert.match(archive, /requestSerial !== archiveListRequestSerial/, 'An old query must never overwrite a newer query')
assert.match(archive, /const refreshed = await fetchArchiveLifecycleSnapshot\(archiveId\)/, 'Saved drawer state must not come from a stale or superseded list request')
assert.doesNotMatch(archive, /page_size: (1000|10000)/, 'No whole-table requests for the list or drawer snapshot')
assert.match(read('styles/pms-theme.css'), /\.ag-cell-wrapper[\s\S]*?min-width: 0/, 'Text wrappers must shrink to the column')
const progress = read('views/project/ProjectList.vue')
assert.match(progress, /:pagination="true"/, 'Progress must sort the complete filtered dataset before grid pagination')
assert.match(progress, /all_rows: true/, 'Client-side filtering must use one complete result, not shifting offset chunks')
for (const file of ['views/system/UserList.vue', 'views/system/DataDictionaryList.vue']) {
  assert.match(read(file), /requestSerial !== listRequestSerial/, `${file}: old responses must not overwrite newer page/filter requests`)
}
console.log('list pagination contract passed')
