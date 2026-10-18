import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const browser=await chromium.launch({channel:'msedge',headless:true})
const kinds=process.env.PMS_IDENTITY_TEST_KIND?[process.env.PMS_IDENTITY_TEST_KIND]:['user','role']
assert.ok(kinds.every(kind=>['user','role'].includes(kind)))
try {
 for(const kind of kinds) {
  const page=await browser.newPage({viewport:{width:1366,height:850}})
  const pending=[],writes=[],errors=[];let mode='INITIAL'
  const method=kind==='user'?'fetchUserList':'fetchList',rowsKey=kind==='user'?'userList':'roleList'
  const result=name=>{
   const rows=name?[kind==='user'?{id:1,username:name,real_name:'隔离人员',status:1,role_names:[]}:{id:1,role_name:name,role_code:'fixture',status:1,data_scope:1}]:[]
   return kind==='user'?{items:rows,total:rows.length}:rows
  }
  page.on('pageerror',error=>errors.push(error.message))
  await page.addInitScript(()=>localStorage.setItem('access_token','isolated-identity-state'))
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname
   if(url.origin!==base)return route.abort()
   if(!path.startsWith('/api/'))return route.continue()
   if(req.method()!=='GET'){writes.push(path);return route.abort()}
   let body=[]
   if(path==='/api/auth/me')body={id:1,username:'fixture',real_name:'隔离验收',permissions:[`system:${kind}:view`]}
   else if(path==='/api/'+(kind==='user'?'users':'roles')){
    if(mode==='HOLD'){pending.push(route);return}
    if(mode==='FAIL')return route.fulfill({status:503,json:{detail:'隔离模拟读取失败'}})
    body=result(mode==='EMPTY'?null:mode)
   } else if(path.includes('product-lines'))body={items:[],total:0}
   return route.fulfill({json:body})
  })
  await page.goto(base+'/system/'+kind)
  await expect(page.getByText('INITIAL',{exact:true}).first()).toBeVisible()
  const fetch=async()=>page.getByRole('button',{name:'查询',exact:true}).evaluate((el,{target,method})=>{
   let vm=el.__vueParentComponent;while(vm&&vm.type.__name!==target)vm=vm.parent
   if(!vm)throw Error('身份列表读取入口缺失')
   window.identityVm=vm;window.identityRequests||=[]
   window.identityRequests.push(vm.setupState[method]().catch(()=>undefined))
  },{target:kind==='user'?'UserList':'RoleList',method})
  mode='FAIL';await fetch()
  const alert=page.getByRole('alert').filter({has:page.getByRole('button',{name:'重试',exact:true})})
  await expect(alert).toBeVisible()
  await expect(page.getByText('INITIAL',{exact:true})).toHaveCount(0)
  mode='RETRY';await alert.getByRole('button',{name:'重试',exact:true}).click()
  await expect(page.getByText('RETRY',{exact:true}).first()).toBeVisible()
  mode='HOLD';await fetch();await fetch();await expect.poll(()=>pending.length).toBe(2)
  await pending[1].fulfill({json:result('LATEST')});await expect(page.getByText('LATEST',{exact:true}).first()).toBeVisible()
  await pending[0].fulfill({json:result('OLD')});await page.evaluate(()=>Promise.all(window.identityRequests))
  await expect(page.getByText('OLD',{exact:true})).toHaveCount(0)
  await expect(page.getByText('LATEST',{exact:true}).first()).toBeVisible()
  mode='EMPTY';await fetch();await page.evaluate(()=>Promise.all(window.identityRequests))
  assert.equal(await page.evaluate(key=>window.identityVm.setupState[key].length,rowsKey),0)
  mode='HOLD';await fetch();await expect.poll(()=>pending.length).toBe(3)
  await page.evaluate(()=>window.identityVm.proxy.$router.push('/login'))
  await pending[2].fulfill({json:result('AFTER-UNMOUNT')});await page.evaluate(()=>Promise.all(window.identityRequests))
  assert.equal(await page.evaluate(key=>window.identityVm.setupState[key].length,rowsKey),0)
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[])
  console.log(`PASS ${kind}: failure/retry, latest query only, empty and unmount; mocked GET only`)
  await page.close()
 }
} finally {await browser.close()}
