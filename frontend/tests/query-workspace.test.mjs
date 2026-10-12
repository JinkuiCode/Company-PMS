import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
const source = new URL('../src/query-system/workspace.ts', import.meta.url)
assert.ok(existsSync(source), '共享查询工作区状态模块必须存在，不允许页面各自保存方案')
const { instantiateDefinitions, activeQuery, saveScheme, readSchemes, schemeStorageKey, settingsDefinitions, selectScheme, prepareDefinitions } = await import(source.href)
const fields = [{field:'code',label:'编码',type:'text'}, {field:'qty',label:'数量',type:'number'}, {field:'org',label:'组织',type:'enum',required:true,options:[{value:1,label:'Bench'}]}]
const defs = [{field:'code',shown:true,operator:'contains',value:null,valueEnd:null},{field:'qty',shown:false,operator:'equals',value:0,valueEnd:null},{field:'org',shown:true,operator:'in',value:[],valueEnd:null}]
const draft = instantiateDefinitions(defs)
assert.match(Object.values(activeQuery(draft,fields).errors).join(), /组织/)
draft[1].value = [1]
assert.deepEqual(activeQuery(draft,fields).errors,{})
assert.equal(activeQuery([...draft,{id:3,field:'qty',operator:'equals',value:0,valueEnd:null,schemaVersion:2}],fields).conditions.length,2)
assert.ok(activeQuery([{id:1,field:'org',operator:'notIn',value:[1],valueEnd:null,schemaVersion:2}],fields).errors[1])
const storage = new Map(), local = {getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)}
const key = schemeStorageKey(4,'archive'), other = schemeStorageKey(5,'archive')
let schemes = saveScheme(local,key,[],{name:'jin',definitions:settingsDefinitions(defs,draft,fields),isDefault:true,preferences:{pageSize:50}},fields)
assert.equal(readSchemes(local,other).length,0)
schemes = saveScheme(local,key,schemes,{name:'second',definitions:defs,isDefault:true,preferences:{}},fields)
assert.equal(schemes.filter(s=>s.isDefault).length,1)
assert.equal(schemes[0].isDefault,false)
const selected = selectScheme(schemes,'jin',defs)
selected.conditions[0].value='temporary'
assert.equal(selectScheme(schemes,'jin',defs).conditions[0].value,null,'草稿不得改变已保存默认值')
assert.deepEqual(selected.columnFilters,[])
assert.throws(()=>saveScheme(local,key,schemes,{name:'second',definitions:defs,isDefault:false},fields,'jin'),/同名/)
assert.throws(()=>schemeStorageKey(null,'archive'),/登录/)
const obsolete = [...defs, {field:'project_name',shown:true,operator:'equals',value:'旧项目',valueEnd:null}]
const original = JSON.stringify(obsolete)
const prepared = prepareDefinitions(obsolete, fields)
assert.deepEqual(prepared.definitions, defs)
assert.deepEqual(prepared.invalidFields, ['project_name'])
assert.equal(JSON.stringify(obsolete), original, '失效条件仅在内存整理，不改变原方案')
assert.deepEqual(prepareDefinitions(defs, fields).invalidFields, [])
assert.deepEqual(settingsDefinitions(prepared.definitions, instantiateDefinitions(prepared.definitions), fields).map(d=>d.field).sort(), fields.map(f=>f.field).sort())
console.log('query workspace passed: private schemes, single default, draft isolation, required, zero, reselection')
