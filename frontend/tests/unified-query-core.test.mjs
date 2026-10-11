import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
const file = new URL('../src/query-system/core.ts', import.meta.url)
assert.ok(existsSync(file), '统一查询协议应作为独立模块存在')
const { operatorsFor, operatorLabel, validateConditions, adaptConditions, hasConditionValue, matchesConditions } = await import(file.href)
const fields = [
  { field:'name', label:'名称', type:'text' }, { field:'qty', label:'数量', type:'number' },
  { field:'date', label:'日期', type:'date' },
  { field:'line', label:'产品线', type:'enum', options:[{value:1,label:'Bench'},{value:2,label:'Single'}] },
]
const condition = (field, operator, value, valueEnd=null) => ({id:1,field,operator,value,valueEnd,schemaVersion:2})
assert.deepEqual(operatorsFor('enum'), ['equals','notEquals','in','notIn','isEmpty','notEmpty'])
assert.equal(operatorLabel('lessOrEqual','date'), '不晚于')
assert.equal(operatorLabel('startsWith','text'), '左包含')
assert.deepEqual(validateConditions([condition('line','in',[1,2])],fields), {})
assert.ok(validateConditions([condition('line','in',[])],fields)[1])
assert.ok(validateConditions([condition('line','in',[3])],fields)[1])
assert.deepEqual(validateConditions([condition('qty','equals',0)],fields), {})
assert.ok(hasConditionValue(condition('qty','equals',0)))
assert.ok(hasConditionValue(condition('qty','isEmpty',null)))
assert.ok(!hasConditionValue(condition('line','in',[])))
for (const c of [condition('qty','between',2,1),condition('date','equals','2026-02-30'),condition('name','equals',12),condition('missing','equals','x'),condition('qty','contains',1)]) {
  assert.ok(Object.keys(validateConditions([c],fields)).length)
}
const old = [{id:9,field:'name',operator:'notEquals',value:'x',valueEnd:''}, {id:10,field:'date',operator:'before',value:'2026-10-10'}]
const adapted = adaptConditions(old)
assert.equal(adapted[0].schemaVersion,1, '旧否定比较不得无标记改为新语义')
assert.equal(adapted[1].operator,'before', '旧日期保留协议以沿用日期边界')
assert.equal(old[0].schemaVersion,undefined, '适配不得修改存储内容')
assert.deepEqual(validateConditions(adapted,fields),{})
assert.ok(Object.keys(validateConditions([{...condition('name','equals','x'),schemaVersion:999}],fields)).length)
assert.equal(matchesConditions({name:null},[condition('name','notEquals','x')],fields),false)
assert.equal(matchesConditions({qty:0},[condition('qty','isEmpty',null)],fields),false)
assert.equal(matchesConditions({line:2},[condition('line','in',[1,2])],fields),true)
assert.equal(matchesConditions({name:'%_test'},[condition('name','startsWith','%_')],fields),true)
console.log('unified query core passed: typed rules, zero/null, membership, invalid input, legacy versions')
