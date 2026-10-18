import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const out='../outputs/progress-form-session-20261018'
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1366,height:850}})
 const errors=[],posts=[],otherWrites=[],metadata=[];let holdMetadata=false
 page.on('pageerror',error=>errors.push(error.message))
 const policies=['archive_id','dept_id','pm_id','budget','project_start_date','original_planned_ship_date'].map(field_key=>({field_key,label:field_key,source_type:'project',value_type:'text',visible:true,editable:true,required:['archive_id','dept_id','pm_id'].includes(field_key)}))
 policies.push({field_key:'fixture_project',label:'项目业务补充',source_type:'project',value_type:'text',visible:true,editable:true,required:true})
 policies.push({field_key:'computed_fixture',label:'计算字段',source_type:'computed',value_type:'text',visible:true,editable:true,required:false})
 const fields={fields:[
  {key:'fixture_detail',label:'明细业务补充',group:'progress',value_type:'text',source_type:'detail',visible:true,editable:true,required:true,list_available:true},
  {key:'computed_detail',label:'计算明细字段',group:'progress',value_type:'text',source_type:'detail',computed:true,visible:true,editable:true,required:true},
 ],policies}
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-project-create'))
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  if(req.method()==='POST'&&path==='/api/projects'){posts.push({route,body:req.postDataJSON()});return}
  if(req.method()!=='GET'){otherWrites.push(path);return route.abort()}
  let body=[]
  if(path==='/api/auth/me')body={id:1,username:'fixture',real_name:'隔离验收',permissions:['project:list:view','project:list:add']}
  else if(path==='/api/projects')body={items:[],total:0}
  else if(path==='/api/projects/archives/options')body=[{id:1,project_code:'PMS-ISOLATED',project_name:'隔离项目档案'}]
  else if(path==='/api/depts/options')body=[{id:1,dept_name:'测试部门',parent_id:null}]
  else if(path==='/api/users/options')body=[{id:1,real_name:'测试负责人'}]
  else if(path.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'未开始'}],label_map:{1:'未开始'}}
  else if(path==='/api/projects/sheet-fields'){
   if(holdMetadata){metadata.push(route);return}
   body=fields
  }
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/list')
 await expect(page.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
 await expect(page.getByRole('button',{name:'说明',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'查询',exact:true}).evaluate(el=>{
  let vm=el.__vueParentComponent;while(vm&&!vm.setupState?.handleSubmit)vm=vm.parent
  if(!vm)throw Error('真实项目表单入口缺失');window.projectCreateVm=vm
 })
 assert.equal(await page.evaluate(()=>window.projectCreateVm.setupState.isProgressPolicyEditable('computed_fixture')),false,'计算来源不能因服务端可编辑标记而开放')
 const form=page.locator('.project-create-dialog')
 const cancel=form.getByRole('button',{name:'取消',exact:true})
 const save=form.getByRole('button',{name:'确定',exact:true})
 await page.getByRole('button',{name:'新增项目',exact:true}).click()
 await expect(form.getByRole('textbox',{name:'计算明细字段',exact:true})).toHaveCount(0)
 await cancel.click();await expect(form).toBeHidden()
 await page.getByRole('button',{name:'新增项目',exact:true}).click()
 await page.evaluate(()=>{window.projectCreateVm.setupState.form.budget=10})
 await cancel.click()
 const confirm=page.getByRole('dialog',{name:'未保存的内容',exact:true})
 await expect(confirm).toBeVisible()
 await confirm.getByRole('button',{name:'继续填写',exact:true}).click()
 await expect(form).toBeVisible()
 assert.equal(await page.evaluate(()=>window.projectCreateVm.setupState.form.budget),10)
 await cancel.click();await confirm.getByRole('button',{name:'放弃修改',exact:true}).click()
 await expect(form).toBeHidden()
 await page.getByRole('button',{name:'新增项目',exact:true}).click()
 await save.click()
 await expect(form.getByText('请选择项目档案',{exact:true})).toBeVisible()
 assert.equal(posts.length,0,'必输不完整不能提交')
 await page.evaluate(()=>{
  const s=window.projectCreateVm.setupState
  Object.assign(s.form,{archive_id:1,dept_id:1,pm_id:1,budget:10,project_values:{fixture_project:'项目补充'},sheet_values:{fixture_detail:'明细补充'}})
  s.onArchiveChange(1)
  window.projectCreateSubmissions=[s.handleSubmit(),s.handleSubmit()]
 })
 await expect.poll(()=>posts.length).toBe(1)
 await page.evaluate(()=>window.projectCreateSubmissions[1])
 await expect(save).toBeDisabled();await expect(cancel).toBeDisabled()
 await expect(form.getByRole('spinbutton',{name:'预算',exact:true})).toBeDisabled()
 await page.evaluate(async()=>{await window.projectCreateVm.proxy.$router.push('/login')})
 await expect(page).toHaveURL(base+'/project/list')
 holdMetadata=true
 await posts[0].route.fulfill({status:422,json:{detail:{code:'FIELD_POLICY_VALIDATION_FAILED',fields:[
  {field_key:'budget',message:'预算校验失败'},
  {field_key:'pm_id',message:'负责人已变化，请重新选择'},
  {field_key:'fixture_project',message:'项目补充校验失败'},
  {field_key:'fixture_detail',message:'明细补充校验失败'},
  {field_key:'unknown_field',message:'未知字段不应放进表单'},
 ]}}})
 await expect.poll(()=>metadata.length).toBe(1)
 await expect(save).toBeDisabled()
 holdMetadata=false;await metadata[0].fulfill({json:fields})
 await expect(save).toBeEnabled()
 fs.writeFileSync(out+'/error-state.json',JSON.stringify(await page.evaluate(()=>({
  errors:{...window.projectCreateVm.setupState.projectCreateServerErrors},
  phase:window.projectCreateVm.setupState.projectCreateSession.phase.value,
  form:{...window.projectCreateVm.setupState.form},
  visible:window.projectCreateVm.setupState.isProgressPolicyVisible('pm_id'),
 })),null,2))
 await page.screenshot({path:out+'/error-state.png'})
 await expect(form.getByText('负责人已变化，请重新选择',{exact:true})).toBeVisible()
 await expect(form.getByText('预算校验失败',{exact:true})).toBeVisible()
 await expect(form.getByText('未知字段不应放进表单',{exact:true})).toHaveCount(0)
 assert.deepEqual(await page.evaluate(()=>Object.keys(window.projectCreateVm.setupState.projectCreateServerErrors)),['pm_id','budget','project_values.fixture_project','sheet_values.fixture_detail'])
 for(const [label,id] of [['项目业务补充','project-required-fixture_project-error'],['明细业务补充','sheet-required-fixture_detail-error']]){
  const input=form.getByRole('textbox',{name:label,exact:true})
  await expect(input).toHaveAttribute('aria-invalid','true')
  await expect(input).toHaveAttribute('aria-describedby',id)
 }
 assert.equal(await page.evaluate(()=>window.projectCreateVm.setupState.form.budget),10)
 await page.screenshot({path:out+'/structured-errors.png'})
 await page.evaluate(()=>{window.projectCreateVm.setupState.form.budget=11})
 await save.click();await expect.poll(()=>posts.length).toBe(2)
 assert.equal(posts[1].body.budget,11);assert.equal(posts[1].body.archive_id,1)
 await posts[1].route.fulfill({status:422,json:{detail:[
  {loc:['body','end_date'],msg:'结束日期格式无效'},
  {loc:['body','start_date'],msg:'开始日期格式无效'},
 ]}})
 await expect(save).toBeEnabled()
 await expect(form.getByText('开始日期格式无效',{exact:true})).toBeVisible()
 await expect(form.getByText('结束日期格式无效',{exact:true})).toBeVisible()
 assert.deepEqual(await page.evaluate(()=>Object.keys(window.projectCreateVm.setupState.projectCreateServerErrors)),['start_date','end_date'])
 await page.evaluate(()=>Object.assign(window.projectCreateVm.setupState.form,{start_date:'2026-10-18',end_date:'2026-10-19'}))
 await save.click();await expect.poll(()=>posts.length).toBe(3)
 await posts[2].route.fulfill({json:{id:99,...posts[2].body}})
 await expect(form).toBeHidden()
 assert.equal(posts.length,3);assert.deepEqual(otherWrites,[]);assert.deepEqual(errors,[])
 console.log('PASS: clean/dirty close, invalid form, duplicate submit, busy input/navigation lock, async 422 projection, retained draft and successful retry; all APIs mocked')
}finally{await browser.close()}
