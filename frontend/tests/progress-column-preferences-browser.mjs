import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base=process.env.PMS_PROGRESS_TEST_BASE || 'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const out='../outputs/progress-column-preferences-20261018'
fs.mkdirSync(out,{recursive:true})
const key='pms_project_progress_list_columns_v2:1'
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
 const page=await browser.newPage({viewport:{width:1366,height:850}})
 const errors=[],writes=[];let owner=1,lastKeys=''
 page.on('pageerror',error=>errors.push(error.message))
 await page.addInitScript(key=>{
  localStorage.setItem('access_token','isolated-progress-preferences')
  if(!sessionStorage.getItem('initialized')){
   localStorage.setItem(key,JSON.stringify({selected_sheet_field_keys:['fixture_notes','removed'],columnState:[
    {colId:'project_code',width:246,pinned:'left'},
    {colId:'sheet:fixture_notes',width:188,hide:false},
    {colId:'sheet:fixture_extra',width:209,pinned:'right',sort:'desc',sortIndex:1},
    {colId:'sheet:removed',width:90},
   ]}))
   sessionStorage.setItem('initialized','1')
  }
 },key)
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  if(req.method()!=='GET'){writes.push(path);return route.abort()}
  let body=[]
  if(path==='/api/auth/me')body={id:owner,username:'fixture',real_name:'隔离验收',permissions:['project:list:view']}
  else if(path==='/api/projects/sheet-fields')body={fields:[
   {key:'fixture_notes',label:'验收备注',group:'progress',value_type:'text',source_type:'detail',list_available:true,visible:true,editable:true},
   {key:'fixture_extra',label:'未选有效列',group:'progress',value_type:'text',source_type:'detail',list_available:true,visible:true,editable:true},
  ],policies:[]}
  else if(path.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'未开始'}],label_map:{1:'未开始'}}
  else if(path==='/api/projects'){
   lastKeys=url.searchParams.get('sheet_field_keys')||''
   body={total:1,items:[{id:1,project_code:'PREF-001',project_name:'偏好隔离验收',status:1,sheet_fields:{fixture_notes:'测试内容'}}]}
  }
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/list')
 await expect(page.getByText('PREF-001',{exact:true}).first()).toBeVisible()
 assert.equal(Math.round(await page.locator('.ag-header-cell[col-id="project_code"]').evaluate(el=>el.getBoundingClientRect().width)),246)
 assert.ok(lastKeys.split(',').includes('fixture_notes'));assert.ok(!lastKeys.split(',').includes('removed'))
 await expect(page.getByText('测试内容',{exact:true})).toBeVisible()
 async function persist(){await page.getByRole('button',{name:'查询',exact:true}).evaluate(el=>{
  let vm=el.__vueParentComponent;while(vm&&!vm.setupState?.persistColumnPreferences)vm=vm.parent
  if(!vm)throw Error('真实列偏好保存入口缺失')
  window.progressPreferenceVm=vm;vm.setupState.persistColumnPreferences()
 })}
 await persist()
 let saved=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key)
 assert.equal(saved.schema_version,1,'进度页必须通过共享版本化存储写入')
 assert.deepEqual(saved.selected_sheet_field_keys,['fixture_notes']);assert.deepEqual(saved.selected_column_keys,['fixture_notes'])
 assert.equal(saved.columnState.find(s=>s.colId==='project_code').width,246)
 assert.ok(!saved.columnState.some(s=>s.colId==='sheet:removed'))
 assert.deepEqual(saved.columnState.find(s=>s.colId==='sheet:fixture_extra'),{colId:'sheet:fixture_extra',width:209,pinned:'right',sort:'desc',sortIndex:1},'普通保存仍须保留当前未勾选的有效旧列布局')
 const valid=JSON.stringify(saved)
 for(const raw of [JSON.stringify({schema_version:99,keep:'future'}),'{bad',JSON.stringify({...saved,owner_id:999})]){
  await page.evaluate(({key,raw})=>localStorage.setItem(key,raw),{key,raw})
  await persist()
  assert.equal(await page.evaluate(key=>localStorage.getItem(key),key),raw,'不支持的缓存不能被普通布局事件覆盖')
 }
 await page.evaluate(({key,valid})=>localStorage.setItem(key,valid),{key,valid})
 owner=2;await page.reload()
 await expect(page.getByText('PREF-001',{exact:true}).first()).toBeVisible()
 assert.ok(!lastKeys.split(',').includes('fixture_notes'),'账号2不能继承账号1列选择')
 assert.equal(await page.evaluate(key=>localStorage.getItem(key),key),valid)
 await page.evaluate(()=>{
  const original=Storage.prototype.setItem
  window.deniedPreferenceWrites=0
  Storage.prototype.setItem=function(k,v){if(k==='pms_project_progress_list_columns_v2:2'){window.deniedPreferenceWrites++;throw Error('模拟写入拒绝')}return original.call(this,k,v)}
 })
 await persist()
 assert.ok(await page.evaluate(()=>window.deniedPreferenceWrites)>0)
 await page.getByRole('button',{name:'查询',exact:true}).click()
 await expect(page.getByText('PREF-001',{exact:true}).first()).toBeVisible()
 await page.addInitScript(()=>{
  const get=Storage.prototype.getItem
  window.deniedPreferenceReads=0
  Storage.prototype.getItem=function(k){if(k==='pms_project_progress_list_columns_v2:2'){window.deniedPreferenceReads++;throw Error('模拟读取拒绝')}return get.call(this,k)}
 })
 await page.reload()
 await expect(page.getByText('PREF-001',{exact:true}).first()).toBeVisible()
 assert.ok(await page.evaluate(()=>window.deniedPreferenceReads)>0)
 await page.screenshot({path:out+'/account-isolation-and-storage-denied.png'})
 assert.deepEqual(writes,[]);assert.deepEqual(errors,[])
 console.log('PASS: legacy selection/width restored; invalid columns removed; v1 dual-key compatibility; future/corrupt/foreign data protected; account isolation; denied storage does not block query; mocked APIs only')
}finally{await browser.close()}
