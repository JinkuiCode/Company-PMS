import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
const file='src/views/reports/InventoryList.vue'
assert.ok(existsSync(file),'库存正式页面尚未实现')
const source=readFileSync(file,'utf8')
for(const component of ['PmsDataList','PmsListFilters','PmsListColumnPicker','CustomPagination','PmsTextControl','PmsSelectControl'])assert.ok(source.includes(component),component)
for(const code of ['report:inventory:export','DEFAULT_PAGE_SIZE','AbortController','current !== revision','getInventoryMetadata','getInventoryRows'])assert.ok(source.includes(code),code)
assert.ok(!source.includes('el-input'))
assert.ok(readFileSync('src/router/index.ts','utf8').includes('report:inventory:view'))
console.log('inventory report UI contract passed')
