import assert from 'node:assert/strict'
import { test } from 'node:test'
import { existsSync } from 'node:fs'

const source = new URL('../src/views/reports/stockDetailState.ts', import.meta.url)
test('stock-detail state module exists', () => assert.ok(existsSync(source)))
if (existsSync(source)) {
  const { buildStockDetailQuery, createStockDetailRequest } = await import(source.href)
  const filters = { material: ' PFA ', dates: ['2026-06-01', '2026-09-23'], organization_id: 1, stock_id: null }
  test('organization is required even for a saved plan without selection', () => {
    assert.throws(() => buildStockDetailQuery({ ...filters, organization_id: null }, 1, 50), /组织/)
    assert.throws(() => buildStockDetailQuery({ ...filters, organization_id: null, organization_ids: [] }, 1, 50), /组织/)
  })
  test('multiple organizations and legacy saved plans share a normalized query', () => {
    assert.deepEqual(buildStockDetailQuery({ ...filters, organization_id: null, organization_ids: [2, 1, 2] }, 1, 50).organization_ids, [1, 2])
    assert.deepEqual(buildStockDetailQuery({ ...filters, organization_id: 3 }, 1, 50).organization_ids, [3])
    assert.throws(() => buildStockDetailQuery({ ...filters, organization_ids: [0] }, 1, 50))
  })
  test('blank material and invalid dates fail before network access including restored plans', () => {
    for (const change of [{ material: '　 ' }, { dates: [] }, { dates: ['2026-09-23', '2026-06-01'] },
      { dates: ['2026-02-30', '2026-03-01'] }, { stock_id: '研发仓' }, { organization_id: -1 }]) {
      assert.throws(() => buildStockDetailQuery({ ...filters, ...change }, 1, 50))
    }
    assert.equal(buildStockDetailQuery(filters, 1, 50).material, 'PFA')
  })
  test('invalid request clears previous results without invoking loader', async () => {
    let calls = 0
    const state = createStockDetailRequest(async () => { calls++; return { items: [{ row_id: 'a' }], openings: [], total: 1 } })
    await state.query(filters, 1, 50)
    await state.query({ ...filters, material: '' }, 1, 50)
    assert.equal(calls, 1)
    assert.equal(state.value.items.length, 0)
    assert.equal(state.value.total, 0)
    assert.match(state.value.error, /物料/)
  })
  test('late response and failure never replace newer request results', async () => {
    let resolve, signal
    const wait = new Promise(r => { resolve = r })
    const state = createStockDetailRequest((params, s) => {
      if (params.material === 'PFA') { signal = s; return wait }
      return Promise.resolve({ items: [{ row_id: 'b' }], openings: [], total: 1 })
    })
    const first = state.query(filters, 1, 50)
    await state.query({ ...filters, material: 'B' }, 1, 50)
    assert.equal(signal.aborted, true)
    resolve({ items: [{ row_id: 'a' }], openings: [], total: 1 })
    await first
    assert.equal(state.value.items[0].row_id, 'b')
    assert.equal(state.value.loading, false)
  })
  test('closing page aborts request and cannot apply its response', async () => {
    let resolve, signal
    const state = createStockDetailRequest((p, s) => { signal = s; return new Promise(r => { resolve = r }) })
    const request = state.query(filters, 1, 50)
    state.clear()
    resolve({ items: [{ row_id: 'a' }], openings: [], total: 1 })
    await request
    assert.equal(signal.aborted, true)
    assert.equal(state.value.items.length, 0)
    assert.equal(state.value.loading, false)
  })
}
