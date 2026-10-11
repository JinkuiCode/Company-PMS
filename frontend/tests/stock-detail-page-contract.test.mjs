import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { test } from 'node:test'

const path = new URL('../src/views/reports/StockDetailList.vue', import.meta.url)
test('formal quantity report uses standard list, form, layout and detail modules', () => {
  assert.ok(existsSync(path), 'formal report page not implemented')
  const source = readFileSync(path, 'utf8')
  for (const name of ['PmsDataList', 'PmsQueryWorkspace', 'PmsListColumnPicker', 'CustomPagination',
    'PmsFormDrawer', 'createDetailSwitch', 'createReportRequest']) assert.ok(source.includes(name), name)
  assert.ok(!source.includes('allow-create'))
  assert.ok(source.includes('pinned-top-row-data'))
  assert.ok(source.includes(':legacy-schemes="legacyReportSchemes"'))
  assert.ok(!source.includes('savePlan'))
  assert.ok(!source.includes('loadPlan'))
  assert.ok(!source.includes('FPRICE'))
  assert.ok(!source.includes('FAMOUNT'))
  assert.ok(source.includes('ReportExportControl'))
  assert.ok(source.includes("auth.hasPermission('report:stock-detail:export')"))
  for (const expected of ['pms-report-query-surface', ':before-export="beforeExport"', 'metadata.value?.filter_fields', "operators: ['reference']", 'column_filters']) assert.ok(source.includes(expected), expected)
  assert.ok(!source.includes('watch(filters,'), 'editing filters must not clear data')
})
