import assert from 'node:assert/strict'
import {test} from 'node:test'
import {reportScope,purchaseDetailEntry} from '../src/query-system/report-adapter.ts'
import {buildStockDetailQuery} from '../src/views/reports/stockDetailState.ts'
import {readFileSync} from 'node:fs'
import {linkReportScope} from '../src/query-system/report-adapter.ts'
import ts from 'typescript'
const code={id:1,schemaVersion:2,field:'material_code',operator:'reference',value:['0007-A','0008-B'],valueEnd:null}
const source=[code,{id:2,field:'organization_ids',operator:'reference',value:[11],valueEnd:null},{id:3,field:'bill_date',operator:'between',value:'2026-10-01',valueEnd:'2026-10-20'}]
test('stock converts the entire reference array into primary scope, not an after-balance filter',()=>{
  let result
  assert.doesNotThrow(()=>{result=reportScope('stock-detail',source)})
  assert.deepEqual(result.params.material_codes,['0007-a','0008-b'])
  assert.equal(result.params.material,undefined);assert.equal(result.conditions.some(c=>c.field==='material_code'),false)
  const params=buildStockDetailQuery({...result.params,dates:[result.params.start_date,result.params.end_date],stock_id:null},1,50)
  assert.deepEqual(params.material_codes,['0007-a','0008-b'])
})
test('purchase overview drill preserves all selected material codes',()=>{
  const result=purchaseDetailEntry({conditions:[code],organization_ids:[11],dates:[],column_filters:[]},[{field:'material_code'}],{project_code:'P',organization_id:11,product_line_name:'线'})
  assert.deepEqual(result.draft.conditions[0].value,['0007-A','0008-B'])
})
test('invalid stock arrays and ambiguous dual primary modes cannot widen scope',()=>{
  assert.throws(()=>reportScope('stock-detail',[{...code,value:[]},...source.slice(1)]))
  assert.throws(()=>buildStockDetailQuery({material:'A',material_codes:['B'],dates:['2026-10-01','2026-10-20'],organization_ids:[11],stock_id:null},1,50))
})
test('actual purchase detail setter cannot erase selected codes when drill removes a product line row',()=>{
  const page=readFileSync(new URL('../src/views/reports/PurchaseProgressList.vue',import.meta.url),'utf8')
  const line=page.split('\n').find(line=>line.startsWith('const conditions = computed'))
  const queryDraft={value:[code,{id:2,field:'organization_ids',operator:'reference',value:[11],valueEnd:null}]}
  const js=ts.transpile(line.replace('const conditions =','return'),{target:ts.ScriptTarget.ES2022})
  const control=new Function('computed','queryDraft','linkReportScope',js)(x=>x,queryDraft,linkReportScope)
  control.set([code])
  assert.deepEqual(queryDraft.value[0].value,['0007-A','0008-B'])
})
