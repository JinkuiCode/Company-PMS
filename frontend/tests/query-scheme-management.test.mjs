import assert from 'node:assert/strict'
import {test} from 'node:test'
import * as workspace from '../src/query-system/workspace.ts'

const fields=[{field:'code',label:'编码',type:'text'}]
const scheme=(name,value='X',isDefault=false)=>({version:2,name,isDefault,definitions:[{field:'code',shown:true,operator:'equals',value,valueEnd:null,schemaVersion:2}],preferences:{visible:['material_code'],purchaseMaterialLayoutVersion:1,pageSize:100}})
const key=workspace.schemeStorageKey(7,'report-purchase-progress')
function storage(initial=[]){
  const data=new Map([[key,JSON.stringify(initial)]]),writes=[]
  return {data,writes,getItem:k=>data.get(k)??null,setItem(k,v){writes.push(k);if(this.fail?.(k))throw Error('storage unavailable');data.set(k,v)}}
}
function load(...args){assert.equal(typeof workspace.loadPersonalSchemes,'function','shared personal scheme loading with successful-once legacy import is missing');return workspace.loadPersonalSchemes(...args)}
function remove(...args){assert.equal(typeof workspace.deleteScheme,'function','shared personal scheme delete is missing');return workspace.deleteScheme(...args)}

test('old schemes import once and a renamed or deleted source does not revive',()=>{
  const local=storage(),old=scheme('旧方案'),legacy=()=>({schemes:[old],warnings:[]})
  const first=load(local,key,legacy)
  assert.equal(first.writable,true)
  assert.deepEqual(first.schemes,[old])
  workspace.saveScheme(local,key,first.schemes,{...old,name:'新名称'},fields,'旧方案',old)
  assert.deepEqual(load(local,key,legacy).schemes.map(s=>s.name),['新名称'])
  remove(local,key,'新名称',scheme('新名称'))
  assert.deepEqual(load(local,key,legacy).schemes,[])
})

test('marker write failure preserves source data and blocks destructive maintenance until retry',()=>{
  const local=storage(),old=scheme('旧方案'),legacy=()=>({schemes:[old],warnings:['旧源警告']})
  local.fail=k=>k!==key
  const first=load(local,key,legacy)
  assert.equal(first.writable,false)
  assert.deepEqual(first.schemes,[old])
  assert.ok(first.warnings.length)
  local.fail=null
  const retried=load(local,key,legacy)
  assert.equal(retried.writable,true)
  assert.deepEqual(retried.schemes,[old])
})

test('modern write failure cannot complete import or overwrite the modern array',()=>{
  const current=scheme('当前'),local=storage([current]),before=local.getItem(key)
  local.fail=k=>k===key
  const result=load(local,key,()=>({schemes:[scheme('旧方案')],warnings:[]}))
  assert.equal(result.writable,false)
  assert.equal(local.getItem(key),before)
  assert.equal(local.writes.length,1,'must not write success marker after modern write failed')
})

test('corrupt modern storage is retained and never replaced by an empty scheme list',()=>{
  const local=storage();local.data.set(key,'{bad-json')
  assert.throws(()=>load(local,key,()=>({schemes:[scheme('旧')],warnings:[]})))
  assert.equal(local.getItem(key),'{bad-json')
  assert.deepEqual(local.writes,[])
})

test('saving merges unrelated latest changes but rejects a stale edit of the same scheme',()=>{
  const a=scheme('A'),b=scheme('B'),local=storage([a,b])
  local.data.set(key,JSON.stringify([a,{...b,name:'B-renamed'}]))
  const next=workspace.saveScheme(local,key,[a,b],{...a,name:'A-edited'},fields,'A',a)
  assert.deepEqual(next.map(s=>s.name).sort(),['A-edited','B-renamed'])
  const baseline=next.find(s=>s.name==='A-edited')
  const changed={...baseline,definitions:[{...baseline.definitions[0],value:'different tab'}]}
  local.data.set(key,JSON.stringify([changed,scheme('C')]))
  const before=local.getItem(key)
  assert.throws(()=>workspace.saveScheme(local,key,next,{...baseline,name:'A-final'},fields,'A-edited',baseline),/其他|更新|变更|冲突/)
  assert.equal(local.getItem(key),before)
})

test('deleting checks the exact baseline and retains unrelated latest schemes',()=>{
  const a=scheme('A'),local=storage([a,scheme('B')])
  local.data.set(key,JSON.stringify([a,scheme('C')]))
  const result=remove(local,key,'A',a)
  assert.deepEqual(result.map(s=>s.name),['C'])
  assert.throws(()=>remove(local,key,'',null))
  const b=scheme('B'),changed={...b,isDefault:true}
  local.data.set(key,JSON.stringify([changed]))
  assert.throws(()=>remove(local,key,'B',b),/其他|更新|变更|冲突/)
  assert.deepEqual(JSON.parse(local.getItem(key)),[changed])
})

test('failed save and delete leave the original serialized data intact',()=>{
  const a=scheme('A'),local=storage([a]),before=local.getItem(key)
  local.fail=()=>true
  assert.throws(()=>workspace.saveScheme(local,key,[a],{...a,name:'A-edit'},fields,'A',a))
  assert.equal(local.getItem(key),before)
  assert.throws(()=>remove(local,key,'A',a))
  assert.equal(local.getItem(key),before)
})

test('default remains unique, new-name collision is checked against latest storage',()=>{
  const a=scheme('A','X',true),b=scheme('B'),local=storage([a,b])
  const saved=workspace.saveScheme(local,key,[a,b],{...b,isDefault:true},fields,'B',b)
  assert.deepEqual(saved.filter(s=>s.isDefault).map(s=>s.name),['B'])
  local.data.set(key,JSON.stringify([...saved,scheme('new')]))
  assert.throws(()=>workspace.saveScheme(local,key,saved,scheme('new'),fields,'',null),/同名/)
})

test('duplicate names and malformed scheme entries fail closed without overwriting data',()=>{
  for(const value of [[scheme('A'),scheme('A')],[{...scheme('A'),definitions:['bad']}],[{...scheme('A'),isDefault:'yes'}]]){
    const local=storage(value),original=local.getItem(key)
    assert.throws(()=>load(local,key),/格式|无效/)
    assert.equal(local.getItem(key),original)
    assert.deepEqual(local.writes,[])
  }
})
