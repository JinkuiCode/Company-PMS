import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const out='../outputs/system-settings-page-state-20261018'
fs.mkdirSync(out,{recursive:true})
const kinds=process.env.PMS_SETTINGS_TEST_KIND?[process.env.PMS_SETTINGS_TEST_KIND]:['product','policy']
assert.ok(kinds.every(kind=>['product','policy'].includes(kind)))
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 for(const kind of kinds){
  const page=await browser.newPage({viewport:{width:1366,height:850}})
  const errors=[],writes=[],pending=[];let mode='INITIAL'
  const method=kind==='product'?'load':'fetchPolicies',rowsKey=kind==='product'?'items':'rows'
  page.on('pageerror',e=>errors.push(e.message))
  await page.addInitScript(()=>localStorage.setItem('access_token','isolated-settings-state'))
  const row=name=>kind==='product'
   ? {id:1,organization_id:42,organization_code:'FIXTURE',organization_name:'隔离组织',display_name:name,is_enabled:1,sort:0,updated_at:'2026-10-18T10:00:00'}
   : {field_key:'fixture_field',label:name,group:'basic',group_label:'基础',source_type:'detail',value_type:'text',visible:true,editable:true,required:false,list_available:true,visible_cap:true,editable_cap:true,required_cap:true,list_available_cap:true}
  const result=name=>({items:name?[row(name)]:[],total:name?1:0,groups:[{key:'basic',label:'基础'}]})
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname
   if(url.origin!==base)return route.abort()
   if(!path.startsWith('/api/'))return route.continue()
   if(req.method()!=='GET'){writes.push(path);return route.abort()}
   let body=[]
   if(path==='/api/auth/me')body={id:1,username:'fixture',real_name:'隔离验收',permissions:['system:product-line:view','system:field-policy:view']}
   else if(path==='/api/product-lines'||path==='/api/field-policies'){
    if(mode==='HOLD'){pending.push(route);return}
    if(mode==='FAIL')return route.fulfill({status:503,json:{detail:'隔离模拟读取失败'}})
    body=result(mode==='EMPTY'?null:mode)
   }
   return route.fulfill({json:body})
  })
  await page.goto(base+(kind==='product'?'/system/product-line':'/system/field-policy'))
  await expect(page.getByText('INITIAL',{exact:true}).first()).toBeVisible()
  async function fetch(count=1){await page.getByRole('button',{name:'查询',exact:true}).evaluate((el,{method,count,target})=>{
   let vm=el.__vueParentComponent;while(vm&&vm.type.__name!==target)vm=vm.parent
   if(!vm)throw Error('设置页读取入口缺失')
   window.settingsVm=vm;window.settingsRequests||=[]
   for(let i=0;i<count;i++)window.settingsRequests.push(vm.setupState[method]().catch(()=>undefined))
  },{method,count,target:kind==='product'?'ProductLineList':'FieldPolicyList'})}
  if(kind==='policy'){
   mode='HOLD';await fetch()
   await page.locator('.el-segmented').getByText('项目进度',{exact:true}).click()
   await expect.poll(()=>pending.length).toBe(2)
   assert.equal(new URL(pending[0].request().url()).searchParams.get('module'),'project_archive')
   assert.equal(new URL(pending[1].request().url()).searchParams.get('module'),'project_progress')
   await pending[1].fulfill({json:result('LATEST')})
   await expect(page.getByText('LATEST',{exact:true}).first()).toBeVisible()
   await pending[0].fulfill({json:result('OLD-MODULE')})
   await expect(page.getByText('OLD-MODULE',{exact:true})).toHaveCount(0)
   await expect(page.getByText('LATEST',{exact:true}).first()).toBeVisible()
  }
  const previous=kind==='policy'?'LATEST':'INITIAL'
  mode='FAIL';await fetch()
  const alert=page.getByRole('alert').filter({has:page.getByRole('button',{name:'重试',exact:true})})
  await expect(alert).toBeVisible()
  await expect(page.getByText(previous,{exact:true})).toHaveCount(0)
  mode='RETRY';await alert.getByRole('button',{name:'重试',exact:true}).click()
  await expect(page.getByText('RETRY',{exact:true}).first()).toBeVisible()
  await expect(alert).toHaveCount(0)
  mode='EMPTY';await fetch();await page.evaluate(()=>Promise.all(window.settingsRequests))
  assert.equal(await page.evaluate(key=>window.settingsVm.setupState[key].length,rowsKey),0)
  const index=pending.length;mode='HOLD';await fetch();await expect.poll(()=>pending.length).toBe(index+1)
  await page.evaluate(()=>window.settingsVm.proxy.$router.push('/login'))
  await pending[index].fulfill({json:result('AFTER-UNMOUNT')})
  await page.evaluate(()=>Promise.all(window.settingsRequests))
  assert.equal(await page.evaluate(key=>window.settingsVm.setupState[key].some(row=>(row.display_name||row.label)==='AFTER-UNMOUNT'),rowsKey),false)
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[])
  console.log(`PASS ${kind}: ${kind==='policy'?'cross-module response guard, ':''}clear stale rows, error/retry, empty, unmount; mocked GET only`)
  await page.close()
 }
}finally{await browser.close()}
