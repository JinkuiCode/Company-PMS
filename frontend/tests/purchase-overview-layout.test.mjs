import assert from 'node:assert/strict'
import { test } from 'node:test'
import { existsSync } from 'node:fs'
const moduleUrl = new URL('../src/views/reports/purchase-overview-layout.ts', import.meta.url)
test('overview layout migration exists', () => assert.ok(existsSync(moduleUrl)))
if (existsSync(moduleUrl)) {
  const { migrateOverviewLayout } = await import(moduleUrl.href)
  test('old layout gains first product line and conversion while keeping user widths and sort', () => {
    const input = { visible: ['project_code', 'completion_rate', 'total_lines'], pageSize: 100,
      columns: [{ colId: 'project_code', width: 144 }, { colId: 'completion_rate', width: 181, sort: 'desc' }, { colId: 'product_line_name', hide: true, width: 137, pinned: 'right' }, { colId: 'total_lines', width: 98 }] }
    const before = structuredClone(input), next = migrateOverviewLayout(input)
    assert.deepEqual(input, before)
    assert.deepEqual(next.visible, ['product_line_name', 'project_code', 'completion_rate', 'conversion_rate', 'total_lines'])
    assert.equal(next.columns[0].colId, 'product_line_name')
    assert.deepEqual(next.columns[0], { colId: 'product_line_name', width: 137, hide: false, pinned: 'left' })
    assert.equal(next.columns.find(c => c.colId === 'completion_rate').sort, 'desc')
    assert.equal(next.columns.find(c => c.colId === 'completion_rate').width, 181)
    assert.equal(next.columns.find(c => c.colId === 'conversion_rate').sort, null)
    assert.equal(next.columns.find(c => c.colId === 'conversion_rate').sortIndex, null)
    assert.equal(next.pageSize, 100)
    assert.deepEqual(migrateOverviewLayout(next), next)
  })
  test('new saved choices remain authoritative and empty default layouts do not invent a partial order', () => {
    const saved = { metricLayoutVersion: 1, visible: ['project_code'], columns: [{ colId: 'project_code', width: 170 }] }
    assert.deepEqual(migrateOverviewLayout(saved), saved)
    const empty = migrateOverviewLayout({})
    assert.equal(empty.visible, undefined)
    assert.equal(empty.columns, undefined)
    assert.equal(empty.metricLayoutVersion, 1)
  })
}
