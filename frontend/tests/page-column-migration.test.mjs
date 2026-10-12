import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
const read = path => readFileSync(new URL(`../src/${path}`,import.meta.url),'utf8')
test('server-paged lists use shared local page filtering, not server column candidates', () => {
  for (const path of ['project/ProjectArchive','reports/PurchaseOverviewList','reports/PurchaseProgressList','reports/InventoryList','reports/StockDetailList','system/OperationLogList','system/SyncTaskList']) {
    const source=read(`views/${path}.vue`)
    assert.match(source,/usePageColumnFilter/,path)
    assert.doesNotMatch(source,/reportColumnCandidates\(|request\.get\([^\n]*column-values/,path)
    assert.doesNotMatch(source,/column_filters:\s*serializeColumnFilters\(columnFilters.value\)/,`${path} must not send local filters to SQL`)
  }
})
test('popup uses compact shared button styles and current-page scope', () => {
  const source=read('query-system/PmsQueryColumnHeader.vue')
  assert.match(source,/仅筛选当前页/)
  assert.doesNotMatch(source,/本次查询全部结果/)
  assert.match(source,/pms-button-auxiliary/)
  assert.match(source,/pms-button-dismiss/)
})
test('report scheme changes close active popup and discard its old draft', () => {
  for (const name of ['PurchaseOverviewList','PurchaseProgressList','InventoryList','StockDetailList']) {
    const source = read(`views/reports/${name}.vue`)
    assert.match(source, /function clearColumnFilters\(\) \{ pageColumns\.clear\(\)/, name)
  }
})
