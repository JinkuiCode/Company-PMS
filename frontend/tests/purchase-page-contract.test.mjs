import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
const root = resolve(import.meta.dirname, '..')
const page = resolve(root, 'src/views/reports/PurchaseProgressList.vue')
assert.ok(existsSync(page), 'The approved report must have a real application page')
const source = readFileSync(page, 'utf8')
for (const component of ['PmsDataList', 'PmsListFilters', 'PmsListColumnPicker', 'CustomPagination']) assert.ok(source.includes(component))
assert.match(source, /createPurchaseDetailState/)
assert.match(source, /selectRow/)
assert.match(source, /reconcileRows/)
assert.match(source, /report:purchase:export/)
assert.match(source, /auth\.user\?\.id/)
assert.doesNotMatch(source, /<el-(input|select|date-picker)\b/)
assert.match(readFileSync(resolve(root, 'src/router/index.ts'), 'utf8'), /report:purchase:view/)
assert.match(readFileSync(resolve(root, 'src/utils/request.ts'), 'utf8'), /axios\.isCancel/)
console.log('purchase page integration contracts passed')
