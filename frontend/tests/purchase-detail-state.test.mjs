import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createPurchaseDetailState } from '../src/views/reports/purchaseDetailState.ts'

function deferred() {
  let resolve, reject
  const promise = new Promise((a, b) => { resolve = a; reject = b })
  return { promise, resolve, reject }
}

test('changing selected application resets order filter and discards old responses', async () => {
  const first = deferred(), second = deferred()
  const controller = createPurchaseDetailState(id => id === 'A' ? first.promise : second.promise)
  const a = controller.open('A')
  controller.selectOrder('order-A')
  const b = controller.selectRow('B')
  assert.equal(controller.state.requestId, 'B')
  assert.equal(controller.state.orderId, null)
  assert.equal(controller.state.data, null)
  second.resolve({ requestId: 'B', orders: [] })
  await b
  first.resolve({ requestId: 'A', orders: [] })
  await a
  assert.equal(controller.state.data.requestId, 'B')
  assert.equal(controller.state.loading, false)
})

test('selecting a row before opening does not fetch or open the drawer', async () => {
  let calls = 0
  const controller = createPurchaseDetailState(async () => { calls++; return {} })
  await controller.selectRow('A')
  assert.equal(calls, 0)
  assert.equal(controller.state.open, false)
})

test('closing clears selection and aborts pending work without reopening', async () => {
  const wait = deferred()
  let signal
  const controller = createPurchaseDetailState((id, input) => { signal = input; return wait.promise })
  const pending = controller.open('A')
  controller.close()
  assert.equal(signal.aborted, true)
  wait.resolve({ requestId: 'A' })
  await pending
  assert.equal(controller.state.open, false)
  assert.equal(controller.state.data, null)
})

test('old rejection cannot replace the next row with an error', async () => {
  const wait = deferred()
  const controller = createPurchaseDetailState(id => id === 'A' ? wait.promise : Promise.resolve({ requestId: id }))
  const a = controller.open('A')
  await controller.selectRow('B')
  wait.reject(new Error('raw database connection details'))
  await a
  assert.equal(controller.state.error, null)
  assert.equal(controller.state.data.requestId, 'B')
})

test('active errors are safe, retryable, and never display stale data', async () => {
  let fail = true
  const controller = createPurchaseDetailState(async id => {
    if (fail) throw new Error('password=do-not-show')
    return { requestId: id }
  })
  await controller.open('A')
  assert.equal(controller.state.data, null)
  assert.equal(controller.state.loading, false)
  assert.equal(controller.state.error, '明细加载失败，请重试')
  fail = false
  await controller.retry()
  assert.equal(controller.state.error, null)
  assert.equal(controller.state.data.requestId, 'A')
})

test('page or filter removal closes stale detail; retained row stays selected', async () => {
  const controller = createPurchaseDetailState(async id => ({ requestId: id }))
  await controller.open('A')
  controller.reconcileRows(['A', 'B'])
  assert.equal(controller.state.open, true)
  controller.reconcileRows(['B'])
  assert.equal(controller.state.open, false)
  assert.equal(controller.state.requestId, null)
})
