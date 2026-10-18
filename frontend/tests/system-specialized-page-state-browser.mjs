import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const kinds=process.env.PMS_SPECIAL_TEST_KIND?[process.env.PMS_SPECIAL_TEST_KIND]:['enum','parameter','sync']
assert.ok(kinds.every(k=>['enum','parameter','sync'].includes(k)))
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
 for(const kind of kinds) {
  const page=await browser.newPage({viewport:{width:1366,height:850}})
  const pending=[],writes=[],errors=[],reads=[];let mode='INITIAL',definitionsFail=false
  const component={enum:'EnumList',parameter:'ParameterList',sync:'SyncTaskList'}[kind]
  const method={enum:'fetchItems',parameter:'load',sync:'fetchTasks'}[kind]
  const rowsKey={enum:'dictItems',parameter:'items',sync:'items'}[kind]
  const result=name=>{
   const rows=!name?[]:[kind==='enum'?{id:1,item_value:'1',item_label:name,status:1,sort:0,reference_count:0,deletable:true}:kind==='parameter'?{code:'fixture.public',name,group:'测试',description:'隔离参数',sensitive:false,configured:true,version:1,value:'test'}:{id:1,archive_id:42,project_code:name,project_name:'隔离项目',status:'failed',status_label:'失败',attempts:1}]
   return kind==='enum'?rows:{items:rows,total:rows.length,query_version:2,worker_enabled:true}
  }
  page.on('pageerror',e=>errors.push(e.message))
  await page.addInitScript(()=>localStorage.setItem('access_token','isolated-specialized-state'))
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname
   if(url.origin!==base)return route.abort()
   if(!path.startsWith('/api/'))return route.continue()
   if(req.method()!=='GET'){writes.push(path);return route.abort()}
   let body=[]
   if(path==='/api/auth/me')body={id:1,username:'fixture',real_name:'隔离验收',permissions:[`system:${kind==='sync'?'sync':kind}:view`]}
   else if(path==='/api/dicts'){
    if(definitionsFail)return route.fulfill({status:503,json:{detail:'隔离模拟定义失败'}})
    body=[1,2].map(id=>({id,dict_code:'fixture_'+id,dict_name:'枚举'+id,description:'隔离枚举',mode:'configurable',bindings:[],item_count:1,allow_add:true}))
   } else if(path==='/api/parameters'||path==='/api/sync-tasks'||/^\/api\/dicts\/\d+\/items$/.test(path)) {
    reads.push({path,mode})
    if(mode==='HOLD'){pending.push(route);return}
    if(mode==='FAIL')return route.fulfill({status:503,json:{detail:'隔离模拟读取失败'}})
    body=result(mode==='EMPTY'?null:mode)
   }
   return route.fulfill({json:body})
  })
  await page.goto(base+'/system/'+kind)
  await expect(page.getByText('INITIAL',{exact:true}).first()).toBeVisible()
  if(kind==='sync') {
   await expect.poll(()=>reads.filter(row=>row.path==='/api/sync-tasks'&&row.mode==='INITIAL').length).toBe(2)
   await expect.poll(()=>page.getByRole('button',{name:'查询',exact:true}).evaluate(el=>{
    let vm=el.__vueParentComponent;while(vm&&vm.type.__name!=='SyncTaskList')vm=vm.parent
    return vm.setupState.loading
   })).toBe(false)
  }
  const invoke=async(operation=method)=>page.getByRole('button',{name:'查询',exact:true}).evaluate((el,{component,operation})=>{
   let vm=el.__vueParentComponent;while(vm&&vm.type.__name!==component)vm=vm.parent
   if(!vm)throw Error('专用列表入口缺失')
   window.specialVm=vm;window.specialRequests||=[]
   window.specialRequests.push(vm.setupState[operation]().catch(()=>undefined))
  },{component,operation})
  if(kind==='enum') {
   definitionsFail=true;await invoke('fetchDicts')
   const definitionsAlert=page.getByRole('alert').filter({hasText:'枚举列表读取失败'})
   await expect(definitionsAlert).toBeVisible()
   await expect(page.locator('.enum-master-item')).toHaveCount(0)
   definitionsFail=false;await definitionsAlert.getByRole('button',{name:'重试',exact:true}).click()
   await expect(page.getByText('INITIAL',{exact:true}).first()).toBeVisible()
  }
  mode='FAIL';await invoke()
  const alert=page.getByRole('alert').filter({has:page.getByRole('button',{name:'重试',exact:true})})
  await expect(alert).toBeVisible();await expect(page.getByText('INITIAL',{exact:true})).toHaveCount(0)
  mode='RETRY';await alert.getByRole('button',{name:'重试',exact:true}).click()
  await expect(page.getByText('RETRY',{exact:true}).first()).toBeVisible()
  mode='HOLD';await invoke()
  if(kind==='enum')await page.locator('.enum-master-item').filter({hasText:'枚举2'}).click()
  else await invoke()
  await expect.poll(()=>pending.length).toBe(2)
  await pending[1].fulfill({json:result('LATEST')});await expect(page.getByText('LATEST',{exact:true}).first()).toBeVisible()
  await pending[0].fulfill({json:result('OLD')});await page.evaluate(()=>Promise.all(window.specialRequests))
  await expect(page.getByText('OLD',{exact:true})).toHaveCount(0)
  if(kind==='sync') {
   const index=pending.length;await invoke();await expect.poll(()=>pending.length).toBe(index+1)
   await page.evaluate(()=>{window.specialVm.setupState.page=2})
   await pending[index].fulfill({json:result('OLD-DURING-DEBOUNCE')})
   await page.evaluate(()=>Promise.all(window.specialRequests))
   await expect(page.getByText('OLD-DURING-DEBOUNCE',{exact:true})).toHaveCount(0)
   await expect.poll(()=>pending.length).toBe(index+2)
   assert.equal(new URL(pending[index+1].request().url()).searchParams.get('page'),'2')
   await pending[index+1].fulfill({json:result('PAGE2')})
   await expect(page.getByText('PAGE2',{exact:true}).first()).toBeVisible()
  }
  if(kind==='parameter') {
   const index=pending.length;await invoke();await expect.poll(()=>pending.length).toBe(index+1)
   await page.evaluate(()=>{let vm=window.specialVm;while(vm.parent)vm=vm.parent;vm.appContext.config.globalProperties.$pinia._s.get('auth').user.permissions=[]})
   await pending[index].fulfill({json:result('AFTER-REVOKE')});await page.evaluate(()=>Promise.all(window.specialRequests))
   assert.equal(await page.evaluate(()=>window.specialVm.setupState.items.length),0)
   await page.evaluate(()=>window.specialVm.appContext.config.globalProperties.$pinia._s.get('auth').user.permissions=['system:parameter:view'])
  }
  mode='EMPTY';await invoke();await page.evaluate(()=>Promise.all(window.specialRequests))
  assert.equal(await page.evaluate(key=>window.specialVm.setupState[key].length,rowsKey),0)
  const index=pending.length;mode='HOLD';await invoke();await expect.poll(()=>pending.length).toBe(index+1)
  await page.evaluate(()=>window.specialVm.proxy.$router.push('/login'))
  await pending[index].fulfill({json:result('AFTER-UNMOUNT')});await page.evaluate(()=>Promise.all(window.specialRequests))
  assert.equal(await page.evaluate(key=>window.specialVm.setupState[key].length,rowsKey),0)
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[])
  console.log(`PASS ${kind}: failure clears stale rows, retry, latest response, empty, unmount; mocked GET only`)
  await page.close()
 }
} finally {await browser.close()}
