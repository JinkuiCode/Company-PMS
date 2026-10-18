import {chromium, expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

// Isolated engineering fixture: no real login, business reads or writes.
const base = process.env.PMS_PROGRESS_TEST_BASE || 'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1','隔离测试只允许本机入口')
const out = '../outputs/progress-page-load-20261018'
fs.mkdirSync(out, {recursive:true})
const browser = await chromium.launch({channel:'msedge',headless:true})
try {
 for (const kind of ['projects','tasks']) {
  const page = await browser.newPage({viewport:{width:1366,height:850}})
  page.setDefaultTimeout(8000)
  await page.addInitScript(() => localStorage.setItem('access_token','isolated-progress-page-load'))
  const errors=[], writes=[], pending=[]
  page.on('pageerror',error=>errors.push(error.message))
  let mode='INITIAL', listRequests=0
  const row = name => kind==='projects'
   ? {id:1,project_code:name,project_name:name,dept_id:1,pm_id:1,status:1,sheet_fields:{}}
   : {id:1,task_name:name,project_id:1,status:1,progress:0,sort:1}
  const result = name => kind==='projects'
   ? {items:name?[row(name)]:[],total:name?1:0}
   : name?[row(name)]:[]
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname
   if (url.origin!==base) return route.abort()
   if (!path.startsWith('/api/')) return route.continue()
   if (req.method()!=='GET') { writes.push(path); return route.abort() }
   let body=[]
   if(path==='/api/auth/me') body={id:1,username:'fixture',real_name:'隔离验收',permissions:['project:list:view']}
   else if(path.startsWith('/api/document-history/')) body={total:0,items:[],actions:[]}
   else if(path==='/api/projects/sheet-fields') body={groups:[],policies:[]}
   else if(path.startsWith('/api/dicts/code/')) body={items:[{value:1,label:'未开始'}],label_map:{1:'未开始'}}
   else if(path==='/api/projects' || path==='/api/projects/1/tasks') {
    listRequests++
    if(mode==='HOLD'){pending.push(route);return}
    if(mode==='FAIL')return route.fulfill({status:503,json:{detail:'隔离模拟读取失败'}})
    body=result(mode==='EMPTY'?null:mode)
   }
   return route.fulfill({json:body})
  })
  await page.goto(base+(kind==='projects'?'/project/list':'/project/1/progress?name=隔离项目'))
  await expect(page.getByText('INITIAL',{exact:true}).first()).toBeVisible()
  const method=kind==='projects'?'fetchList':'fetchTasks'
  async function fetch(count=1) {
   await page.getByRole('button',{name:'查询',exact:true}).evaluate((el,{method,count})=>{
    let vm=el.__vueParentComponent
    while(vm&&!vm.setupState?.[method])vm=vm.parent
    if(!vm)throw Error('真实页面加载入口缺失')
    window.progressFixtureVm=vm
    window.progressFixtureRequests ||= []
    for(let i=0;i<count;i++)window.progressFixtureRequests.push(vm.setupState[method]())
   },{method,count})
  }
  mode='FAIL';await fetch()
  const alert=page.locator('.pms-list-load-error[role="alert"]')
  await expect(alert).toContainText('加载失败')
  await expect(page.getByText('INITIAL',{exact:true})).toHaveCount(0)
  await page.screenshot({path:`${out}/${kind}-failure.png`})
  mode='RETRY';await alert.getByRole('button',{name:'重试',exact:true}).click()
  await expect(page.getByText('RETRY',{exact:true}).first()).toBeVisible()
  await expect(alert).toBeHidden()
  mode='HOLD';await fetch(2);await expect.poll(()=>pending.length).toBe(2)
  await pending[1].fulfill({json:result('LATEST')})
  await expect(page.getByText('LATEST',{exact:true}).first()).toBeVisible()
  await pending[0].fulfill({json:result('STALE')})
  await expect(page.getByText('STALE',{exact:true})).toHaveCount(0)
  await expect(page.getByText('LATEST',{exact:true}).first()).toBeVisible()
  await fetch(2);await expect.poll(()=>pending.length).toBe(4)
  await pending[3].fulfill({json:result('LATEST-AGAIN')})
  await expect(page.getByText('LATEST-AGAIN',{exact:true}).first()).toBeVisible()
  await pending[2].fulfill({status:503,json:{detail:'迟到旧错误'}})
  await expect(alert).toBeHidden()
  await expect(page.getByText('LATEST-AGAIN',{exact:true}).first()).toBeVisible()
  if(kind==='tasks') {
   await page.getByRole('button',{name:'记录',exact:true}).click()
   await expect(page.getByText('LATEST-AGAIN · 操作记录',{exact:true})).toBeVisible()
   await page.evaluate(()=>{
    const vm=window.progressFixtureVm
    window.progressHistoryRevision=vm.setupState.taskHistoryRevision
    const select=vm.setupState.taskHistorySwitch.select
    let once=true
    vm.setupState.taskHistorySwitch.select=async row=>{
     await select(row)
     if(once){once=false;window.progressHistoryEntered=true;await new Promise(resolve=>{window.releaseProgressHistory=resolve})}
    }
   })
   mode='HISTORY-OLD';await fetch()
   await expect.poll(()=>page.evaluate(()=>window.progressHistoryEntered)).toBe(true)
   mode='HOLD';const historyIndex=pending.length
   await fetch();await expect.poll(()=>pending.length).toBe(historyIndex+1)
   await page.evaluate(async()=>{
    window.releaseProgressHistory()
    await window.progressFixtureRequests.at(-2)
   })
   assert.deepEqual(await page.evaluate(()=>({
    loading:window.progressFixtureVm.setupState.tasksState.loading.value,
    unchanged:window.progressFixtureVm.setupState.taskHistoryRevision===window.progressHistoryRevision,
   })),{loading:true,unchanged:true},'旧历史刷新不能结束新查询或增加刷新代次')
   await pending[historyIndex].fulfill({json:result('HISTORY-LATEST')})
   await expect(page.getByText('HISTORY-LATEST · 操作记录',{exact:true})).toBeVisible()
   await page.getByRole('button',{name:'关闭',exact:true}).click()
   await expect(page.getByText('HISTORY-LATEST · 操作记录',{exact:true})).toHaveCount(0)
  }
  mode='EMPTY';await fetch()
  await expect(page.locator('.ag-center-cols-container .ag-row')).toHaveCount(0)
  await expect(page.locator('.ag-overlay-loading-center')).toHaveCount(0)
  await expect(alert).toBeHidden()
  await page.screenshot({path:`${out}/${kind}-empty.png`})
  mode='HOLD';const unmountIndex=pending.length
  await fetch();await expect.poll(()=>pending.length).toBe(unmountIndex+1)
  await page.evaluate(()=>window.progressFixtureVm.proxy.$router.push('/login'))
  await expect(page).toHaveURL(base+'/login')
  await pending[unmountIndex].fulfill({json:result('AFTER-UNMOUNT')})
  await page.evaluate(()=>Promise.all(window.progressFixtureRequests))
  assert.equal(await page.evaluate(()=>window.progressFixtureVm.setupState.rowData.some(row=>(row.project_code||row.task_name)==='AFTER-UNMOUNT')),false)
  assert.ok(listRequests>=9)
  assert.deepEqual(writes,[],'隔离验收禁止真实或模拟业务写入')
  assert.deepEqual(errors,[])
  console.log(`PASS ${kind}: failure/retry, empty, late success/error, history race (tasks) and unmount; all APIs mocked`)
  await page.close()
 }
} finally { await browser.close() }
