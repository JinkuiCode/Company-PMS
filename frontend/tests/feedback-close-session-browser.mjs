import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1366,height:850}}),writes=[],errors=[]
 const options={feedback_type:[[1,'问题'],[2,'需求']],feedback_module:[[1,'项目档案']],feedback_issue_category:[[1,'界面体验']],feedback_request_category:[[1,'功能建议']],feedback_impact:[[1,'不影响正常使用']],feedback_status:[[1,'待处理'],[5,'已完成']],feedback_outcome:[[1,'已交付']],feedback_cause:[[1,'功能修复']]}
 page.on('pageerror',error=>errors.push(error.message))
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-feedback-close-fixture'))
 await page.route('**/*',async route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname
  if(u.origin!==base)return route.abort()
  if(!p.startsWith('/api/'))return route.continue()
  let body=[]
  if(p==='/api/auth/me')body={id:1,username:'fixture',real_name:'隔离测试',email:'fixture@example.invalid',permissions:['feedback:view','feedback:add']}
  else if(p.startsWith('/api/dicts/code/')){const code=p.split('/').at(-1),items=(options[code]||[]).map(([value,label])=>({value:String(value),label,status:1}));body={dict_code:code,items,all_items:items,label_map:Object.fromEntries(items.map(x=>[x.value,x.label]))}}
  else if(p==='/api/feedback/statistics')body={total:0,open:0,completed:0,statuses:{},modules:[],categories:[]}
  else if(p==='/api/feedback'&&req.method()==='GET')body={items:[],total:0,query_version:1}
  else if(req.method()!=='GET'){
   assert.equal(p,'/api/feedback');assert.equal(req.method(),'POST');const data=req.postDataJSON();writes.push(data);body={...data,id:31,version:1,report_no:'FIXTURE-ONLY',author_name:'隔离测试',attachments:[],followups:[]}
  }
  return route.fulfill({json:body})
 })
 await page.goto(base+'/feedback')
 const add=page.getByRole('button',{name:'新增提报',exact:true});await expect(add).toBeEnabled();await add.click()
 const dialog=page.getByRole('dialog',{name:'新增提报',exact:true}),title=dialog.getByRole('textbox',{name:'标题',exact:true})
 await title.fill('仅隔离模拟，未保存')
 await title.evaluate(el=>{let vm=el.__vueParentComponent;while(vm&&vm.type.__name!=='FeedbackForm')vm=vm.parent;if(!vm)throw Error('FeedbackForm missing');window.feedbackFormFixture=vm;window.closeRequests=[vm.setupState.guard(),vm.setupState.guard()]})
 const confirmation=page.locator('.el-message-box').filter({hasText:'当前记录有未保存的修改。'})
 await expect(confirmation).toHaveCount(1)
 await page.screenshot({path:'../outputs/governance-finish-20261018/feedback-close-browser.png',animations:'disabled'})
 await confirmation.getByRole('button',{name:'取消',exact:true}).click()
 assert.deepEqual(await page.evaluate(()=>Promise.all(window.closeRequests)),[false,false]);await expect(title).toHaveValue('仅隔离模拟，未保存');assert.equal(writes.length,0)
 await dialog.getByRole('button',{name:'取消',exact:true}).click();await confirmation.getByRole('button',{name:'放弃修改并切换',exact:true}).click();await expect(dialog).toBeHidden()
 await add.click();await expect(title).toHaveValue('');await dialog.getByRole('button',{name:'取消',exact:true}).click();await expect(dialog).toBeHidden();await expect(confirmation).toHaveCount(0)
 await add.click();await dialog.locator('#feedback-files').setInputFiles({name:'fixture.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.7\nfixture')});await dialog.getByRole('button',{name:'取消',exact:true}).click();await expect(confirmation).toHaveCount(1);await confirmation.getByRole('button',{name:'取消',exact:true}).click();await expect(dialog.getByText('fixture.pdf',{exact:true})).toBeVisible();assert.equal(writes.length,0)
 await dialog.getByRole('button',{name:'取消',exact:true}).click();await confirmation.getByRole('button',{name:'放弃修改并切换',exact:true}).click();await expect(dialog).toBeHidden()
 await add.click()
 for(const [label,value] of [['提报类型','问题'],['涉及模块','项目档案'],['具体类别','界面体验'],['影响程度','不影响正常使用']]){await dialog.getByRole('combobox',{name:label,exact:true}).press('Enter');await page.getByRole('option',{name:value,exact:true}).click()}
 for(const [label,value] of [['标题','完整隔离测试'],['详细说明','只用模拟API'],['复现步骤','模拟操作'],['期望结果','只提交一次']])await dialog.getByRole('textbox',{name:label,exact:true}).fill(value)
 await dialog.getByRole('button',{name:'取消',exact:true}).click();await confirmation.getByRole('button',{name:'保存后切换',exact:true}).click();await expect(dialog).toBeHidden();assert.equal(writes.length,1);assert.match(writes[0].submission_id,/^[a-f0-9-]{36}$/);assert.equal(writes[0].title,'完整隔离测试');await expect.poll(()=>page.evaluate(()=>window.feedbackFormFixture.setupState.dirty)).toBe(false);assert.deepEqual(errors,[])
 console.log('PASS: one close confirmation; cancel/discard/clean/file-only/save; one mocked POST; no real data, email or ERP')
}finally{await browser.close()}
