import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { test } from 'node:test'
const path = new URL('./model.mjs', import.meta.url)
test('shared prototype query model exists', () => assert.ok(existsSync(path)))
if (existsSync(path)) {
  const { operators, matches, validate, createSession } = await import(path.href)
  test('operators follow type and preserve null versus numeric zero', () => {
    assert.ok(operators('text').includes('contains'))
    assert.ok(!operators('number').includes('contains'))
    assert.equal(matches(null, 'empty', ''), true)
    assert.equal(matches(0, 'empty', ''), false)
    assert.equal(matches(null, 'eq', 0), false)
    assert.equal(matches(0, 'eq', 0), true)
    assert.equal(matches('PFA管', 'starts', 'PFA'), true)
  })
  test('required input and invalid ranges are rejected', () => {
    assert.ok(validate('stock', { material: '', organizations: [], dates: [], conditions: [] }))
    assert.ok(validate('inventory', { conditions: [{ field: 'qty', type: 'number', op: 'between', value: 9, end: 1 }] }))
    assert.equal(validate('stock', { material: 'PFA', organizations: [1], dates: ['2026-09-01', '2026-09-24'], conditions: [] }), '')
  })
  test('draft changes, reset and plans do not query or overwrite applied conditions', () => {
    const session = createSession({ material: 'PFA' })
    assert.equal(session.applied, null)
    session.apply()
    session.draft.material = '阀'
    assert.equal(session.applied.material, 'PFA')
    assert.equal(session.dirty, true)
    session.restore({ material: '' })
    assert.equal(session.applied.material, 'PFA')
    session.apply()
    assert.equal(session.applied.material, '')
  })
}
