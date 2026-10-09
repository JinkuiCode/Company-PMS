import assert from 'node:assert/strict'
import { test } from 'node:test'
import { existsSync } from 'node:fs'

const source = new URL('../src/views/reports/stockDetailState.ts', import.meta.url)
test('stock-detail state module exists', () => assert.ok(existsSync(source)))
if (existsSync(source)) {
  const { buildStockDetailQuery, createStockDetailRequest, formatStockQuantity } = await import(source.href)
  test('quantities have two decimals, hide rounded zero and preserve decimal rounding', () => {
    assert.equal(typeof formatStockQuantity, 'function')
    for (const [value, expected] of [['6', '6.00'], ['1.005', '1.01'], ['-1.005', '-1.01'],
      ['0', ''], ['-0.004', ''], ['0.0049', ''], ['0.005', '0.01'],
      ['1234567890123456.125', '1234567890123456.13'], [null, ''], [undefined, ''], ['', '']]) {
      assert.equal(formatStockQuantity(value), expected)
    }
  })
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
  test('invalid request preserves previous results without invoking loader', async () => {
    let calls = 0
    const state = createStockDetailRequest(async () => { calls++; return { items: [{ row_id: 'a' }], openings: [], total: 1 } })
    await state.query(filters, 1, 50)
    await state.query({ ...filters, material: '' }, 1, 50)
    assert.equal(calls, 1)
    assert.equal(state.value.items.length, 1)
    assert.equal(state.value.total, 1)
    assert.match(state.value.error, /物料/)
  })
  test('conditions serialize, successful snapshots are isolated and retry keeps failed parameters', async () => {
    const calls = []
    let fail = false
    const state = createStockDetailRequest(async p => {
      calls.push(structuredClone(p))
      if (fail) throw Error('offline')
      return { items: [{ row_id: p.material }], openings: [], total: 1 }
    })
    const draft = { ...filters, conditions: [{ id: 1, field: 'bill_no', operator: 'contains', value: 'DOC', valueEnd: null }] }
    await state.query(draft, 1, 50)
    assert.deepEqual(JSON.parse(calls[0].filters), [{ field: 'bill_no', operator: 'contains', value: 'DOC', valueEnd: null }])
    draft.conditions[0].value = 'NEW'
    assert.equal(JSON.parse(state.value.applied.filters)[0].value, 'DOC')
    fail = true
    await state.query({ ...draft, material: 'FAILED' }, 2, 20)
    assert.equal(state.value.items[0].row_id, 'PFA')
    assert.equal(state.value.applied.material, 'PFA')
    draft.material = 'EDITED'
    fail = false
    await state.retry()
    assert.equal(calls.at(-1).material, 'FAILED')
    assert.equal(calls.at(-1).page, 2)
    assert.equal(state.value.applied.material, 'FAILED')
    await state.paginate(3, 20)
    assert.equal(calls.at(-1).material, 'FAILED')
    assert.equal(calls.at(-1).page, 3)
    state.clear()
    assert.equal(state.value.applied, null)
    await state.retry()
    await state.paginate(1, 50)
    assert.equal(calls.length, 4)
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
  test('a later success without summary clears the previous summary', async () => {
    const state = createStockDetailRequest(async p => ({ items: [], openings: [], total: 0,
      ...(p.material === 'PFA' ? { summary: { income_qty: '9' } } : {}) }))
    await state.query(filters, 1, 50)
    assert.equal(state.value.summary.income_qty, '9')
    await state.query({ ...filters, material: 'B' }, 1, 50)
    assert.equal(state.value.summary, null)
  })
  test('late rejection cannot replace a newer successful snapshot or create a retry', async () => {
    let reject
    const calls = []
    const state = createStockDetailRequest(p => {
      calls.push(p.material)
      if (p.material === 'PFA') return new Promise((_, fail) => { reject = fail })
      return Promise.resolve({ items: [{ row_id: 'new' }], openings: [], total: 1 })
    })
    const stale = state.query(filters, 1, 50)
    await state.query({ ...filters, material: 'B' }, 1, 50)
    reject(Error('old'))
    await stale
    await state.retry()
    assert.equal(state.value.error, '')
    assert.equal(state.value.applied.material, 'B')
    assert.deepEqual(calls, ['PFA', 'B'])
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
  test('plan restore invalidates in-flight results without losing the successful page', async () => {
    let resolve, signal
    const state = createStockDetailRequest((p, s) => {
      if (p.material === 'B') { signal = s; return new Promise(done => { resolve = done }) }
      return Promise.resolve({ items: [{ row_id: 'accepted' }], openings: [], total: 70 })
    })
    await state.query(filters, 2, 50)
    const pending = state.query({ ...filters, material: 'B' }, 1, 20)
    assert.equal(typeof state.invalidate, 'function')
    state.invalidate()
    assert.equal(signal.aborted, true)
    assert.equal(state.value.loading, false)
    resolve({ items: [{ row_id: 'stale' }], openings: [], total: 1 })
    await pending
    assert.equal(state.value.items[0].row_id, 'accepted')
    assert.equal(state.value.applied.page, 2)
    assert.equal(state.value.applied.page_size, 50)
    assert.equal(state.value.error, '')
  })
  test('failed page size change preserves accepted pagination until retry succeeds', async () => {
    let fail = false
    const state = createStockDetailRequest(async () => {
      if (fail) throw Error('offline')
      return { items: [{ row_id: 'accepted' }], openings: [], total: 70 }
    })
    await state.query(filters, 2, 50)
    fail = true
    await state.paginate(1, 20)
    assert.equal(state.retryKind, 'page')
    assert.equal(state.value.applied.page, 2)
    assert.equal(state.value.applied.page_size, 50)
    fail = false
    await state.retry()
    assert.equal(state.value.applied.page, 1)
    assert.equal(state.value.applied.page_size, 20)
    assert.equal(state.retryKind, null)
  })
  test('submit retry retains its kind on failure and clears it only on success or invalidation', async () => {
    let fail = true
    const state = createStockDetailRequest(async () => {
      if (fail) throw Error('offline')
      return { items: [], openings: [], total: 0 }
    })
    await state.query(filters, 1, 100)
    assert.equal(state.retryKind, 'submit')
    assert.equal(await state.retry(), false)
    assert.equal(state.retryKind, 'submit')
    fail = false
    assert.equal(await state.retry(), true)
    assert.equal(state.retryKind, null)
    fail = true
    await state.query(filters, 1, 100)
    state.invalidate()
    assert.equal(state.retryKind, null)
  })
}
