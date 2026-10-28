import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base=process.env.PMS_GOVERNANCE_URL||'http://127.0.0.1:5174',out='../outputs/form-compliance-20261016'
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
 const page=await browser.newPage({viewport:{width:1440,height:900}});page.setDefaultTimeout(8000)
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-retry-control'))
 let manage=true,retryAllowed=true,retryFail=true,finishRetry
 const writes=[],errors=[]
 const rows=[{id:101,user_name:'未知状态用户',status:'unknown',read_at:null,error_message:''},{id:102,user_name:'失败状态用户',status:'failed',read_at:null,error_message:''},{id:103,user_name:'等待配置用户',status:'waiting',read_at:null,error_message:''}]
 const release={id:1,version:'v1.0.0',title:'隔离控件验收',summary:'模拟数据，不进行真实邮件投递',published_at:'2026-10-16T09:00:00',changes:[{kind:'调整',title:'共享勾选控件',description:'保留人工核查规则',guide:'archive'}]}
 page.on('pageerror',error=>errors.push(error.message))
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname,method=route.request().method()
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let json=[]
  if(path==='/api/auth/me')json={id:1,username:'fixture',real_name:'本机隔离验收',permissions:['project:archive:view',...(manage?['system:release:manage']:[]),...(retryAllowed?['system:release:retry']:[])]}
  else if(path==='/api/business-notices')json={total:0,unread:0,items:[]}
  else if(path==='/api/releases/runtime')json={product:'PMS 项目管理系统',version:'v1.0.0',environment:'开发环境',published_at:release.published_at,page_updates:{}}
  else if(path==='/api/releases/notices')json={total:1,unread:1,items:[{id:11,read_at:null,release}]}
  else if(path==='/api/releases')json={total:1,items:[release]}
  else if(path==='/api/releases/1/deliveries')json={total:rows.length,items:rows}
  else if(path==='/api/releases/mail/101/retry'&&method==='POST'){
   writes.push(route.request().postDataJSON());await new Promise(resolve=>{finishRetry=resolve})
   if(retryFail)return route.fulfill({status:503,json:{detail:'隔离模拟重试失败，请保留原因稍后重试'}})
   rows[0].status='pending';json={queued:true}
  }
  else if(path==='/api/projects/archives/list')json={total:0,items:[]}
  else if(path==='/api/product-lines/options'||path==='/api/product-lines/labels')json={options:[],label_map:{}}
  else if(path==='/api/projects/archives/fields')json={items:[]}
  else if(path.startsWith('/api/dicts/code/'))json={items:[],label_map:{}}
  return route.fulfill({json})
 })
 async function notices(){
  await page.goto(base+'/project/archive');await page.getByRole('button',{name:/^通知/}).click()
  await page.getByRole('tab',{name:'升级通知',exact:true}).click()
  return page.getByRole('dialog',{name:'通知',exact:true})
 }
 let notice=await notices()
 await notice.getByRole('row').filter({hasText:'未知状态用户'}).getByRole('button',{name:'受控重试',exact:true}).click()
 let confirm=page.getByRole('dialog',{name:'确认重试邮件',exact:true})
 const reason=confirm.getByRole('textbox',{name:'重试原因',exact:true})
 const checkbox=confirm.getByRole('checkbox',{name:'已人工核查，确认用户未收到邮件',exact:true})
 const submit=confirm.getByRole('button',{name:'确认重试',exact:true})
 await expect(submit).toBeDisabled();await expect(checkbox).not.toBeChecked()
 await reason.fill('已向用户核实，未收到本次邮件')
 await expect(submit).toBeDisabled();assert.equal(writes.length,0)
 await checkbox.focus();await checkbox.press('Space');await expect(checkbox).toBeChecked();await expect(submit).toBeEnabled()
 await reason.fill('');await expect(submit).toBeDisabled()
 await reason.fill('已向用户核实，未收到本次邮件');await expect(submit).toBeEnabled()
 await checkbox.focus();await checkbox.press('Space');await expect(checkbox).not.toBeChecked();await expect(submit).toBeDisabled()
 await checkbox.press('Space');await expect(checkbox).toBeChecked();await expect(submit).toBeEnabled()
 await expect(confirm.locator('.pms-form-control--binary')).toHaveCount(1)
 await page.screenshot({animations:'disabled',path:out+'/unknown-confirm.jpg'})
 await submit.click();await expect.poll(()=>writes.length).toBe(1)
 await expect(reason).toBeDisabled();await expect(checkbox).toBeDisabled();await expect(submit).toBeDisabled()
 finishRetry();await expect(reason).toBeEnabled();await expect(reason).toHaveValue('已向用户核实，未收到本次邮件');await expect(checkbox).toBeChecked()
 assert.deepEqual(writes[0],{reason:'已向用户核实，未收到本次邮件',checked_not_received:true})
 retryFail=false;await submit.click();await expect.poll(()=>writes.length).toBe(2);finishRetry();await expect(confirm).toBeHidden()
 assert.deepEqual(writes[1],writes[0])
 for(const name of ['失败状态用户','等待配置用户']){
  await notice.getByRole('row').filter({hasText:name}).getByRole('button',{name:'受控重试',exact:true}).click()
  confirm=page.getByRole('dialog',{name:'确认重试邮件',exact:true})
  await expect(confirm.getByRole('checkbox')).toHaveCount(0)
  const submit=confirm.getByRole('button',{name:'确认重试',exact:true})
  await expect(submit).toBeDisabled();await confirm.getByRole('textbox',{name:'重试原因',exact:true}).fill('核对配置后再处理')
  await expect(submit).toBeEnabled();await confirm.getByRole('button',{name:'取消',exact:true}).click()
 }
 retryAllowed=false;notice=await notices()
 await expect(notice.getByRole('row').filter({hasText:'失败状态用户'})).toBeVisible()
 await expect(notice.getByRole('button',{name:'受控重试',exact:true})).toHaveCount(0)
 manage=false;notice=await notices()
 await expect(notice.getByText('邮件投递',{exact:true})).toHaveCount(0)
 assert.equal(writes.length,2);assert.deepEqual(errors,[])
 console.log('PASS: unknown原因与人工核查双条件、键盘勾选、统一控件、忙碌禁用、失败留值及重试；failed/waiting原条件；撤去模拟权限隐藏重试；全模拟API，真实邮件/业务写入0')
}finally{await browser.close()}
