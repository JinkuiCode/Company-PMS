import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const kinds=process.env.PMS_SAVE_TEST_KIND?[process.env.PMS_SAVE_TEST_KIND]:['user','role','enum']
assert.ok(kinds.every(k=>['user','role','enum'].includes(k)))
const browser=await chromium.launch({channel:'msedge',headless:true})
try {for(const kind of kinds){
 const page=await browser.newPage({viewport:{width:1366,height:850}})
 page.setDefaultTimeout(8000)
 const writes=[],pending=[],errors=[]
 let failCache=false,failIdentity=false
 const fixture={
  user:{id:2,username:'FIXTURE-USER',real_name:'隔离员工',email:'fixture@example.invalid',mobile:'',dept_id:4,status:1,role_ids:[1],role_names:['隔离角色']},
  role:{id:2,role_code:'fixture',role_name:'隔离角色',remark:'',data_scope:2,status:1,product_line_ids:[1],home_menu_id:21,home_priority:3},
  enum:{id:51,item_value:'101',item_label:'隔离枚举值',sort:2,status:1,reference_count:1,value_locked:true,deletable:false},
 }
 const definitions=[{id:1,dict_code:'archive_category',dict_name:'隔离类别',description:'模拟枚举',mode:'configurable',allow_add:true,allow_value_edit:false,bindings:[],item_count:1},
                    {id:2,dict_code:'equipment_series',dict_name:'另一枚举',description:'模拟枚举',mode:'configurable',allow_add:true,allow_value_edit:false,bindings:[],item_count:0}]
 const tree=[{id:20,parent_id:0,menu_name:'项目管理',menu_type:'M',status:1,visible:1,children:[
  {id:21,parent_id:20,menu_name:'项目档案',menu_type:'C',permission_code:'project:archive:view',path:'/project/archive',status:1,visible:1,children:[
   {id:22,parent_id:21,menu_name:'新增档案',menu_type:'B',permission_code:'project:archive:add',status:1,visible:1,children:[]},
  ]},
 ]}]
 page.on('pageerror',e=>errors.push(e.message))
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-system-save-session'))
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let body=[]
  if(req.method()!=='GET'){
   assert.ok((kind==='user'&&['/api/users/2','/api/users'].includes(path))||
    (kind==='role'&&['/api/roles/2','/api/roles'].includes(path))||
    (kind==='enum'&&['/api/dicts/items/51','/api/dicts/1/items'].includes(path)),`unexpected mocked write ${path}`)
   writes.push({method:req.method(),path,body:req.postDataJSON()});pending.push(route);return
  }
  if(path==='/api/auth/me'&&failIdentity)return route.fulfill({status:503,json:{detail:'隔离身份刷新失败'}})
  if(path==='/api/auth/me')body={id:1,username:'fixture',permissions:[`system:${kind}:view`,`system:${kind}:add`,`system:${kind}:edit`]}
  else if(path==='/api/users')body={items:[fixture.user],total:1}
  else if(path==='/api/depts/tree')body=[{id:4,dept_name:'隔离部门',children:[]}]
  else if(path==='/api/roles/options')body=[{id:1,role_name:'隔离角色',status:1}]
  else if(path==='/api/roles')body=[fixture.role]
  else if(path==='/api/menus/tree')body=tree
  else if(path==='/api/roles/2/menus')body={menu_ids:[20,21,22]}
  else if(path==='/api/product-lines/role-options')body={items:[{value:1,label:'隔离产品线一'},{value:2,label:'隔离产品线二'}]}
  else if(path==='/api/dicts')body=definitions
  else if(path==='/api/dicts/1/items')body=[fixture.enum]
  else if(path==='/api/dicts/2/items')body=[]
  else if(path.startsWith('/api/dicts/code/')){
   if(failCache)return route.fulfill({status:503,json:{detail:'隔离缓存刷新失败'}})
   body={items:[],all_items:[],label_map:{}}
  }
  return route.fulfill({json:body})
 })
 console.log(kind,'STEP open');await page.goto(base+'/system/'+kind)
 await page.getByRole('button',{name:'编辑',exact:true}).first().click()
 const name=page.getByRole('textbox',{name:{user:'员工姓名',role:'角色名称',enum:'显示名称'}[kind],exact:true})
 const drawer=page.getByRole('dialog').filter({has:name})
 await expect(name).toBeVisible()
 const type={user:'UserFormDrawer',role:'RoleList',enum:'EnumList'}[kind]
 const close={user:'close',role:'closeDialog',enum:'closeItemDialog'}[kind]
 const save={user:'save',role:'handleSubmit',enum:'handleItemSubmit'}[kind]
 const invoke=async(method,count=1)=>name.evaluate((el,{method,count,type})=>{
  let vm=el.__vueParentComponent;while(vm&&vm.type.__name!==type)vm=vm.parent
  assertVm(vm)
  function assertVm(value){if(!value)throw Error('form adapter missing')}
  window.saveVm=vm;window.formRequests||=[]
  for(let i=0;i<count;i++)window.formRequests.push(Promise.resolve(vm.setupState[method]()))
 },{method,count,type})
 const initial={user:'隔离员工',role:'隔离角色',enum:'隔离枚举值'}[kind]
 await expect(name).toHaveValue(initial)
 // Editing a role's existing grants must not be mistaken for a user change.
 await drawer.getByRole('button',{name:'取消',exact:true}).click()
 await expect(name).toHaveCount(0)
 await page.getByRole('button',{name:'编辑',exact:true}).first().click()
 await expect(name).toHaveValue(initial)
 console.log(kind,'STEP dirty close');await name.fill('未保存'+kind)
 if(kind==='user'){
  await invoke(close,2)
 }else await drawer.getByRole('button',{name:'取消',exact:true}).click()
 const confirm=page.getByRole('dialog',{name:'未保存修改',exact:true})
 await expect(confirm).toHaveCount(1)
 await invoke(close);await invoke(save)
 assert.equal(writes.length,0,'确认关闭期间不得提交')
 await confirm.getByRole('button',{name:kind==='user'?'继续编辑':'取消',exact:true}).click()
 await expect(confirm).toHaveCount(0)
 await page.evaluate(()=>Promise.all(window.formRequests));await expect(name).toHaveValue('未保存'+kind)
 await page.evaluate(()=>{window.formNavigation=window.saveVm.proxy.$router.push('/login')})
 await expect(confirm).toBeVisible()
 await confirm.getByRole('button',{name:kind==='user'?'继续编辑':'取消',exact:true}).click()
 await page.evaluate(()=>window.formNavigation);await expect(confirm).toHaveCount(0)
 assert.equal(new URL(page.url()).pathname,'/system/'+kind)
 if(kind==='enum'){
  await name.evaluate(el=>{let vm=el.__vueParentComponent;while(vm&&vm.type.__name!=='EnumList')vm=vm.parent;void vm.setupState.selectDict(2)})
  await expect(confirm).toBeVisible()
  await confirm.getByRole('button',{name:'取消',exact:true}).click();await expect(confirm).toHaveCount(0)
  await expect(drawer.getByRole('heading',{name:'隔离类别',exact:true})).toBeVisible()
 }
 await invoke(close)
 await confirm.getByRole('button',{name:kind==='user'?'关闭':'确定',exact:true}).click()
 await expect(name).toHaveCount(0)
 await page.getByRole('button',{name:'编辑',exact:true}).first().click()
 console.log(kind,'STEP invalid');await name.fill('');await drawer.getByRole('button',{name:'保存',exact:true}).click()
 await expect(page.getByText({user:'请输入员工姓名',role:'请输入角色名称',enum:'请输入显示名称'}[kind],{exact:true}).first()).toBeVisible()
 assert.equal(writes.length,0)
 console.log(kind,'STEP duplicate save');await name.fill('修改'+kind);await invoke(save,2)
 await expect.poll(()=>writes.length).toBe(1)
 await expect(name).toBeDisabled()
 await expect(drawer.getByRole('button',{name:'取消',exact:true})).toBeDisabled()
 await invoke(close)
 await page.evaluate(()=>window.saveVm.proxy.$router.push('/login'))
 assert.equal(new URL(page.url()).pathname,'/system/'+kind)
 if(kind==='user') {
  await name.evaluate(el=>{let vm=el.__vueParentComponent;while(vm&&vm.type.__name!=='UserList')vm=vm.parent;vm.setupState.openUserDialog({id:99,username:'WRONG-TARGET'})})
  await expect(page.getByRole('textbox',{name:'账号（工号）',exact:true})).toHaveValue('FIXTURE-USER')
 }
 const bodies={
  user:{real_name:'修改user',email:'fixture@example.invalid',mobile:null,dept_id:4,role_ids:[1],status:1},
  role:{role_name:'修改role',role_code:'fixture',data_scope:2,product_line_ids:[1],status:1,remark:'',menu_ids:[20,21,22],home_menu_id:21,home_priority:3},
  enum:{item_label:'修改enum',sort:2,status:1},
 }
 if(kind==='role')writes[0].body.menu_ids.sort((a,b)=>a-b)
 assert.deepEqual(writes[0].body,bodies[kind]);assert.equal(writes[0].method,'PUT')
 console.log(kind,'STEP failed reply');await pending[0].fulfill({status:422,json:{detail:[{loc:['body',kind==='user'?'real_name':kind==='role'?'role_name':'item_label'],msg:'隔离字段冲突'}]}})
 await page.evaluate(()=>Promise.all(window.formRequests))
 await expect(name).toBeEnabled();await expect(name).toHaveValue('修改'+kind)
 if(kind==='user')await expect(name).toHaveAttribute('aria-invalid','true')
 await page.screenshot({path:`../outputs/system-save-sessions-20261018/${kind}-failure.png`})
 console.log(kind,'STEP retry');if(kind==='enum')failCache=true
 if(kind==='user'){failIdentity=true;await page.evaluate(()=>window.saveVm.appContext.config.globalProperties.$pinia._s.get('auth').user.id=2)}
 await drawer.getByRole('button',{name:'保存',exact:true}).click()
 await expect.poll(()=>writes.length).toBe(2)
 await pending[1].fulfill({json:{id:kind==='enum'?51:2}})
 await expect(name).toHaveCount(0)
 if(kind==='user'){
  await expect(page.getByText('用户资料已保存，权限刷新失败，请刷新页面',{exact:true})).toBeVisible()
  assert.equal(writes.length,2);failIdentity=false
  await page.evaluate(()=>window.saveVm.appContext.config.globalProperties.$pinia._s.get('auth').user.id=1)
 }
 if(kind==='enum'){
  await expect(page.getByText('枚举值已保存，选项刷新失败，请刷新页面',{exact:true})).toBeVisible()
  assert.equal(writes.length,2,'缓存刷新失败不得重复保存')
  failCache=false
 }
 // Check grant-only dirty tracking; no actual permission write occurs.
 if(kind==='role'){
  console.log(kind,'STEP grants dirty');await page.getByRole('button',{name:'编辑',exact:true}).first().click()
  await expect(name).toBeEnabled();console.log('role grant open');await page.screenshot({path:'../outputs/system-save-sessions-20261018/role-grant-before.png'});await drawer.getByText('隔离产品线二',{exact:true}).click();console.log('role grant checked')
  await invoke(close);console.log('role grant close invoked');await expect(confirm).toBeVisible()
  await confirm.getByRole('button',{name:'取消',exact:true}).click();await expect(confirm).toHaveCount(0)
  await expect(drawer.getByRole('checkbox',{name:'隔离产品线二',exact:true})).toBeChecked()
  await invoke(close);await confirm.getByRole('button',{name:'确定',exact:true}).click();await expect(name).toHaveCount(0)
 }
 if(kind==='role') {
  await page.getByRole('button',{name:'编辑',exact:true}).first().click()
  await drawer.locator('.permission-check-all').click()
  await invoke(close);await expect(confirm).toBeVisible()
  await confirm.getByRole('button',{name:'取消',exact:true}).click();await expect(confirm).toHaveCount(0)
  await invoke(close);await confirm.getByRole('button',{name:'确定',exact:true}).click();await expect(name).toHaveCount(0)
 }
 console.log(kind,'STEP create');await page.getByRole('button',{name:kind==='user'?'新增用户':kind==='role'?'新增角色':'新增值',exact:true}).click()
 await name.fill('新增'+kind)
 if(kind==='user'){
  await page.getByRole('textbox',{name:'账号（工号）',exact:true}).fill('NEW-FIXTURE')
  await page.getByRole('textbox',{name:'邮箱',exact:true}).fill('')
 }
 if(kind==='role')await page.getByRole('textbox',{name:'角色编码',exact:true}).fill('new-fixture')
 await drawer.getByRole('button',{name:kind==='user'?'创建用户':'保存',exact:true}).click()
 await expect.poll(()=>writes.length).toBe(3)
 assert.equal(writes[2].method,'POST')
 assert.equal('password' in writes[2].body,false);assert.equal('item_value' in writes[2].body,false)
 assert.equal(writes[2].path,{user:'/api/users',role:'/api/roles',enum:'/api/dicts/1/items'}[kind])
 await pending[2].fulfill({json:{id:10}});await expect(name).toHaveCount(0)
 await page.getByRole('button',{name:'编辑',exact:true}).first().click()
 await invoke(save,0)
 await page.evaluate(kind=>window.saveVm.appContext.config.globalProperties.$pinia._s.get('auth').user.permissions=[`system:${kind}:view`],kind)
 await invoke(save);await page.evaluate(()=>Promise.all(window.formRequests));assert.equal(writes.length,3,'缺操作权限不写入')
 await invoke(close);await expect(name).toHaveCount(0)
 assert.deepEqual(errors,[])
 if(kind!=='user') {
  await page.getByRole('button',{name:'说明',exact:true}).click()
  await expect(page.getByText(kind==='role'?'配置权限':'选择枚举',{exact:true}).first()).toBeVisible()
  await expect(page.getByRole('link',{name:'新页签打开',exact:true})).toHaveAttribute('href',new RegExp(`/page-guide/${kind==='role'?'roles':'enums'}#`))
 }
 console.log(`PASS ${kind}: shared dirty/close/route, initialization baseline, confirmation/save mutex, validation, busy lock, failure preservation, snapshot and unchanged POST/PUT; all API mocked`)
 await page.close()
}}finally{await browser.close({reason:'isolated acceptance finished'})}
