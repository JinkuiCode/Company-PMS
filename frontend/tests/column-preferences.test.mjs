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
