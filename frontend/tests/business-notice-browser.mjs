import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const base=process.env.PMS_NOTICE_URL||'http://127.0.0.1:5197'
const browser=await chromium.launch({channel:'msedge',headless:true})
await mkdir('../.runtime/p20-notifications/screenshots',{recursive:true})
try {
 const page=await browser.newPage({viewport:{width:1366,height:900}}),errors=[]
 page.on('pageerror',e=>errors.push(e.message))
 let read=false,failRead=true,failList=false,denied=false,reads=0
 const notice={id:11,change_id:21,event:'submitted',request_version:1,status:2,project_code:'P2026-018',project_name:'精密装配线',author_name:'张明',approver_name:'李华',created_at:'2026-10-27T16:00:00+08:00',read_at:null}
 const change={id:21,archive_id:1,status:2,version:1,project_code:'P2026-018',author_name:'张明',approver_name:'李华',reason:'核对名称',opinion:'',can_approve:true,can_withdraw:false,differences:[{field_key:'customer',field_label:'客户名称',before_display:'原客户',after_display:'新客户'}]}
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-notice-test'))
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let json=[]
  if(path==='/api/auth/me')json={id:1,username:'fixture',real_name:'李华',permissions:['project:archive:view','project:archive:edit']}
  else if(path==='/api/releases/runtime')json={version:'v1.3.0',environment:'隔离测试',page_updates:{}}
  else if(path==='/api/releases/notices')json={total:0,unread:2,items:[]}
  else if(path==='/api/releases')json={total:0,items:[]}
  else if(path==='/api/business-notices'){
   if(failList)return route.fulfill({status:503,json:{detail:'模拟读取失败'}})
   json={total:read&&url.searchParams.get('unread_only')==='true'?0:1,unread:read?0:1,items:read&&url.searchParams.get('unread_only')==='true'?[]:[{...notice,read_at:read?'2026-10-27T16:20:00+08:00':null}]}
  } else if(path==='/api/business-notices/11'){
   if(denied)return route.fulfill({status:404,json:{detail:'通知不存在或无权访问'}})
   json={...notice,read_at:read?'2026-10-27T16:20:00+08:00':null}
  } else if(path==='/api/business-notices/11/read'){
   if(failRead)return route.fulfill({status:500,json:{detail:'模拟保存失败'}})
   read=true;reads++;json={read:true}
  } else if(path==='/api/projects/archive-changes/requests/21')json=change
  else if(path==='/api/projects/archive-changes/requests/999')return route.fulfill({status:404,json:{detail:'不存在或无权访问'}})
  else if(path==='/api/projects/archive-changes')json={total:1,items:[change]}
  else if(path==='/api/dicts/code/archive_change_status')json={items:[{value:'2',label:'待审批'},{value:'3',label:'已通过'},{value:'4',label:'已退回'},{value:'5',label:'已撤回'}]}
  else if(path==='/api/projects/archives/list')json={total:0,items:[]}
  else if(path==='/api/projects/archives/fields')json={items:[]}
  else if(path==='/api/product-lines/options')json={options:[],label_map:{}}
  return route.fulfill({json})
 })
 await page.goto(base+'/project/archive')
 const bell=page.getByRole('button',{name:/^通知/})
 await expect(bell).toHaveAttribute('aria-label','通知，3条未读')
 await expect(page.getByText('审批通知 · 交互样稿')).toHaveCount(0)
 await bell.click()
 const dialog=page.getByRole('dialog',{name:'通知',exact:true})
 await expect(dialog.getByText('精密装配线',{exact:true}).first()).toBeVisible()
 await expect(dialog.getByRole('button',{name:'标为已读',exact:true})).toBeVisible()
 assert.equal(reads,0)
 await expect(dialog.getByText('邮件投递',{exact:true})).toHaveCount(0)
 await dialog.getByRole('button',{name:'标为已读',exact:true}).click()
 await expect(dialog.getByText('保存已读失败，请重试')).toBeVisible();assert.equal(reads,0)
 failRead=false;await dialog.getByRole('button',{name:'标为已读',exact:true}).click()
 await expect(dialog.getByRole('button',{name:'已读',exact:true})).toBeDisabled();assert.equal(reads,1)
 failList=true;await dialog.getByRole('button',{name:'刷新',exact:true}).click()
 await expect(dialog.getByText('业务消息读取失败，请重试')).toBeVisible()
 await expect(bell).toHaveAttribute('aria-label',/2条未读/)
 await dialog.getByRole('tab',{name:'升级通知',exact:true}).click()
 await expect(dialog).toContainText('暂无版本记录')
 await dialog.getByRole('tab',{name:'业务消息',exact:true}).click();failList=false
 await dialog.getByRole('button',{name:'刷新',exact:true}).click()
 await dialog.getByRole('button',{name:'查看申请',exact:true}).click()
 await expect(page).toHaveURL(/change_id=21/)
 const request=page.getByRole('dialog',{name:'档案变更审批'})
 await expect(request).toContainText('新客户')
 await expect(request.getByRole('button',{name:'通过',exact:true})).toBeVisible()
 await request.getByRole('button',{name:'关闭',exact:true}).click()
 await bell.click();await dialog.getByRole('button',{name:'查看申请',exact:true}).click()
 await expect(request).toBeVisible()
 await request.getByRole('button',{name:'关闭',exact:true}).click()
 await page.goto(base+'/project/archive?change_id=999')
 await expect(page.getByText('申请不存在或无权访问，请重新选择')).toBeVisible()
 await expect(page.getByRole('dialog',{name:'档案变更审批'})).toHaveCount(0)
 await bell.click();await expect(dialog).toBeVisible()
 await expect(page.locator('.el-message')).toHaveCount(0,{timeout:10000})
 await page.screenshot({path:'../.runtime/p20-notifications/screenshots/notification-integrated-blue.png',animations:'disabled'})
 await page.keyboard.press('Escape')
 for(const [id,label] of [['teal','青绿'],['graphite','石墨']]) {
  await page.getByRole('button',{name:'切换外观'}).click();await page.getByRole('menuitem',{name:label,exact:true}).click();await bell.click()
  await expect(dialog.getByRole('button',{name:'查看申请',exact:true})).toBeVisible()
  await page.screenshot({path:`../.runtime/p20-notifications/screenshots/notification-integrated-${id}.png`,animations:'disabled'});await page.keyboard.press('Escape')
 }
 await page.getByRole('button',{name:'切换外观'}).click();await page.getByRole('menuitem',{name:'办公蓝',exact:true}).click();await bell.click()
 await page.setViewportSize({width:518,height:760})
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 assert.equal(await page.locator('.notice-list').evaluate(el=>getComputedStyle(el).maxHeight),'180px')
 await page.screenshot({path:'../.runtime/p20-notifications/screenshots/notification-integrated-narrow.png',animations:'disabled'})
 await page.keyboard.press('Escape')
 await page.getByRole('button',{name:'用户菜单'}).click()
 await page.getByRole('menuitem',{name:'退出',exact:true}).click()
 await expect(page).toHaveURL(/login/)
 assert.deepEqual(errors,[])
 console.log('PASS: unified notices, channel isolation, explicit read, deep link access, original approval, narrow layout, logout')
} finally {await browser.close()}
