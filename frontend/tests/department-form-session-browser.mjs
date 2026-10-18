import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
 const page=await browser.newPage({viewport:{width:1366,height:850}})
 const writes=[],pending=[],errors=[];let leadersFail=false
 const dept={id:4,parent_id:0,dept_name:'隔离部门',leader_id:8,leader_label:'隔离负责人',sort:2,status:1,children:[]}
 page.on('pageerror',e=>errors.push(e.message))
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-department-session'))
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let body=[]
  if(path==='/api/auth/me')body={id:1,username:'fixture',permissions:['system:user:view','system:user:add','system:user:edit','system:user:delete']}
  else if(req.method()!=='GET'){
   writes.push({method:req.method(),path,body:req.postDataJSON()})
   assert.ok((req.method()==='PUT'&&path==='/api/depts/4')||(req.method()==='POST'&&path==='/api/depts'),`unexpected mocked write ${path}`)
   pending.push(route);return
  } else if(path==='/api/users')body={items:[{id:8,username:'isolated-owner',real_name:'隔离负责人',dept_id:4,status:1,role_names:[]}],total:1}
  else if(path==='/api/users/options'){
   if(leadersFail)return route.fulfill({status:503,json:{detail:'隔离候选失败'}})
   body=[{id:8,username:'isolated-owner',real_name:'隔离负责人'}]
  } else if(path==='/api/depts/tree')body=[dept]
  return route.fulfill({json:body})
 })
 await page.goto(base+'/system/user')
 await expect(page.getByText('隔离部门',{exact:true}).first()).toBeVisible()
 const invoke=async(method,...args)=>page.getByRole('button',{name:'查询',exact:true}).evaluate((el,{method,args})=>{
  let vm=el.__vueParentComponent;while(vm&&vm.type.__name!=='UserList')vm=vm.parent
  window.deptVm=vm;window.deptRequests||=[]
  window.deptRequests.push(Promise.resolve(vm.setupState[method](...args)))
 },{method,args})
 await invoke('openDeptDialog',dept)
 const name=page.getByRole('textbox',{name:'部门名称',exact:true})
 const drawer=page.getByRole('dialog').filter({has: name})
 await expect(name).toHaveValue('隔离部门')
 await expect(drawer.getByRole('button',{name:'保存',exact:true})).toBeEnabled()
 await name.fill('未保存部门')
 await drawer.getByRole('button',{name:'取消',exact:true}).click()
 const confirm=page.getByRole('dialog').filter({hasText:'放弃尚未保存的部门修改？'})
 await expect(confirm).toBeVisible()
 await invoke('closeDeptDialog');await invoke('handleDeptSubmit')
 await expect(confirm).toHaveCount(1);assert.equal(writes.length,0)
 await confirm.getByRole('button',{name:'取消',exact:true}).click()
 await page.evaluate(()=>Promise.all(window.deptRequests))
 await expect(confirm).toHaveCount(0)
 await expect(name).toHaveValue('未保存部门')
 await invoke('openDeptDialog',{...dept,id:9,dept_name:'另一部门'})
 await expect(confirm).toBeVisible()
 await confirm.getByRole('button',{name:'取消',exact:true}).click()
 await page.evaluate(()=>Promise.all(window.deptRequests));await expect(confirm).toHaveCount(0);await expect(name).toHaveValue('未保存部门')
 await page.evaluate(()=>{window.deptRoute=window.deptVm.proxy.$router.push('/login')})
 await expect(confirm).toBeVisible()
 await confirm.getByRole('button',{name:'取消',exact:true}).click()
 await page.evaluate(()=>window.deptRoute);await expect(confirm).toHaveCount(0)
 assert.equal(new URL(page.url()).pathname,'/system/user')
 await drawer.getByRole('button',{name:'取消',exact:true}).click()
 await confirm.getByRole('button',{name:'确定',exact:true}).click()
 await expect(name).toHaveCount(0)
 await invoke('openDeptDialog',dept)
 await expect(name).toHaveValue('隔离部门')
 await name.fill('');await drawer.getByRole('button',{name:'保存',exact:true}).click()
 await expect(page.getByText('请输入部门名称',{exact:true})).toBeVisible();assert.equal(writes.length,0)
 await name.fill('修改部门')
 await invoke('handleDeptSubmit');await invoke('handleDeptSubmit')
 await expect.poll(()=>writes.length).toBe(1)
 await expect(name).toBeDisabled();await expect(drawer.getByRole('button',{name:'取消',exact:true})).toBeDisabled()
 await invoke('openDeptDialog',{...dept,id:9,dept_name:'错目标'})
 await page.evaluate(()=>window.deptVm.proxy.$router.push('/login'))
 assert.equal(new URL(page.url()).pathname,'/system/user')
 await invoke('closeDeptDialog')
 assert.deepEqual(writes[0],{method:'PUT',path:'/api/depts/4',body:{id:4,parent_id:0,dept_name:'修改部门',leader_id:8,sort:2,status:1}})
 await pending[0].fulfill({status:409,json:{detail:'隔离保存冲突'}})
 await page.evaluate(()=>Promise.all(window.deptRequests))
 await expect(name).toBeEnabled();await expect(name).toHaveValue('修改部门')
 await page.screenshot({path:'../outputs/department-form-session-20261018/conflict.png'})
 await drawer.getByRole('button',{name:'保存',exact:true}).click()
 await expect.poll(()=>writes.length).toBe(2)
 await pending[1].fulfill({json:{...dept,dept_name:'修改部门'}})
 await expect(name).toHaveCount(0)
 leadersFail=true;await invoke('openDeptDialog',null,4)
 await expect(page.getByText('无法加载负责人选项，请重试',{exact:true})).toBeVisible()
 await expect(drawer.getByRole('button',{name:'保存',exact:true})).toBeDisabled()
 await invoke('handleDeptSubmit');await page.evaluate(()=>Promise.all(window.deptRequests));assert.equal(writes.length,2)
 leadersFail=false;await drawer.getByRole('button',{name:'重试',exact:true}).click()
 await expect(drawer.getByRole('button',{name:'保存',exact:true})).toBeEnabled()
 await name.fill('新隔离部门')
 await drawer.locator('[aria-label="部门负责人"] .el-select__wrapper').click()
 await page.getByRole('option',{name:'隔离负责人（isolated-owner）',exact:true}).click()
 await drawer.getByRole('button',{name:'保存',exact:true}).click()
 await expect.poll(()=>writes.length).toBe(3)
 assert.deepEqual(writes[2],{method:'POST',path:'/api/depts',body:{id:0,parent_id:4,dept_name:'新隔离部门',leader_id:8,sort:0,status:1}})
 await pending[2].fulfill({json:{id:5}});await expect(name).toHaveCount(0)
 await invoke('openDeptDialog',dept)
 await page.evaluate(()=>window.deptVm.appContext.config.globalProperties.$pinia._s.get('auth').user.permissions=['system:user:view'])
 await invoke('handleDeptSubmit');await page.evaluate(()=>Promise.all(window.deptRequests))
 assert.equal(writes.length,3);assert.deepEqual(errors,[])
 console.log('PASS department form: dirty close/switch, single confirmation, validation/save mutex, fixed snapshot, busy route/input lock, failure retry, candidate failure/retry, original POST/PUT, no-permission rejection; all API mocked')
} finally {await browser.close()}
