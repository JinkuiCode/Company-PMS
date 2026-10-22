import assert from 'node:assert/strict'
import {test} from 'node:test'
import {readFileSync,existsSync} from 'node:fs'
import {createRequire} from 'node:module'
import {dirname,resolve} from 'node:path'
import ts from 'typescript'
import * as vue from 'vue'

const require=createRequire(import.meta.url)
const root=resolve(dirname(new URL(import.meta.url).pathname),'../src')
const keys=['product_line_name','project_code','material_code','material_name','unit_name','bill_no','progress']
const field=key=>({key,label:key,group:key.startsWith('material')?'物料信息':'其他',value_type:'text'})
const metadata={fields:keys.map(field),organizations:[{value:7,label:'产品线A'}],query_fields:keys.map(key=>({field:key,label:key,type:'text'})),progress_labels:{},document_status_labels:{}}
const flatten=columns=>columns.flatMap(c=>c.children?flatten(c.children):[c])

function pageHarness(initial={},entry,response=metadata){
  const storage=new Map([['pms:purchase-report:v1:42',JSON.stringify(initial)]]),calls=[],cache=new Map()
  const localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)}
  const api=new Proxy({},{get:(_,key)=>async(...args)=>{
    calls.push({method:key,args})
    return String(key).endsWith('Metadata')?response:{items:[],total:0,queried_at:''}
  }})
  function load(specifier){
    if(specifier==='vue')return {...vue,onMounted(){},onUnmounted(){},watch(){}}
    if(specifier==='element-plus')return {ElButton:{},ElMessage:{warning(){}},ElMessageBox:{confirm:async()=>true}}
    if(specifier==='ag-grid-community')return {ModuleRegistry:{registerModules(){}},AllCommunityModule:{}}
    if(specifier==='ag-grid-vue3'||specifier==='@element-plus/icons-vue'||specifier.endsWith('.vue')||specifier.endsWith('.css')||specifier==='@/form-system')return {}
    if(specifier.startsWith('@/api/'))return api
    if(specifier==='@/stores/auth')return {useAuthStore:()=>({user:{id:42},hasPermission:()=>true})}
    if(specifier==='@/query-system/column-grid')return {decorateQueryColumns:value=>value}
    if(specifier==='@/utils/agGridLocale')return {chineseLocaleText:{}}
    if(!specifier.startsWith('@/')&&!specifier.startsWith('/'))return require(specifier)
    let file=specifier.startsWith('@/')?resolve(root,specifier.slice(2)):specifier
    if(!existsSync(file))file+='.ts'
    if(cache.has(file))return cache.get(file)
    const exports={};cache.set(file,exports)
    const code=ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
    new Function('require','exports','module',code)(s=>load(s.startsWith('.')?resolve(dirname(file),s):s),exports,{exports})
    return exports
  }
  const script=readFileSync(resolve(root,'views/reports/PurchaseProgressList.vue'),'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
  const code=ts.transpileModule(script+'\nexports.page={initialize,readPreferences,visible,columns,planSnapshot,savePreferences,submitWorkspace,conditions,pageSize,applyEntry};',{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const exports={}
  new Function('require','exports','localStorage','defineProps','defineEmits',code)(s=>load(s.startsWith('.')?resolve(root,'views/reports',s):s),exports,localStorage,()=>({entry}),()=>()=>{})
  return {page:exports.page,calls,storage,saved:()=>JSON.parse(localStorage.getItem('pms:purchase-report:v1:42'))}
}

test('actual detail page defaults material code immediately before material name',async()=>{
  const {page,calls}=pageHarness()
  await page.initialize()
  const shown=flatten(page.columns.value).filter(c=>!c.hide).map(c=>c.colId)
  assert.ok(shown.includes('material_code'),'material code is hidden on a new detail page')
  assert.equal(shown.indexOf('material_code')+1,shown.indexOf('material_name'))
  assert.deepEqual(shown.slice(0,2),['product_line_name','project_code'])
  assert.equal(calls.filter(c=>c.method==='getPurchaseRows').length,0,'standalone report must stay pending')
})

test('actual detail page migrates old visible and frozen column state without changing other columns',async()=>{
  const initial={reportIdentityVersion:1,visible:['product_line_name','project_code','material_name','bill_no'],columns:[
    {colId:'product_line_name',pinned:'left',width:144},{colId:'project_code',pinned:'left',width:175},
    {colId:'bill_no',width:211,sort:'desc',sortIndex:0},{colId:'material_name',pinned:'right',width:241,flex:2},
    {colId:'material_code',hide:true,pinned:'left',width:167},
  ],sort:{sort:'bill_no',direction:'desc'},pageSize:200,custom:'keep'}
  const {page,saved}=pageHarness(initial)
  await page.initialize()
  assert.ok(page.visible.value.includes('material_code'),'legacy visibility must receive the new default')
  const state=page.planSnapshot().columns
  assert.equal(state.findIndex(c=>c.colId==='material_code')+1,state.findIndex(c=>c.colId==='material_name'))
  assert.deepEqual(state.find(c=>c.colId==='material_code'),{colId:'material_code',hide:false,pinned:'right',width:167})
  for(const column of initial.columns.filter(c=>c.colId!=='material_code'))assert.deepEqual(state.find(c=>c.colId===column.colId),column)
  assert.equal(saved().custom,'keep')
  assert.equal(saved().pageSize,200)
})

const layout={}
const helper=ts.transpileModule(readFileSync(resolve(root,'views/reports/purchase-material-layout.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
new Function('exports',helper)(layout)
const migrate=layout.migratePurchaseMaterialLayout

test('one-time layout migration preserves input and becomes idempotent',()=>{
  const original={visible:['material_name','unit_name'],columns:[{colId:'unit_name',width:97},{colId:'material_name',hide:false,width:234,pinned:'right'}],pageSize:300,scope:{project_code:'P1'},custom:{value:8}}
  const copy=structuredClone(original),result=migrate(original,keys)
  assert.deepEqual(original,copy)
  assert.deepEqual(migrate(result,keys),result)
  assert.deepEqual(result.scope,original.scope)
  assert.equal(result.pageSize,300)
  assert.deepEqual(result.custom,original.custom)
  assert.equal(result.purchaseMaterialLayoutVersion,1)
})

test('hidden name remains hidden and partial applyOrder only moves material code',async()=>{
  const initial={reportIdentityVersion:1,visible:['product_line_name','project_code','bill_no'],columns:[
    {colId:'bill_no',width:203},{colId:'material_name',hide:true,pinned:'left',width:225},
    {colId:'product_line_name',pinned:'left',width:141},
  ]}
  const {page}=pageHarness(initial)
  await page.initialize()
  assert.ok(!page.visible.value.includes('material_name'))
  assert.ok(page.visible.value.includes('material_code'))
  const state=page.planSnapshot().columns
  assert.deepEqual(state.filter(c=>c.colId!=='material_code').map(c=>c.colId),[
    'bill_no','material_name','product_line_name','project_code','unit_name','progress','purchase_actions',
  ])
  assert.equal(state.find(c=>c.colId==='material_name').hide,true)
  assert.equal(state.find(c=>c.colId==='material_code').pinned,'left')
})

test('modern saved visibility and order remain authoritative, including all columns hidden',async()=>{
  const initial={reportIdentityVersion:1,purchaseMaterialLayoutVersion:1,visible:['bill_no','material_name'],columns:[
    {colId:'material_name',width:201,pinned:null},{colId:'bill_no',width:194},{colId:'material_code',hide:true,pinned:'right',width:188},
  ]}
  const {page}=pageHarness(initial)
  await page.initialize()
  assert.deepEqual(page.visible.value,initial.visible)
  assert.deepEqual(page.planSnapshot().columns,initial.columns)
  assert.deepEqual(migrate({...initial,visible:[]},keys).visible,[])
})

test('old named scheme migration remains in memory until explicit scheme save',async()=>{
  const {page,storage,calls}=pageHarness()
  await page.initialize()
  const definitions=[{field:'bill_no',operator:'equals',value:'REQ1',valueEnd:null,shown:true,schemaVersion:2}]
  const preferences={reportIdentityVersion:1,visible:['material_name','bill_no'],columns:[{colId:'material_name',width:226,pinned:'right'},{colId:'bill_no',width:172}],pageSize:100}
  const schemes=[{version:2,name:'旧方案',isDefault:true,definitions,preferences}]
  const key='pms:query-workspace:v2:42:report-purchase-progress'
  storage.set(key,JSON.stringify(schemes))
  page.conditions.value=definitions.map((d,i)=>({...d,id:i+1}))
  await page.submitWorkspace(page.conditions.value,preferences)
  assert.deepEqual(JSON.parse(storage.get(key)),schemes)
  assert.ok(page.visible.value.includes('material_code'))
  assert.equal(page.planSnapshot().purchaseMaterialLayoutVersion,1)
  assert.equal(page.pageSize.value,100)
  assert.match(calls.find(c=>c.method==='getPurchaseRows').args[0].filters,/REQ1/)
  const snapshot=page.planSnapshot()
  const modern={...snapshot,visible:['bill_no'],columns:[{colId:'bill_no',width:177},{colId:'material_code',hide:true,pinned:null}]}
  await page.submitWorkspace(page.conditions.value,modern)
  assert.deepEqual(page.visible.value,['bill_no'])
  assert.deepEqual(page.planSnapshot().columns,modern.columns)
})

test('old backend metadata does not complete the material layout version',async()=>{
  const initial={reportIdentityVersion:1,visible:['material_name'],columns:[{colId:'material_name',width:223}]}
  const {page,saved}=pageHarness(initial,undefined,{...metadata,fields:metadata.fields.filter(f=>f.key!=='material_code')})
  await page.initialize()
  assert.deepEqual(saved(),initial)
  assert.equal(page.planSnapshot().purchaseMaterialLayoutVersion,undefined)
})

test('overview drill keeps the same default layout and exact project query scope',async()=>{
  const entry={draft:{keyword:'',organization_ids:[7],project_code:'',supplier:'',progress:'',dates:[],conditions:[{id:1,field:'bill_no',operator:'equals',value:'REQ1',valueEnd:null,schemaVersion:2}]},scope:{project_code:'P1',organization_id:7,product_line_name:'产品线A'}}
  const {page,calls}=pageHarness({},entry)
  await page.initialize()
  assert.ok(page.visible.value.includes('material_code'))
  const request=calls.find(c=>c.method==='getPurchaseRows').args[0]
  assert.equal(request.project_code,'P1')
  assert.deepEqual(request.organization_ids,[7])
  assert.match(request.filters,/REQ1/)
})

test('visible-only old scheme retains the current effective column order',()=>{
  const current=[{colId:'bill_no',width:207},{colId:'unit_name',width:93},{colId:'material_name',width:243,pinned:'right'},
    {colId:'material_code',width:166},{colId:'product_line_name',pinned:'left'},{colId:'project_code',pinned:'left'},{colId:'progress'}]
  const result=migrate({reportIdentityVersion:1,visible:['material_name','unit_name','bill_no']},keys,current)
  assert.deepEqual(result.columns.filter(c=>c.colId!=='material_code').map(c=>c.colId),current.filter(c=>c.colId!=='material_code').map(c=>c.colId))
  assert.equal(result.columns.find(c=>c.colId==='material_code').pinned,'right')
})

test('omitted name pin inherits current pin while explicit null unpins code',()=>{
  const current=[{colId:'material_name',pinned:'right',width:240},{colId:'material_code',pinned:'left',width:163}]
  const inherited=migrate({columns:[{colId:'material_name',width:224}]},keys,current)
  assert.equal(inherited.columns.find(c=>c.colId==='material_code').pinned,'right')
  assert.deepEqual(inherited.columns.find(c=>c.colId==='material_name'),{colId:'material_name',width:224})
  const explicit=migrate({columns:[{colId:'material_name',pinned:null,width:224}]},keys,current)
  assert.equal(explicit.columns.find(c=>c.colId==='material_code').pinned,null)
})
