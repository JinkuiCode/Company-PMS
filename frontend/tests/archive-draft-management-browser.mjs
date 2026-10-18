import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const output='../outputs/archive-draft-management-20261016/real-page'
fs.mkdirSync(output,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
const origin='http://127.0.0.1:5174',api='/api/archive-draft-management'
const uid=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`
const rows=new Map(Array.from({length:502},(_,i)=>[uid(i+1),{id:uid(i+1),version:1,status:'active',project_code:`DG-${String(i+1).padStart(4,'0')}`,project_name:`草稿项目${i+1}`,creator_name:i?'王工程师':'陈工程师',creator_enabled:!!i,product_line_name:'8吋Bench',product_line_id:1,updated_at:'2026-10-16T16:40:00+08:00'}]))
let permissions=['project:archive:view','project:archive:draft:manage'],mutations=0,listReads=0,conflict=false,deny=false,slowResolve,slow=false,historyStatus=200,pauseList=false,releaseList,revokeSignal=false
const errors=[],calls=[]
try{
 const page=await browser.newPage({viewport:{width:1440,height:900}})
 page.setDefaultTimeout(8000)
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-management-ui-fixture'))
 page.on('pageerror',e=>errors.push(e.message))
 await page.route('**/*',async route=>{
  const request=route.request(),u=new URL(request.url()),path=u.pathname,method=request.method()
  if(u.origin!==origin)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  calls.push([method,path])
  const fulfill=(data,status=200)=>route.fulfill({status,json:data})
  if(path==='/api/auth/me')return fulfill({id:900000002,username:'fixture',real_name:'验收用户',permissions})
  if(path==='/api/projects/archives/list')return fulfill({items:[],total:0})
  if(path==='/api/projects/archives/fields')return fulfill({items:['project_code','project_name','manager_id','product_line_id'].map(key=>({field_key:key,label:({project_code:'项目编号',project_name:'项目名称',manager_id:'负责人',product_line_id:'产品线'})[key],visible:true,editable:true,list_available:true,required:true}))})
  if(path==='/api/product-lines/labels'||path==='/api/product-lines/options')return fulfill({options:[{value:1,label:'8吋Bench'}],label_map:{1:'8吋Bench'}})
  if(path.startsWith('/api/dicts/code/'))return fulfill({items:[],all_items:[],label_map:{}})
  if(path==='/api/releases/notices'&&revokeSignal)return fulfill({detail:'权限已调整'},403)
  if(path===api&&method==='GET'){
   listReads++;if(deny)return fulfill({detail:'无权限'},403)
   const pageNo=Number(u.searchParams.get('page')||1),size=Number(u.searchParams.get('page_size')||50),items=[...rows.values()].filter(r=>r.status==='active')
   if(pauseList)await new Promise(resolve=>{releaseList=resolve})
   return fulfill({items:items.slice((pageNo-1)*size,pageNo*size),total:items.length})
  }
  if(path.startsWith(api+'/')){
   const id=path.split('/')[3],row=rows.get(id)
   if(deny)return fulfill({detail:'无权限'},403)
   if(path.endsWith('/history'))return historyStatus===200?fulfill({items:[{id:1,actor:'陈工程师',created_at:'2026-10-16T16:40:00+08:00',action:'draft_save',action_label:'保存草稿',status:'success',status_label:'成功',source:'档案草稿',summary:'保存草稿',diff_items:[]}],total:1,actions:[{value:'draft_save',label:'保存草稿'}]}):fulfill({detail:'当前无权访问'},historyStatus)
   if(method==='DELETE'){
    mutations++;if(conflict){row.version++;return fulfill({detail:{code:'DRAFT_VERSION_CONFLICT'}},409)}
    assert.equal(request.postDataJSON().expected_version,row.version)
    row.status='deleted';return fulfill({msg:'草稿已删除'})
   }
   if(method==='GET'){
    if(slow&&id===uid(1))await new Promise(resolve=>{slowResolve=resolve})
    return fulfill({...row,payload:{project_code:row.project_code,project_name:row.project_name,product_line_id:1},fields:[{key:'project_code',label:'项目编号',display:row.project_code},{key:'project_name',label:'项目名称',display:row.project_name},{key:'product_line_id',label:'产品线',display:'8吋Bench'},{key:'manager_id',label:'负责人',display:row.creator_name}],warnings:[]})
   }
  }
  if(method!=='GET')throw Error('Unexpected mutation '+method+' '+path)
  return fulfill([])
 })
 async function enter(){await page.goto(origin+'/project/archive-drafts');await page.addStyleTag({content:'*{transition:none!important;animation:none!important}'})}
 await page.goto(origin+'/project/archive')
 await page.addStyleTag({content:'*{transition:none!important;animation:none!important}'})
 await page.getByRole('button',{name:'草稿管理',exact:true}).click()
 await expect(page).toHaveURL(origin+'/project/archive-drafts')
 await expect(page.locator('.header-title')).toHaveText('草稿管理')
 await expect(page.getByRole('button',{name:'说明',exact:true})).toBeVisible()
 await expect(page.getByText('共 502 条',{exact:true})).toBeVisible()
 assert.equal(listReads,2,'initial query must read all server pages once')
 await page.getByRole('textbox',{name:'查询1值',exact:true}).fill('DG-0501')
 await page.getByRole('button',{name:'查询',exact:true}).click()
 const row501=page.getByRole('row').filter({hasText:'DG-0501'})
 await expect(row501).toBeVisible();await expect(page.getByText('共 1 条',{exact:true})).toBeVisible()
 await row501.getByRole('button',{name:'删除',exact:true}).click()
 const confirm=page.getByRole('dialog',{name:'删除草稿',exact:true})
 await expect(confirm).toContainText('DG-0501')
 await confirm.getByRole('button',{name:'取消',exact:true}).click();assert.equal(mutations,0)
 await row501.getByRole('button',{name:'查看',exact:true}).click()
 const detail=page.getByRole('dialog',{name:'草稿详情',exact:true})
 await expect(detail.getByRole('textbox',{name:'产品线',exact:true})).toHaveValue('8吋Bench')
 await expect(detail.getByRole('textbox',{name:'产品线',exact:true})).toHaveAttribute('readonly','')
 await detail.getByRole('tab',{name:'操作记录',exact:true}).click()
 await expect(detail).toContainText('陈工程师');assert(calls.some(([,path])=>path===api+'/'+uid(501)+'/history'))
 await page.screenshot({path:output+'/history.png',animations:'disabled'})
 conflict=true;await detail.getByRole('button',{name:'删除',exact:true}).click();await confirm.getByRole('button',{name:'确认删除',exact:true}).click()
 await expect(detail).toContainText('草稿已有更新');assert.equal(mutations,1)
 await detail.getByRole('button',{name:'关闭此对话框',exact:true}).click()
 await expect(detail).toBeHidden()
 await page.getByRole('button',{name:'查询',exact:true}).click()
 conflict=false;await row501.getByRole('button',{name:'删除',exact:true}).click();await confirm.getByRole('button',{name:'确认删除',exact:true}).click()
 await expect(row501).toHaveCount(0);assert.equal(mutations,2)
 await enter()
 await expect(page.getByText('共 501 条',{exact:true})).toBeVisible()
 await page.screenshot({path:output+'/list.png',animations:'disabled'})
 slow=true
 const row1=page.getByRole('row').filter({hasText:'DG-0001'}),row2=page.getByRole('row').filter({hasText:'DG-0002'})
 await row1.getByRole('button',{name:'查看',exact:true}).click()
 await expect(detail).toBeVisible();await expect(detail).toContainText('正在加载')
 await row2.locator('td').first().click()
 await expect(detail.getByRole('textbox',{name:'项目编号',exact:true})).toHaveValue('DG-0002')
 slowResolve();slow=false
 await expect(detail.getByRole('textbox',{name:'项目编号',exact:true})).toHaveValue('DG-0002')
 await page.screenshot({path:output+'/detail.png',animations:'disabled'})
 deny=true;await detail.getByRole('button',{name:'删除',exact:true}).click();await confirm.getByRole('button',{name:'确认删除',exact:true}).click()
 await expect(page.getByRole('row').filter({hasText:'DG-0002'})).toHaveCount(0)
 await expect(page.getByText('当前无权管理草稿，请联系管理员核对权限。',{exact:true})).toBeVisible()
 deny=false;await enter();await expect(page.getByText('共 501 条',{exact:true})).toBeVisible()
 await row2.getByRole('button',{name:'查看',exact:true}).click()
 await expect(detail.getByRole('textbox',{name:'项目编号',exact:true})).toHaveValue('DG-0002')
 deny=true;await detail.getByRole('tab',{name:'操作记录',exact:true}).click()
 await expect(detail).toBeHidden()
 await expect(page.getByRole('row').filter({hasText:'DG-0002'})).toHaveCount(0)
 await expect(page.getByText('当前无权管理草稿，请联系管理员核对权限。',{exact:true})).toBeVisible()
 deny=false;await enter();await expect(page.getByText('共 501 条',{exact:true})).toBeVisible()
 await row2.getByRole('button',{name:'查看',exact:true}).click()
 await expect(detail.getByRole('textbox',{name:'项目编号',exact:true})).toHaveValue('DG-0002')
 pauseList=true
 const pending=page.waitForRequest(request=>new URL(request.url()).pathname===api)
 await page.getByRole('button',{name:'查询',exact:true}).click();await pending
 historyStatus=404;await detail.getByRole('tab',{name:'操作记录',exact:true}).click()
 await expect(detail).toBeHidden()
 await expect(page.getByText('草稿不存在或已无权访问，请重新查询。',{exact:true})).toBeVisible()
 const lateReply=page.waitForResponse(response=>new URL(response.url()).pathname===api)
 releaseList();pauseList=false;await lateReply
 await expect(page.getByRole('row').filter({hasText:'DG-0002'})).toHaveCount(0)
 historyStatus=200
 permissions.push('business:data:all');await enter()
 await expect(page.getByText('共 501 条',{exact:true})).toBeVisible()
 await row2.getByRole('button',{name:'查看',exact:true}).click()
 await expect(detail.getByRole('textbox',{name:'项目编号',exact:true})).toHaveValue('DG-0002')
 permissions=permissions.filter(code=>code!=='business:data:all');revokeSignal=true
 const authReload=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/auth/me')
 await page.getByRole('button',{name:'升级通知',exact:true}).click();await authReload
 await expect(page.locator('#managed-draft-project_code')).toHaveCount(0)
 revokeSignal=false
 deny=false;permissions=['project:archive:view'];const before=calls.filter(([,p])=>p===api).length
 await enter();await expect(page).toHaveURL(origin+'/403')
 assert.equal(calls.filter(([,p])=>p===api).length,before)
 assert.deepEqual(errors,[])
 console.log('PASS actual management route: all-page filters, view/delete/cancel/CAS, shared history, latest selection wins, live denial clears data, route permission; synthetic API only')
}finally{await browser.close()}
