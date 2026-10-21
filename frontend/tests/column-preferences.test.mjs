import assert from 'node:assert/strict'
import {test} from 'node:test'
import {existsSync} from 'node:fs'
const url=new URL('../src/list-system/columnPreferences.ts',import.meta.url),mod=existsSync(url)?await import(url.href):{}
const schema={allowed:new Set(['code','name']),defaults:['code'],fixed:new Set(['actions'])}
function setup(pageKey='archive',ownerId=1,values=new Map()){
 assert.equal(typeof mod.createColumnPreferences,'function','统一列偏好模块必须存在')
 const storage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}
 return {values,store:mod.createColumnPreferences({pageKey,ownerId:()=>ownerId,storage:()=>storage})}
}
test('账号和页面共同隔离，无账号不读取或保存',()=>{
 const a=setup(),b=setup('archive',2,a.values),c=setup('progress',1,a.values),none=setup('archive',null,a.values)
 a.store.write({selected_column_keys:['name'],columnState:[]},schema)
 assert.equal(b.store.read(schema).status,'empty');assert.equal(c.store.read(schema).status,'empty')
 assert.equal(none.store.read(schema).status,'anonymous');assert.equal(none.store.write({selected_column_keys:[],columnState:[]},schema).status,'anonymous')
 assert.equal(a.values.size,1)
})
test('v0只读迁移保留有效布局，写入v1仍保留旧程序可读字段',()=>{
 const {store,values}=setup(),old={selected_column_keys:['name','gone','name'],columnState:[{colId:'name',width:212,pinned:'left',hide:false},{colId:'gone',width:77},{colId:'actions',width:64},{colId:'name',width:123}]}
 const raw=JSON.stringify(old);values.set(store.key(),raw)
 const result=store.read(schema)
 assert.equal(result.status,'ready');assert.deepEqual(result.value,{selected_column_keys:['name'],columnState:[old.columnState[0],old.columnState[2]]})
 assert.equal(values.get(store.key()),raw,'读取不能重写源偏好')
 assert.equal(store.write(result.value,schema).status,'saved')
 const written=JSON.parse(values.get(store.key()));assert.equal(written.schema_version,1);assert.equal(written.owner_id,1);assert.equal(written.page_key,'archive')
 assert.deepEqual(written.selected_column_keys,['name']);assert.equal(written.columnState[0].width,212)
})
test('明确的空列选择不被默认值覆盖，损坏数组不进入grid',()=>{
 const {store,values}=setup();values.set(store.key(),JSON.stringify({selected_column_keys:[],columnState:[null,{},'bad',{colId:'name',width:120}]}))
 assert.deepEqual(store.read(schema).value,{selected_column_keys:[],columnState:[{colId:'name',width:120}]})
})
test('未来版本或归属不符不覆盖，明确恢复默认才清除',()=>{
 const {store,values}=setup()
 for(const bad of [{schema_version:99},{schema_version:1,page_key:'other',owner_id:1},{schema_version:1,page_key:'archive',owner_id:2}]){
  const raw=JSON.stringify(bad);values.set(store.key(),raw)
  assert.equal(store.read(schema).status,'unsupported');assert.equal(store.write({selected_column_keys:[],columnState:[]},schema).status,'unsupported')
  assert.equal(values.get(store.key()),raw)
 }
 assert.equal(store.clear().status,'cleared');assert.equal(store.read(schema).status,'empty')
})
test('缓存读写异常有明确状态，不抛出导致页面崩溃',()=>{
 assert.equal(typeof mod.createColumnPreferences,'function')
 const store=mod.createColumnPreferences({pageKey:'archive',ownerId:()=>1,storage:()=>{throw new Error('浏览器禁止存储')}})
 assert.equal(store.read(schema).status,'unavailable');assert.equal(store.write({selected_column_keys:[],columnState:[]},schema).status,'unavailable');assert.equal(store.clear().status,'unavailable')
})
test('旧账号键保持兼容，损坏JSON拒绝覆盖至明确恢复',()=>{
 assert.equal(typeof mod.createColumnPreferences,'function');const values=new Map()
 const store=mod.createColumnPreferences({pageKey:'archive',ownerId:()=>7,legacyPrefix:'pms_project_archive_list_columns_v2',storage:()=>({getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)})})
 assert.equal(store.key(),'pms_project_archive_list_columns_v2:7')
 values.set(store.key(),'{bad');assert.equal(store.read(schema).status,'invalid');assert.equal(store.write({selected_column_keys:[],columnState:[]},schema).status,'invalid');assert.equal(values.get(store.key()),'{bad')
})
test('旧选择字段别名只读兼容，写入保留双字段供旧程序读取',()=>{
 const values=new Map(),storage={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}
 const store=mod.createColumnPreferences({pageKey:'progress',ownerId:()=>7,legacyPrefix:'progress_v2',legacySelectionKey:'selected_sheet_field_keys',storage:()=>storage})
 const old=JSON.stringify({selected_sheet_field_keys:['name','gone'],columnState:[{colId:'name',width:231,pinned:'left'}]})
 values.set(store.key(),old)
 const read=store.read(schema)
 assert.equal(read.status,'ready');assert.deepEqual(read.value.selected_column_keys,['name'])
 assert.equal(values.get(store.key()),old,'读取不能写回或丢弃旧格式')
 assert.equal(store.write(read.value,schema).status,'saved')
 const written=JSON.parse(values.get(store.key()))
 assert.deepEqual(written.selected_column_keys,['name']);assert.deepEqual(written.selected_sheet_field_keys,['name'])
 assert.equal(written.columnState[0].width,231);assert.equal(written.owner_id,7);assert.equal(written.page_key,'progress');assert.equal(written.schema_version,1)
 values.set(store.key(),JSON.stringify({...written,selected_column_keys:[],selected_sheet_field_keys:['name']}))
 assert.deepEqual(store.read(schema).value.selected_column_keys,[],'新版标准选择优先，包括明确的空选择')
 values.set(store.key(),JSON.stringify({...written,schema_version:99}))
 assert.equal(store.write(read.value,schema).status,'unsupported')
})

test('controlled opt-in layout version survives local round-trip and drops unrelated metadata',()=>{
 const {store,values}=setup(),opt={...schema,layoutVersion:1}
 const input={layout_version:1,selected_column_keys:['name'],columnState:[],unknown:'never store'}
 assert.equal(store.write(input,opt).status,'saved')
 assert.equal(store.read(opt).value.layout_version,1)
 assert.equal(JSON.parse(values.get(store.key())).unknown,undefined)
 assert.equal(mod.normalizeColumnPreference(input,schema).layout_version,undefined,'old callers do not opt in')
})
test('invalid or future opt-in layout version cannot overwrite the original local string',()=>{
 const {store,values}=setup(),opt={...schema,layoutVersion:1}
 for(const version of [2,'1',0,null]){
  const raw=JSON.stringify({layout_version:version,selected_column_keys:['name'],columnState:[]});values.set(store.key(),raw)
  assert.ok(['invalid','unsupported'].includes(store.read(opt).status))
  assert.notEqual(store.write({layout_version:1,selected_column_keys:[],columnState:[]},opt).status,'saved')
  assert.equal(values.get(store.key()),raw)
 }
})
