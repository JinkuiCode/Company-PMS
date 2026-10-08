import assert from 'node:assert/strict'
import { test } from 'node:test'
import { existsSync } from 'node:fs'
const file = new URL('../src/views/reports/purchaseQuickFilter.ts', import.meta.url)
test('purchase quick filters share the canonical query conditions', () => assert.ok(existsSync(file)))
if (existsSync(file)) {
  const { selectedPurchaseProgress, withPurchaseProgress, restorePurchaseProgress } = await import(file.href)
  const c = (field, value, operator = 'equals', id = 1) => ({ id, field, operator, value, valueEnd: null })
  const values = ['not_ordered', 'ordering', 'receiving', 'complete', 'review']
  test('only a single supported equals condition is selected, all other combinations are custom', () => {
    assert.equal(selectedPurchaseProgress([], values), '')
    assert.equal(selectedPurchaseProgress([c('progress', 'ordering')], values), 'ordering')
    assert.equal(selectedPurchaseProgress([c('progress', 'ordering', 'notEquals')], values), 'custom')
    assert.equal(selectedPurchaseProgress([c('progress', 'removed')], values), 'custom')
    assert.equal(selectedPurchaseProgress([c('progress', 'ordering'), c('progress', 'receiving')], values), 'custom')
  })
  test('choosing a shortcut replaces all progress conditions and preserves other fields without mutation', () => {
    const other = c('requested', 5, 'greaterThan', 10)
    const old = [other, c('progress', 'ordering'), c('progress', 'review', 'notEquals', 3)]
    const next = withPurchaseProgress(old, 'complete')
    assert.deepEqual(next.slice(0, 1), [other])
    assert.deepEqual(next[1], c('progress', 'complete', 'equals', 11))
    assert.equal(old.length, 3)
    assert.deepEqual(withPurchaseProgress(old, ''), [other])
  })
  test('restoring legacy plans never creates conflicting duplicate progress conditions', () => {
    const canonical = [c('progress', 'complete')]
    assert.deepEqual(restorePurchaseProgress(canonical, 'ordering'), canonical)
    assert.deepEqual(restorePurchaseProgress([], 'ordering'), [c('progress', 'ordering')])
    assert.deepEqual(restorePurchaseProgress([], ''), [])
  })
}
