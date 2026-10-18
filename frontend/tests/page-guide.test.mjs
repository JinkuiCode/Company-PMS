import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { test } from 'node:test'

const registryFile = new URL('../src/page-guide/registry.ts', import.meta.url)
assert.ok(existsSync(registryFile), '需要独立的正式页面说明目录，不能依赖样稿数据')
const { pageGuides, findGuideEntries } = await import(registryFile.href)
const { migrateReportIdentity } = await import('../src/views/reports/report-identity-layout.ts')

test('approved business surfaces share searchable operation and field instructions', () => {
  assert.deepEqual(Object.keys(pageGuides).sort(), ['archive', 'archiveChanges', 'archiveDrafts', 'audit', 'feedback', 'inventory', 'progress', 'purchase', 'stock', 'tasks', 'users'])
  for (const guide of Object.values(pageGuides)) {
    assert.ok(guide.title && guide.operations.length && guide.fields.length)
    assert.equal(new Set(guide.fields.map(item => item.label)).size, guide.fields.length)
    assert.deepEqual(findGuideEntries(guide, 'fields', '不存在的说明'), [])
  }
  assert.ok(findGuideEntries(pageGuides.purchase, 'fields', '  转单率 ').some(entry => /部分下单不计/.test(entry.logic)))
  assert.ok(findGuideEntries(pageGuides.stock, 'fields', 'NULL').some(entry => /0/.test(entry.logic)))
  assert.ok(!pageGuides.inventory.fields.some(entry => entry.label === '组织'))
  assert.ok(pageGuides.archive.fields.some(entry => entry.label === '项目名称'))
  assert.ok(!pageGuides.archive.fields.some(entry=>entry.label.includes('计划开始')))
  assert.ok(findGuideEntries(pageGuides.archive,'operations','审批').some(entry=>entry.logic.includes('审批前正式档案保持不变')))
  for (const label of ['请购组织','关闭状态','订单数据状态','入库数据状态','待下单数量','待入库数量','申请单行号','累计退料数量','累计净入库数量']) {
    assert.ok(pageGuides.purchase.fields.some(entry=>entry.label.includes(label)), `采购字段说明应覆盖${label}`)
  }
})

test('department instructions cover cross-department leaders without granting user access', () => {
  assert.ok(findGuideEntries(pageGuides.users, 'operations', '跨部门兼任').some(item => /多个部门/.test(item.logic)))
  assert.ok(findGuideEntries(pageGuides.users, 'fields', '部门负责人').some(item => /启用.*用户/.test(item.logic)))
})

test('identity migration puts product line first, drops obsolete report columns and preserves widths', () => {
  const input = { visible: ['project_name', 'project_code', 'Organization', 'product_line_name'], columns: [
    { colId: 'project_name', width: 190 }, { colId: 'project_code', width: 133, sort: 'asc' },
    { colId: 'Organization', width: 178 }, { colId: 'product_line_name', width: 155, hide: true },
  ], pageSize: 100 }
  const copy = structuredClone(input)
  const result = migrateReportIdentity(input, ['project_name', 'Organization'])
  assert.deepEqual(input, copy)
  assert.deepEqual(result.visible, ['product_line_name', 'project_code'])
  assert.equal(result.columns[0].colId, 'product_line_name')
  assert.equal(result.columns[0].width, 155)
  assert.equal(result.columns[0].pinned, 'left')
  assert.equal(result.columns[0].hide, false)
  assert.equal(result.columns[1].width, 133)
  assert.equal(result.columns[1].sort, 'asc')
  assert.equal(result.pageSize, 100)
  assert.deepEqual(migrateReportIdentity(result, ['project_name', 'Organization']), result)
})

test('new saved personal choices remain authoritative and stale hidden/sort columns are removed', () => {
  const current = { reportIdentityVersion: 1, visible: ['Stock'], columns: [{ colId: 'Stock', width: 180 }], sort: { sort: 'Organization', direction: 'desc' } }
  const result = migrateReportIdentity(current, ['Organization'])
  assert.deepEqual(result.visible, ['Stock'])
  assert.deepEqual(result.columns, current.columns)
  assert.equal(result.sort, undefined)
  assert.equal(migrateReportIdentity({}).visible, undefined)
  assert.equal(migrateReportIdentity({}).columns, undefined)
})
