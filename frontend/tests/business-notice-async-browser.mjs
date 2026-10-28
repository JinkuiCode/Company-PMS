import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const base=process.env.PMS_NOTICE_URL||'http://127.0.0.1:5197'
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
 const page=await browser.newPage({viewport:{width:1366,height:900}}),errors=[],retries=[]
 page.on('pageerror',e=>errors.push(e.message))
 await page.clock.install()
 let user=1,holdRequest=false,releaseRequest,holdCount=false,releaseCounts=[],countCalls=0,retryFail=true,releaseRetry
 const permissions=['project:archive:view','project:archive:edit','project:archive:notification:manage','project:archive:notification:retry']
 const notice={id:11,change_id:21,event:'submitted',status:2,project_code:'P21',project_name:'原申请项目',author_name:'提交人',approver_name:'审批人',created_at:'2026-10-27T16:00:00',read_at:null}
 const change=id=>({id,archive_id:1,status:2,version:1,project_code:`P${id}`,author_name:'提交人',approver_name:'审批人',reason:`申请${id}`,can_approve:true,differences:[{field_label:'客户',before_display:'原客户',after_display:`客户${id}`} ]})
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-notice-async'))
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let json=[]
  if(path==='/api/auth/me')json={id:user,username:`fixture${user}`,permissions}
  else if(path==='/api/releases/runtime')json={product:'PMS',version:'v1.3.0',environment:'隔离测试',page_updates:{}}
  else if(path==='/api/releases/notices')json={unread:2,total:0,items:[]}
  else if(path==='/api/business-notices'){
   const original=user
   if(url.searchParams.get('page_size')==='1'){countCalls++;if(holdCount&&original===1)await new Promise(resolve=>releaseCounts.push(resolve))}
   json={unread:original===1?1:0,total:original===1?1:0,items:original===1?[notice]:[]}
  } else if(path==='/api/business-notices/11')json=notice
  else if(path==='/api/business-notices/requests/21/deliveries')json={items:[{id:101,event:'submitted',user_name:'审批人',status:'unknown',attempts:1,read_at:null,error_message:'结果未知'}]}
  else if(path==='/api/business-notices/deliveries/101/retry'){
   retries.push(route.request().postDataJSON());await new Promise(resolve=>releaseRetry=resolve)
   if(retryFail)return route.fulfill({status:503,json:{detail:'模拟拒绝'}})
   json={queued:true}
  } else if(path==='/api/projects/archive-changes/requests/21'){
   if(holdRequest)await new Promise(resolve=>releaseRequest=resolve)
   json=change(21)
  } else if(path==='/api/projects/archive-changes/requests/22')json=change(22)
  else if(path==='/api/projects/archive-changes')json={total:2,items:[change(21),change(22)]}
  else if(path==='/api/dicts/code/archive_change_status')json={items:[{value:'2',label:'待审批'}]}
  else if(path==='/api/projects/archives/list')json={total:0,items:[]}
  else if(path==='/api/projects/archives/fields')json={items:[]}
  else if(path==='/api/product-lines/options')json={options:[],label_map:{}}
  return route.fulfill({json})
 })
 const navigate=id=>page.evaluate(async id=>{const router=document.querySelector('#app').__vue_app__.config.globalProperties.$router;await router.push({path:'/project/archive',query:{change_id:id}})},id)
 await page.goto(base+'/project/archive?change_id=21')
 const request=page.getByRole('dialog',{name:'档案变更审批'}),opinion=request.getByRole('textbox',{name:'审批意见',exact:true})
 await expect(request).toContainText('客户21');await opinion.fill('保留本次意见')
 await navigate(22)
 const confirm=page.getByRole('dialog',{name:'未保存修改'})
 await expect(confirm).toBeVisible();await confirm.getByRole('button',{name:'取消',exact:true}).click()
 await expect(opinion).toHaveValue('保留本次意见');await expect(request).toContainText('客户21')
 await opinion.fill('');holdRequest=true;await navigate(21);await expect.poll(()=>!!releaseRequest).toBe(true)
 await navigate(22);await expect(request).toContainText('客户22')
 releaseRequest();holdRequest=false;await expect(request).toContainText('客户22');await expect(request).not.toContainText('客户21')
 await request.getByRole('button',{name:'关闭',exact:true}).click()
 const bell=page.getByRole('button',{name:/^通知/});await bell.click()
 const dialog=page.getByRole('dialog',{name:'通知',exact:true})
 await dialog.getByText('邮件投递',{exact:true}).click()
 await dialog.getByRole('button',{name:'受控重试',exact:true}).click()
 const retry=page.getByRole('dialog',{name:'确认重试邮件',exact:true}),reason=retry.getByRole('textbox',{name:'重试原因',exact:true}),submit=retry.getByRole('button',{name:'确认重试',exact:true})
 await expect(submit).toBeDisabled();await reason.fill('已核查未收到');await expect(submit).toBeDisabled()
 const checkbox=retry.getByRole('checkbox');await checkbox.focus();await checkbox.press('Space')
 await expect(submit).toBeEnabled();await submit.click();await expect.poll(()=>retries.length).toBe(1)
 await expect(reason).toBeDisabled();await page.keyboard.press('Escape');await expect(retry).toBeVisible()
 releaseRetry();await expect(reason).toBeEnabled();await expect(reason).toHaveValue('已核查未收到')
 await expect(retry).toContainText('重试未成功，请核对当前投递状态后再试')
 retryFail=false;await submit.click();await expect.poll(()=>retries.length).toBe(2);releaseRetry();await expect(retry).toBeHidden()
 assert.deepEqual(retries,[{reason:'已核查未收到',checked_not_received:true},{reason:'已核查未收到',checked_not_received:true}])
 // Hold old-user responses while the authenticated identity changes in the existing store.
 holdCount=true;await page.evaluate(()=>window.dispatchEvent(new Event('focus')))
 await expect.poll(()=>releaseCounts.length).toBeGreaterThan(0)
 user=2
 await page.evaluate(async permissions=>{const {useAuthStore}=await import('/src/stores/auth.ts');useAuthStore().user={id:2,username:'fixture2',permissions}},permissions)
 await expect(dialog).toBeHidden();await expect(bell).toHaveAttribute('aria-label','通知，2条未读')
 releaseCounts.forEach(resolve=>resolve());holdCount=false
 await bell.click();await expect(dialog).toContainText('暂无业务消息');await expect(bell).toHaveAttribute('aria-label','通知，2条未读')
 const before=countCalls;await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await expect.poll(()=>countCalls).toBeGreaterThan(before)
 const beforeTimer=countCalls;await page.clock.runFor(61000);await expect.poll(()=>countCalls).toBeGreaterThan(beforeTimer)
 const visibleCalls=countCalls;await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,value:true}));await page.clock.runFor(61000);assert.equal(countCalls,visibleCalls)
 await page.evaluate(()=>delete document.hidden)
 await page.evaluate(async()=>{const {useAuthStore}=await import('/src/stores/auth.ts');useAuthStore().user.permissions=[]})
 await expect(dialog).toContainText('当前无权查看业务消息')
 await expect(dialog.getByText('原申请项目',{exact:true})).toHaveCount(0)
 assert.deepEqual(errors,[])
 console.log('PASS: draft cancellation, latest request wins, retry reason/confirmation/failure retention, account reset and stale responses, focus/visible polling, revocation')
}finally{await browser.close()}
