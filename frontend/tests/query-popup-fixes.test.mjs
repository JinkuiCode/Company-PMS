import assert from 'node:assert/strict'
import { test } from 'node:test'
import { existsSync } from 'node:fs'
import * as navigation from '../src/page-guide/navigation.ts'
import { optionReference } from '../src/query-system/reference.ts'

test('one popup owns the group; disposing an old header cannot close the new popup', async () => {
  const file = new URL('../src/query-system/column-popup.ts', import.meta.url)
  assert.ok(existsSync(file), '缺少统一列筛选弹窗互斥管理')
  const { createColumnPopupGroup } = await import(file.href)
  const group = createColumnPopupGroup(), calls = []
  const a = Symbol(), b = Symbol()
  group.open(a, () => { calls.push('a'); group.release(a) })
  group.open(b, () => calls.push('b'))
  assert.deepEqual(calls, ['a'])
  group.release(a)
  group.open(a, () => calls.push('a2'))
  assert.deepEqual(calls, ['a', 'b'])
  group.release(a)
  group.open(b, () => calls.push('b2'))
  assert.deepEqual(calls, ['a', 'b'])
})

test('only the four static guide paths are public, not business or similar routes', () => {
  assert.equal(typeof navigation.isPublicGuidePath, 'function', '缺少静态说明页的精确访问边界')
  for (const key of ['archive', 'purchase', 'inventory', 'stock']) assert.equal(navigation.isPublicGuidePath(`/page-guide/${key}`), true)
  for (const path of ['/project/archive', '/reports/purchase-progress', '/page-guide', '/page-guide/unknown', '/page-guide/purchase/edit', '/page-guide/__proto__']) assert.equal(navigation.isPublicGuidePath(path), false)
})

test('product line references display and search names while IDs remain stable', async () => {
  for (const key of ['product_line_id', 'business_product_line_id', 'organization_id', 'organization_ids']) {
    const reference = optionReference('产品线', key, [{ value: 499413, label: '8吋Bench' }, { value: 100002, label: 'Single' }])
    assert.equal(reference.display, 'name', `${key}应隐藏编码`)
    assert.deepEqual((await reference.load({ keyword: 'Bench', page: 1, pageSize: 50 })).items.map(r => r.value), [499413])
    assert.equal((await reference.load({ keyword: '499413', page: 1, pageSize: 50 })).total, 0)
    assert.deepEqual((await reference.load({ ids: [499413], page: 1, pageSize: 50 })).items.map(r => r.value), [499413])
    assert.equal((await reference.load({ batch: { field: 'name', values: ['8吋Bench', 'Single'] }, page: 1, pageSize: 50 })).total, 2)
  }
  const ordinary = optionReference('设备系列', 'equipment_series', [{ value: '001', label: '设备A' }])
  assert.notEqual(ordinary.display, 'name')
  assert.equal((await ordinary.load({ keyword: '001', page: 1, pageSize: 50 })).total, 1)
})
