import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base='http://127.0.0.1:5174',out='../outputs/archive-draft-management-20261016/session'
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
 const page=await browser.newPage({viewport:{width:1366,height:850}})
 const errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(8000)
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-form-session'))
 let attempts=0,reads=0,fail=true,holdResponse,holdMetadata,releaseMetadata,draftVersion=0,draftPayload={}
 const keys=['archive_category','project_code','project_name','customer','product_line_id','quantity','quantity_unit','manager_id','machine_model','equipment_series','serial_no','remarks','contract_signed_date','contract_ship_date']
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname,method=route.request().method()
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let body=[]
  if(path==='/api/auth/me')body={id:1,username:'fixture',real_name:'本机验收',permissions:['project:archive:view','project:archive:add']}
  else if(path==='/api/users/options')body=[{id:1,real_name:'本机验收'}]
  else if(path==='/api/product-lines/options'||path==='/api/product-lines/labels'||path==='/api/form-drafts/archive-create/product-lines')body={options:[{value:7,label:'8吋Bench'}],label_map:{7:'8吋Bench'}}
  else if(path==='/api/projects/archives/fields'){if(holdMetadata)await new Promise(resolve=>{releaseMetadata=resolve});body={items:keys.map(field_key=>({field_key,label:field_key==='project_name'?'项目名称':field_key,visible:!field_key.startsWith('contract_'),editable:!field_key.startsWith('contract_'),list_available:true,required:field_key==='project_name'}))}}
  else if(path.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'主机'},{value:7,label:'台'}],label_map:{1:'主机',7:'台'}}
  else if(path==='/api/projects/archives/list'){reads++;body={total:0,items:[]}}
  else if(path==='/api/form-drafts/archive-create'&&method==='POST'){draftPayload=route.request().postDataJSON().payload;body={id:route.request().postDataJSON().id,version:++draftVersion,status:'active',payload:draftPayload}}
  else if(path.startsWith('/api/form-drafts/archive-create/')&&path.endsWith('/submit')&&method==='POST'){
   attempts++;await new Promise(resolve=>{holdResponse=resolve})
   if(fail===true)return route.fulfill({status:409,json:{detail:{code:'ARCHIVE_UNIQUE_CONFLICT',field_key:'project_code',message:'项目编号已存在'}}})
   if(fail==='policy')return route.fulfill({status:422,json:{detail:{code:'FIELD_POLICY_VALIDATION_FAILED',fields:[{field_key:'quantity',message:'数量规则已更新，请重新确认'},{field_key:'project_name',message:'项目名称需业务确认'},{field_key:'unknown',message:'不得展示内部字段'}]}}})
   body={id:1,...route.request().postDataJSON()}
  }
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/archive')
 await page.getByRole('button',{name:'新增档案',exact:true}).click()
 const form=page.getByRole('dialog',{name:'新增项目档案',exact:true})
 const save=form.getByRole('button',{name:'正式保存',exact:true}),cancel=form.getByRole('button',{name:'取消',exact:true})
 const code=form.getByRole('textbox',{name:'项目编号',exact:true}),name=form.getByRole('textbox',{name:'项目名称',exact:true})
 await code.fill('LOCAL-SESSION-1')
 await save.click();await expect(form).toContainText('请填写项目名称');assert.equal(attempts,0)
 await name.fill('失败保留草稿')
 await form.getByRole('spinbutton',{name:'数量',exact:true}).fill('0');await save.click()
 await expect(form).toContainText('数量只允许填写正整数');assert.equal(attempts,0)
 await form.getByRole('spinbutton',{name:'数量',exact:true}).fill('1')
 // Call the real Vue handler twice in the same event loop, before asynchronous form validation settles.
 // This reproduces keyboard/programmatic submissions without relying on DOM click timing or button debouncing.
 const handlers=await save.evaluate(el=>{
  let vm=el.__vueParentComponent
  while(vm&&!vm.setupState?.handleSubmit)vm=vm.parent
  if(!vm)throw new Error('缺少真实新增页面提交入口')
  vm.setupState.handleSubmit();vm.setupState.handleSubmit();return true
 })
 assert.equal(handlers,true)
 await expect.poll(()=>attempts).toBe(1)
 await expect(cancel).toBeDisabled();await expect(name).toHaveAttribute('readonly', '')
 holdResponse();await expect(form).toContainText('项目编号已存在')
 await expect(name).toHaveValue('失败保留草稿');await expect(code).toHaveValue('LOCAL-SESSION-1')
 await expect(cancel).toBeEnabled();assert.equal(attempts,1)
 await page.screenshot({path:out+'/failure-keeps-draft.jpg'})
 await cancel.click()
 const confirm=page.getByRole('dialog',{name:'未保存修改',exact:true})
 await expect(confirm).toBeVisible();await confirm.getByRole('button',{name:'继续编辑',exact:true}).click()
 await expect(form).toBeVisible();await expect(name).toHaveValue('失败保留草稿')
 await code.fill('LOCAL-SESSION-2');await name.fill('重试保存')
 fail='policy';holdMetadata=true;await save.click();await expect.poll(()=>attempts).toBe(2)
 holdResponse();await expect.poll(()=>Boolean(releaseMetadata)).toBe(true);await expect(cancel).toBeDisabled();await expect(name).toHaveAttribute('readonly','');holdMetadata=false;releaseMetadata();await expect(form).toContainText('项目名称需业务确认');await expect(form).toContainText('数量规则已更新，请重新确认');await expect(form).not.toContainText('不得展示内部字段')
 await name.fill('修正后的名称');await form.getByRole('spinbutton',{name:'数量',exact:true}).fill('2')
 await expect(form).not.toContainText('项目名称需业务确认');await expect(form).not.toContainText('数量规则已更新，请重新确认')
 fail=false;const before=reads;await save.click();await expect.poll(()=>attempts).toBe(3)
 holdResponse();await expect(form).toBeHidden();await expect.poll(()=>reads).toBeGreaterThan(before)
 await page.getByRole('button',{name:'新增档案',exact:true}).click();await expect(code).toHaveValue('')
 await code.fill('放弃草稿');await cancel.click();await confirm.getByRole('button',{name:'放弃本次修改',exact:true}).click();await expect(form).toBeHidden()
 assert.deepEqual(errors,[])
 console.log('PASS: 必填/数量错误无请求，异步验证双提交仅一次，409留值/定位、422字段错误顺序与改值清除、取消关闭、修改后重试成功并刷新、确认放弃；所有API模拟，真实业务写入0')
} finally {await browser.close()}
