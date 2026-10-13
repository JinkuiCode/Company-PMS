import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { reportScope } from '../src/query-system/report-adapter.ts'
import { isRequiredQueryField } from '../src/query-system/core.ts'
import { prepareDefinitions, activeQuery, validateDefinitions } from '../src/query-system/workspace.ts'
import { pageGuides, findGuideEntries } from '../src/page-guide/registry.ts'
import { isPublicGuidePath, guideTabHref } from '../src/page-guide/navigation.ts'
const c=(field,value='PFA',operator='contains')=>({id:1,field,value,operator,valueEnd:null,schemaVersion:2})
const required=[c('organization_ids',[1],'reference'),{...c('bill_date','2026-10-01','between'),valueEnd:'2026-10-13'}]
test('stock scopes use one material field without combined lookup',()=>{
 for(const field of ['material_code','material_name','specification']){
  const result=reportScope('stock-detail',[c(field),...required])
  assert.equal(result.params.material,'PFA');assert.equal(result.params.material_field,field)
  assert.equal(result.params.material_operator,'contains')
  assert.equal(result.conditions[0].field,field)
 }
 assert.throws(()=>reportScope('stock-detail',[c('material_name','PFA','notContains'),...required]),/物料/)
 assert.throws(()=>reportScope('stock-detail',required),/物料/)
})
test('independent material fields remain separate AND conditions',()=>{
 const result=reportScope('stock-detail',[c('material_code','18','startsWith'),c('material_name','PFA'),...required])
 assert.equal(result.params.material_field,'material_code')
 assert.equal(result.params.material_operator,'startsWith')
 assert.deepEqual(result.conditions.map(x=>x.field),['material_code','material_name'])
})
test('a scheme can choose name alone while the material group stays mandatory',()=>{
 const fields=['material_code','material_name','specification'].map(field=>({field,label:field,type:'text',requiredGroup:'物料'}))
 assert.ok(Object.keys(activeQuery([],fields).errors).length)
 assert.ok(Object.keys(validateDefinitions([],fields)).length)
 assert.ok(validateDefinitions([],fields).material_code,'组必输错误须显示在实际字段行')
 const definitions=fields.map(f=>({field:f.field,shown:f.field==='material_name',operator:'contains',value:f.field==='material_name'?'PFA':null,valueEnd:null,schemaVersion:2}))
 assert.deepEqual(validateDefinitions(definitions,fields),{})
 assert.deepEqual(activeQuery([c('material_name')],fields).errors,{})
 assert.equal(isRequiredQueryField(fields[0],fields,[c('material_name')]),false)
 assert.equal(isRequiredQueryField(fields[1],fields,[c('material_name')]),true)
})
test('new query definitions do not offer composite fields',()=>{
 for(const page of ['PurchaseOverviewList','PurchaseProgressList','InventoryList','StockDetailList']){
  const source=readFileSync(new URL(`../src/views/reports/${page}.vue`,import.meta.url),'utf8')
  assert.doesNotMatch(source,/field:\s*['"](?:keyword|material)['"]\s*,\s*label:/)
 }
 assert.doesNotMatch(readFileSync(new URL('../src/views/project/ProjectArchive.vue',import.meta.url),'utf8'),/field:'keyword',label:'综合搜索'/)
})
test('removed combined defaults remain detectable without changing old stored definition',()=>{
 const original=[{field:'keyword',operator:'contains',value:'M1',valueEnd:null,shown:true}]
 const result=prepareDefinitions(original,[{field:'material_code',label:'物料编码',type:'text'}])
 assert.deepEqual(result.invalidFields,['keyword']);assert.equal(original[0].value,'M1')
})
test('feedback guide uses shared searchable content and standalone navigation',()=>{
 assert.ok(pageGuides.feedback)
 assert.ok(findGuideEntries(pageGuides.feedback,'operations','邮件').length)
 assert.ok(findGuideEntries(pageGuides.feedback,'fields','处理状态').length)
 assert.ok(isPublicGuidePath('/page-guide/feedback'))
 assert.match(guideTabHref('feedback',{section:'fields',group:'全部',search:'处理状态'}),/^\/page-guide\/feedback#/)
})
