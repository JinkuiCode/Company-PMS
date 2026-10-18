import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const out='../outputs/system-readonly-page-state-20261018'
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
const kinds=process.env.PMS_READONLY_TEST_KIND?[process.env.PMS_READONLY_TEST_KIND]:['catalog','audit']
assert.ok(kinds.every(kind=>['catalog','audit'].includes(kind)))
try{
 for(const kind of kinds){
  const page=await browser.newPage({viewport:{width:1366,height:850}})
  const errors=[],writes=[],pending=[];let mode='INITIAL'
  const method=kind==='catalog'?'fetchCatalog':'fetchLogs'
  page.on('pageerror',e=>errors.push(e.message))
  await page.addInitScript(()=>localStorage.setItem('access_token','isolated-readonly-state'))
  const row=name=>kind==='catalog'
   ? {module:'fixture',module_name:'隔离模块',group:'基础',field_name:name,field_code:'field_1',value_type:'text',source_type:'database',editable:false,computed:false,description:'测试字段'}
   : {id:1,module:'fixture',action:'update',entity_type:'project',entity_id:'1',entity_name:name,operator_name:'隔离验收',status:'success',summary:'测试事件',created_at:'2026-10-18T10:00:00',diff_items:[]}
  const result=(name,total=name?1:0)=>({items:name?[row(name)]:[],total,modules:[],actions:[],query_version:2})
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname
   if(url.origin!==base)return route.abort()
   if(!path.startsWith('/api/'))return route.continue()
   if(req.method()!=='GET'){writes.push(path);return route.abort()}
   let body=[]
   if(path==='/api/auth/me')body={id:1,username:'fixture',real_name:'隔离验收',permissions:['system:dict:view','system:operation-log:view']}
   else if(path==='/api/field-catalog'||path==='/api/operation-logs'){
    if(mode==='HOLD'){pending.push(route);return}
    if(mode==='FAIL')return route.fulfill({status:503,json:{detail:'隔离模拟读取失败'}})
    if(mode==='MANY'){
     const p=Number(url.searchParams.get('page')||1),size=Number(url.searchParams.get('page_size')||200)
     body={...result(null,300),items:Array.from({length:Math.min(size,Math.max(0,300-(p-1)*size))},(_,i)=>({...row('MANY-'+((p-1)*size+i)),field_code:'field_'+((p-1)*size+i)}))}
    }else body=result(mode==='EMPTY'?null:mode,mode==='HISTORY-OLD'?15:mode==='EMPTY'?0:1)
   }
   return route.fulfill({json:body})
  })
  await page.goto(base+(kind==='catalog'?'/system/dict':'/system/operation-log'))
  await expect(page.getByText('INITIAL',{exact:true}).first()).toBeVisible()
  async function fetch(count=1){await page.getByRole('button',{name:'刷新',exact:true}).evaluate((el,{method,count})=>{
   let vm=el.__vueParentComponent;while(vm&&!vm.setupState?.[method])vm=vm.parent
   if(!vm)throw Error('只读列表入口缺失')
   window.readonlyVm=vm;window.readonlyRequests||=[]
   for(let i=0;i<count;i++)window.readonlyRequests.push(vm.setupState[method]())
  },{method,count})}
  mode='FAIL';await fetch()
  await expect(page.locator('p[role="alert"]')).toBeVisible()
  await expect(page.getByText('INITIAL',{exact:true})).toHaveCount(0)
  mode='RETRY';await page.getByRole('button',{name:'刷新',exact:true}).click()
  await expect(page.getByText('RETRY',{exact:true}).first()).toBeVisible()
  mode='HOLD';await fetch(2);await expect.poll(()=>pending.length).toBe(2)
  await pending[1].fulfill({json:result('LATEST')})
  await expect(page.getByText('LATEST',{exact:true}).first()).toBeVisible()
  await pending[0].fulfill({status:503,json:{detail:'迟到旧错误'}})
  await expect(page.locator('p[role="alert"]')).toHaveCount(0)
  if(kind==='audit'){
   await page.getByRole('button',{name:'详情',exact:true}).click()
   await expect(page.getByRole('dialog',{name:'操作详情',exact:true})).toBeVisible()
   await page.evaluate(()=>{
    const select=window.readonlyVm.setupState.detailSwitch.select
    let once=true
    window.readonlyVm.setupState.detailSwitch.select=async row=>{
     await select(row)
     if(once){once=false;window.historyEntered=true;await new Promise(resolve=>{window.releaseHistory=resolve})}
    }
   })
   mode='HISTORY-OLD';await fetch()
   await expect.poll(()=>page.evaluate(()=>window.historyEntered)).toBe(true)
   const totalBefore=await page.evaluate(()=>window.readonlyVm.setupState.total)
   mode='HOLD';await fetch();await expect.poll(()=>pending.length).toBe(3)
   await page.evaluate(async()=>{window.releaseHistory();await window.readonlyRequests.at(-2)})
   assert.equal(await page.evaluate(()=>window.readonlyVm.setupState.total),totalBefore,'旧详情await结束不能在新查询期间回写总数')
   await pending[2].fulfill({json:result('HISTORY-LATEST')})
   await expect(page.getByRole('dialog',{name:'操作详情'}).getByText('HISTORY-LATEST',{exact:true})).toBeVisible()
   await page.getByRole('button',{name:'关闭操作详情',exact:true}).click()
  }else{
   mode='MANY';await fetch();await page.evaluate(()=>Promise.all(window.readonlyRequests))
   assert.equal(await page.evaluate(()=>window.readonlyVm.setupState.rows.length),300)
   await page.evaluate(()=>{window.readonlyVm.setupState.page=5})
   await fetch();await page.evaluate(()=>Promise.all(window.readonlyRequests))
   assert.equal(await page.evaluate(()=>window.readonlyVm.setupState.page),5,'完整读取成功后的页码不能按加载期间空视图错误重置')
  }
  mode='EMPTY';await fetch();await page.evaluate(()=>Promise.all(window.readonlyRequests))
  assert.equal(await page.evaluate(kind=>window.readonlyVm.setupState[kind==='catalog'?'rows':'logs'].length,kind),0)
  await expect(page.locator('p[role="alert"]')).toHaveCount(0)
  const index=pending.length;mode='HOLD';await fetch();await expect.poll(()=>pending.length).toBe(index+1)
  await page.evaluate(()=>window.readonlyVm.proxy.$router.push('/login'))
  await pending[index].fulfill({json:result('AFTER-UNMOUNT')})
  await page.evaluate(()=>Promise.all(window.readonlyRequests))
  assert.equal(await page.evaluate(kind=>window.readonlyVm.setupState[kind==='catalog'?'rows':'logs'].some(row=>(row.field_name||row.entity_name)==='AFTER-UNMOUNT'),kind),false,'卸载必须废弃未完成读取')
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[])
  console.log(`PASS ${kind}: retry, stale error, empty, unmount and ${kind==='audit'?'history total race':'complete pagination/readiness'}`)
  await page.close()
 }
}finally{await browser.close()}
