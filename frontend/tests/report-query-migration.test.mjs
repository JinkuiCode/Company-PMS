import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
test('all report pages adopt approved surface and Chinese-only column headers',()=>{
  for(const file of ['InventoryList','PurchaseProgressList','StockDetailList']) {
    const source=readFileSync(new URL(`../src/views/reports/${file}.vue`,import.meta.url),'utf8')
    assert.ok(source.includes('pms-report-query-surface'),file)
    assert.ok(source.includes('PmsReportConditions') || source.includes('PmsReportQueryBar'),file)
    assert.ok(!source.includes('headerTooltip: field.description'),file)
    assert.ok(!source.includes('headerTooltip: `${field.key}'),file)
  }
})
