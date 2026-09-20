import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
const archive = readFileSync('src/views/project/ProjectArchive.vue', 'utf8')
assert.ok(!archive.includes('批量同步 ERP'))
assert.ok(!archive.includes('保存并同步 ERP'))
assert.ok(!archive.includes("request.post('/erp/sync'"))
assert.ok(archive.includes('SyncLogDrawer'))
assert.ok(archive.includes('ARCHIVE_CODE_LOCKED') || archive.includes('kingdee_initial'))
const page = readFileSync('src/views/system/SyncTaskList.vue', 'utf8')
assert.ok(page.includes('PmsDataList') && page.includes('CustomPagination'))
assert.ok(page.includes('system:sync:retry'))
assert.ok(page.includes('PmsDateControl') && page.includes('PmsSelectControl'))
assert.ok(readFileSync('src/router/index.ts', 'utf8').includes('system:sync:view'))
console.log('archive auto-sync UI contract passed')
