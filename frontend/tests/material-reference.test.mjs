import assert from 'node:assert/strict'
import {test} from 'node:test'
import {existsSync} from 'node:fs'
const file=new URL('../src/query-system/material-reference.ts',import.meta.url)
const source=existsSync(file)?await import(file.href):{}
function api(name){assert.equal(typeof source[name],'function',`${name} material adapter is missing`);return source[name]}

test('material keys remain strings, preserve leading zeros and reject invalid values',()=>{
  const normalize=api('normalizeMaterialCodes')
  assert.deepEqual(normalize([' 0007-A ','0007-a','0008-B']),['0007-a','0008-b'])
  for(const value of [[],[7],[true],[' '],['A\nB'],Array(1001).fill('A')])assert.throws(()=>normalize(value))
})
test('candidate scope uses editor conditions without requiring material/date values',async()=>{
  const calls=[]
  const reference=api('materialReference')('stock-detail',async params=>{calls.push(params);return{items:[{value:'0007-a',code:'0007-A',label:'合成物料'}],total:1}},()=>[])
  const result=await reference.load({conditions:[{id:1,field:'organization_ids',operator:'reference',value:[11],valueEnd:null}],page:1,pageSize:50})
  assert.deepEqual(calls[0].organization_ids,[11]);assert.equal(result.items[0].value,'0007-a')
  await assert.rejects(()=>reference.load({conditions:[],page:1,pageSize:50}),/产品线/)
})
test('only reference-mode full encoded URLs have a 6000-byte guard',()=>{
  const guard=api('guardMaterialReferenceUrl'),filters=JSON.stringify([{field:'material_code',operator:'reference',value:['0007-a']}])
  assert.doesNotThrow(()=>guard('/reports/purchase',{filters,page:1}))
  assert.throws(()=>guard('/reports/purchase',{filters,other:'长'.repeat(1000)}),/6000|过长/)
  assert.doesNotThrow(()=>guard('/reports/purchase',{filters:JSON.stringify([{field:'material_name',operator:'contains',value:'长'.repeat(1000)}])}))
  assert.throws(()=>guard('/reports/stock-detail',{material_codes:['A'],other:'长'.repeat(1000)}),/6000|过长/)
})
test('the caller receives the explicit reference URL error before the request is sent',()=>{
  const messages=[]
  assert.throws(()=>api('guardMaterialReferenceUrl')('/reports/stock-detail',{material_codes:['A'],extra:'长'.repeat(1000)},false,message=>messages.push(message)),/6000/)
  assert.equal(messages.length,1);assert.match(messages[0],/减少选择|原选择保留/)
})
