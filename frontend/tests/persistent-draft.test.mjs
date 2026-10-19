import {test} from 'node:test'
import assert from 'node:assert/strict'
import {existsSync} from 'node:fs'
const path=new URL('../src/form-system/usePersistentDraft.ts',import.meta.url)
const mod=existsSync(path)?await import(path.href):{}
function setup(){
 assert.equal(typeof mod.usePersistentDraft,'function','持久化草稿适配必须存在')
 const rows=new Map();let loseSave=false,loseSubmit=false
 const api={
  async get(id){if(!rows.has(id))throw {response:{status:404}};return structuredClone(rows.get(id))},
  async save(body){const prior=rows.get(body.id);if(prior&&prior.version!==body.expected_version)throw {response:{status:409,data:{detail:{code:'DRAFT_VERSION_CONFLICT'}}}};const row={id:body.id,version:(prior?.version||0)+1,status:'active',payload:structuredClone(body.payload)};rows.set(body.id,row);if(loseSave)throw {};return structuredClone(row)},
  async submit(id){rows.get(id).status='used';rows.get(id).archive_id=42;if(loseSubmit)throw {};return {id:42}},
 }
 return {d:mod.usePersistentDraft(api,()=> '00000000-0000-4000-8000-000000000001'),rows,setLoseSave:v=>loseSave=v,setLoseSubmit:v=>loseSubmit=v}
}
test('手动保存不完整值，版本冲突保留身份及输入，另存不覆盖旧版本',async()=>{
 const {d,rows}=setup();await d.save({project_name:'未完成'})
 assert.equal(d.version.value,1);rows.get(d.id.value).version=2
 await assert.rejects(d.save({project_name:'本次输入'}));assert.equal(d.conflict.value,true)
 assert.equal(rows.get(d.id.value).payload.project_name,'未完成')
 assert.equal(d.version.value,1)
 d.startNew();assert.equal(d.id.value,null);assert.equal(d.conflict.value,false)
})
test('保存结果不明必须先核对，确认同一快照后恢复版本',async()=>{
 const {d,setLoseSave}=setup();setLoseSave(true)
 await assert.rejects(d.save({quantity:1}));assert.equal(d.unknown.value,'save')
 await assert.rejects(d.save({quantity:2}),/核对/)
 const r=await d.reconcile();assert.equal(r.status,'active');assert.equal(d.version.value,1);assert.equal(d.unknown.value,null)
})
test('正式保存响应丢失可核对已有档案，不重复创建',async()=>{
 const {d,setLoseSubmit}=setup();await d.save({project_name:'正式'})
 setLoseSubmit(true);await assert.rejects(d.submit());assert.equal(d.unknown.value,'submit')
 const r=await d.reconcile();assert.equal(r.archive_id,42);assert.equal(r.status,'used')
})
test('确定的校验失败保留草稿但不进入结果不明状态',async()=>{
 const {d}=setup();await d.save({})
 const second=mod.usePersistentDraft({get:async()=>{},save:async()=>{throw {response:{status:422}}},submit:async()=>{}})
 await assert.rejects(second.save({quantity:-1}));assert.equal(second.unknown.value,null)
 assert.equal(d.version.value,1)
})
test('核对服务器规范化数量字符串，不把同一值误报为多端冲突',async()=>{
 const {d,rows,setLoseSave}=setup();setLoseSave(true)
 await assert.rejects(d.save({quantity:2}));rows.get(d.id.value).payload.quantity='2'
 await d.reconcile();assert.equal(d.conflict.value,false);assert.equal(d.version.value,1)
})
test('编码重号保留身份与版本，允许改号重试，不误报多端冲突',async()=>{
 let duplicate=false
 const d=mod.usePersistentDraft({get:async()=>{},submit:async()=>{},save:async body=>{
  if(duplicate)throw {response:{status:409,data:{detail:{code:'ARCHIVE_UNIQUE_CONFLICT',field_key:'project_code',message:'项目编号已存在，请更换编号'}}}}
  return {id:body.id,version:(body.expected_version||0)+1,status:'active',payload:body.payload}
 }},()=> 'unique-test-id')
 await d.save({project_code:'FIRST'});const id=d.id.value
 duplicate=true;await assert.rejects(d.save({project_code:'DUPLICATE'}))
 assert.equal(d.conflict.value,false);assert.equal(d.unknown.value,null)
 assert.equal(d.id.value,id);assert.equal(d.version.value,1)
 duplicate=false;await d.save({project_code:'CORRECTED'})
 assert.equal(d.version.value,2);assert.equal(d.id.value,id)
})
test('保存响应丢失后核对服务端去除编号首尾空格，不误报版本冲突',async()=>{
 let stored
 const d=mod.usePersistentDraft({get:async()=>stored,submit:async()=>{},save:async body=>{
  stored={id:body.id,version:1,status:'active',payload:{...body.payload,project_code:body.payload.project_code.trim()}}
  throw {}
 }},()=> 'normalized-code-id')
 await assert.rejects(d.save({project_code:' CODE ',project_name:'项目'}))
 assert.equal(d.unknown.value,'save')
 await d.reconcile()
 assert.equal(d.conflict.value,false);assert.equal(d.unknown.value,null);assert.equal(d.version.value,1)
})
