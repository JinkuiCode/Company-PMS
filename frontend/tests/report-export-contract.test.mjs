import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const component = readFileSync(new URL('../src/components/ReportExportControl.vue', import.meta.url), 'utf8')
for (const word of ['createReportExport', 'listReportExports', 'downloadReportExport', 'onUnmounted', 'processed', '导出任务']) assert.ok(component.includes(word), word)
assert.ok(!component.includes(':loading="busy"'))
for (const name of ['InventoryList', 'PurchaseProgressList']) {
  const source = readFileSync(new URL(`../src/views/reports/${name}.vue`, import.meta.url), 'utf8')
  assert.ok(source.includes('<ReportExportControl'))
  assert.ok(!source.includes('export_limit'))
  assert.ok(source.includes('getAllDisplayedColumns'))
}
console.log('report export UI contract passed')
