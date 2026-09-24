import assert from 'node:assert/strict'
import { test } from 'node:test'
import { existsSync } from 'node:fs'
const file = new URL('../src/report-query/state.ts', import.meta.url)
test('shared report query state exists', () => assert.ok(existsSync(file)))
if (existsSync(file)) {
  const { createReportSession, validateConditions, operatorsFor } = await import(file.href)
  test('date and enumeration conditions use typed operators and validated values', () => {
    const fields = [{field:'date',label:'日期',type:'date'}, {field:'status',label:'状态',type:'enum',options:[{value:'approved',label:'已审核'}]}]
    const c = {id:1,field:'date',operator:'between',value:'2026-09-01',valueEnd:'2026-09-24'}
    assert.ok(!operatorsFor('date').includes('contains'))
    assert.equal(validateConditions([c], fields),'')
    assert.match(validateConditions([{...c,value:'2026-02-30'}],fields),/日期/)
    assert.match(validateConditions([{...c,value:'2026-10-01'}],fields),/顺序/)
    assert.equal(validateConditions([{...c,field:'status',operator:'equals',value:'approved'}],fields),'')
    assert.match(validateConditions([{...c,field:'status',operator:'equals',value:'missing'}],fields),/选项/)
  })
  test('draft and successful snapshot remain independent through failures and invalidation', () => {
    const s = createReportSession({ keyword: '', conditions: [] })
    assert.equal(s.applied, null)
    const first = s.begin()
    s.draft.keyword = 'new'
    assert.equal(s.accept(first), true)
    assert.equal(s.applied.keyword, '')
    assert.equal(s.dirty, true)
    const stale = s.begin()
    s.restore({ keyword: 'plan', conditions: [] })
    assert.equal(s.accept(stale), false)
    assert.equal(s.applied.keyword, '')
    const failed = s.begin()
    s.fail(failed)
    assert.equal(s.applied.keyword, '')
    const success = s.begin()
    s.accept(success)
    assert.equal(s.dirty, false)
    s.draft.conditions.push({ value: 'new' })
    assert.equal(s.applied.conditions.length, 0)
  })
  test('typed conditions reject missing values, reversed intervals, stale fields and operators', () => {
    const fields = [{ field:'qty', label:'数量', type:'number' }, {field:'name',label:'名称',type:'text'}]
    const c = { id:1, field:'qty', operator:'equals', value:0, valueEnd:null }
    assert.equal(validateConditions([c], fields), '')
    assert.match(validateConditions([{...c,value:null}], fields), /填写/)
    assert.equal(validateConditions([{...c,operator:'isEmpty',value:null}], fields), '')
    assert.match(validateConditions([{...c,operator:'between',value:2,valueEnd:1}], fields), /顺序/)
    assert.match(validateConditions([{...c,field:'removed'}], fields), /失效/)
    assert.match(validateConditions([{...c,operator:'contains'}], fields), /运算符/)
    assert.ok(!operatorsFor('number').includes('contains'))
    assert.match(validateConditions([null],fields), /无效/)
    assert.match(validateConditions([{...c,value:{}}],fields), /无效/)
  })
}
