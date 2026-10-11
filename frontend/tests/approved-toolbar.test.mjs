import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = name => readFileSync(new URL('../src/' + name, import.meta.url), 'utf8')
const theme = read('styles/pms-theme.css')
for (const cls of ['pms-button-auxiliary', 'pms-button-export', 'pms-button-dismiss', 'pms-query-utilities']) assert.ok(theme.includes(cls), cls)
const row = read('query-system/PmsQueryConditionRow.vue')
assert.ok(!row.includes(':icon="Delete"'), 'Condition removal is a frameless cross, not a red delete action')
assert.ok(row.includes('reference-summary'), 'Reference values must use a bounded readable summary')
const workspace = read('query-system/PmsQueryWorkspace.vue')
assert.ok(!workspace.includes('type="warning"'), 'Reset/cancel use approved quiet auxiliary style')
for (const page of ['InventoryList', 'StockDetailList']) {
  const source = read('views/reports/' + page + '.vue')
  assert.ok(!source.includes('template #toolbar-right'), page + ': no empty business-action row')
  assert.ok(source.includes('template #after'), page + ': utilities are in the scheme row')
}
const parameters=read('views/system/ParameterList.vue')
assert.ok(parameters.includes("row.value_type === 'boolean'"),'Initialization parameter uses a choice, not free text')
const archive=read('views/project/ProjectArchive.vue')
assert.ok(archive.includes('BusinessExportControl'),'Archive exposes an independently authorized export')
assert.ok(archive.includes('businessExportSnapshot(archiveAppliedFilters.value'),'Archive exports submitted conditions, not drafts')
console.log('approved toolbar contract passed')
