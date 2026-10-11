import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
const url = new URL('../src/query-system/system-adapter.ts', import.meta.url)
assert.ok(existsSync(url), '其他列表必须提供适配层，不允许复制私有方案逻辑')
const { useSystemQuery, loadCompleteDataset, serverQueryParams, requireServerQueryVersion } = await import(url.href)
assert.equal(typeof serverQueryParams, 'function', '服务端迁移使用明确v2协议，不降级本页过滤')
const sent = serverQueryParams([{id:1,field:'name',operator:'contains',value:'Beta',valueEnd:null}], [{field:'status',mode:'values',values:[0]}])
assert.equal(JSON.parse(sent.filters)[0].schemaVersion,2)
assert.equal(JSON.parse(sent.column_filters)[0].field,'status')
assert.throws(() => requireServerQueryVersion({items:[],total:0}, true), /v2/)
assert.equal(requireServerQueryVersion({query_version:2},true),true)
const fields = [{field:'name',label:'名称',type:'text'}, {field:'status',label:'状态',type:'enum',options:[{value:0,label:'禁用'},{value:1,label:'启用'}]}]
const query = useSystemQuery(() => fields, ['name','status'])
assert.deepEqual(useSystemQuery(() => fields,['status','name']).defaults.value.filter(d=>d.shown).map(d=>d.field), ['status','name'], '默认查询顺序遵循页面提供的defaults顺序')
const rows = [{id:1,name:'Alpha',status:1},{id:2,name:'Beta',status:0}]
let busy = false
const guarded = useSystemQuery(() => fields, ['name'], {requireQuery:true,ready:()=>!busy})
guarded.filterRows(rows)
assert.equal(guarded.columnContext.ready(),false,'未接受显式查询前禁止全量候选')
await assert.rejects(guarded.columnContext.load('name','',1), /查询/)
guarded.submit([])
assert.equal(guarded.columnContext.ready(),true)
busy = true
assert.equal(guarded.columnContext.ready(),false,'加载期间禁止候选')
busy = false
const emptyColumns = query.columnFilters.value
query.clearColumns()
assert.equal(query.columnFilters.value,emptyColumns,'无列筛选时清理不触发多余表头重建')
query.draft.value = [{id:1,field:'status',operator:'reference',value:[0],valueEnd:null,schemaVersion:2}]
assert.equal(query.filterRows(rows).length, 2, '草稿不触发查询')
query.submit(query.draft.value)
assert.deepEqual(query.filterRows(rows), [rows[1]], '禁用记录也可查询，引用按存储值匹配')
query.draft.value[0].value = [1]
assert.deepEqual(query.filterRows(rows), [rows[1]], '已提交条件与草稿隔离')
query.submit([{id:1,field:'status',operator:'contains',value:'禁',valueEnd:null,schemaVersion:2}])
assert.deepEqual(query.filterRows(rows), [rows[1]], '枚举文本操作按显示名匹配')
query.submit([])
assert.equal(query.filterRows(rows).length, 2)
query.columnContext.apply('status', {field:'status',mode:'values',values:[0]})
assert.deepEqual(query.filterRows(rows), [rows[1]], '列过滤必须在客户端分页前应用')
query.setResultRows(rows)
const candidates = await query.columnContext.load('status','',1)
assert.equal(candidates.items.length, 2, '候选去本列筛选且包括完整结果')
query.clearColumns()
assert.equal(query.filterRows(rows).length, 2, '方案切换/重置清理列筛选')
const dates = useSystemQuery(() => [{field:'created_at',label:'创建日期',type:'date'}], ['created_at'])
const timed = [{created_at:'2026-10-11T12:34:56'}]
dates.filterRows(timed)
const dateValues = await dates.columnContext.load('created_at','',1)
dates.columnContext.apply('created_at',{field:'created_at',mode:'values',values:[dateValues.items[0].value]})
assert.deepEqual(dates.filterRows(timed),timed,'日期候选值与列匹配必须使用同一日期粒度')
const calls = []
const result = await loadCompleteDataset(async (page,pageSize) => {
  calls.push([page,pageSize])
  return {items:rows.slice(page-1,page),total:2,modules:['metadata']}
}, 1)
assert.deepEqual(calls, [[1,1],[2,1]])
query.submit([{id:1,field:'name',operator:'equals',value:'Beta',valueEnd:null,schemaVersion:2}])
assert.deepEqual(query.filterRows(result.items).slice(0,1), [rows[1]], '全授权数据先过滤再分页，能查询第二服务端页')
assert.deepEqual(result.modules,['metadata'])
await assert.rejects(loadCompleteDataset(async page => ({items:page===1?[rows[0]]:[],total:2}),1), /不完整/)
await assert.rejects(loadCompleteDataset(async page => ({items:[rows[0]],total:page===1?2:3}),1), /变化/)
await assert.rejects(loadCompleteDataset(async () => ({items:[rows[0]],total:2}),1,()=>true,row=>row.id), /重复/)
await assert.rejects(loadCompleteDataset(async () => ({items:[rows[0]],total:2}),1,()=>false), /取消/)
assert.throws(()=>query.submit([{id:1,field:'missing',operator:'equals',value:'x',valueEnd:null,schemaVersion:2}]), /失效/)
console.log('system-query adapter: explicit submit, disabled enums, labels, full dataset, partial/stale rejection passed')
