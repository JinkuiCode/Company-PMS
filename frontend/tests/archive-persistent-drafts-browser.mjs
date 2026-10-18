import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base='http://127.0.0.1:5174',out='../outputs/archive-draft-management-20261016/persistent'
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1366,height:850}}),errors=[]
 page.on('pageerror',e=>{errors.push(e.message); fs.appendFileSync(out+'/page-errors.txt',e.stack+'\n')});page.setDefaultTimeout(7000)
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-persistent-draft'))
 await page.addStyleTag({content:'*{animation:none!important;transition:none!important}' }).catch(()=>{})
 const rows=new Map();let conflict=false,failSubmit=true,lostSubmit=false,saveCount=0,submits=0,holdRestore=false,releaseRestore
 const keys=['archive_category','project_code','project_name','customer','product_line_id','quantity','quantity_unit','manager_id','machine_model','equipment_series','serial_no','remarks','contract_signed_date','contract_ship_date']
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url()),p=u.pathname,m=route.request().method()
  if(u.origin!==base)return route.abort()
  if(!p.startsWith('/api/'))return route.continue()
  let body=[]
  if(p==='/api/auth/me')body={id:1,username:'fixture',real_name:'本机验收',permissions:['project:archive:view','project:archive:add']}
  else if(p==='/api/users/options')body=[{id:1,real_name:'本机验收'}]
  else if(p==='/api/product-lines/options'||p==='/api/product-lines/labels'||p==='/api/form-drafts/archive-create/product-lines')body={options:[{value:7,label:'8吋Bench'}],label_map:{7:'8吋Bench'}}
  else if(p==='/api/projects/archives/fields')body={items:keys.map(field_key=>({field_key,label:field_key==='project_name'?'项目名称':field_key,visible:!field_key.startsWith('contract_'),editable:!field_key.startsWith('contract_'),list_available:true,required:['project_name','quantity'].includes(field_key)}))}
  else if(p.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'主机'},{value:7,label:'台'}],label_map:{1:'主机',7:'台'}}
  else if(p==='/api/projects/archives/list')body={total:0,items:[]}
  else if(p==='/api/form-drafts/archive-create'&&m==='GET')body={items:[...rows.values()].filter(r=>r.status==='active'),total:[...rows.values()].filter(r=>r.status==='active').length}
  else if(p==='/api/form-drafts/archive-create'&&m==='POST'){
   saveCount++;const b=route.request().postDataJSON()
   if(conflict)return route.fulfill({status:409,json:{detail:{code:'DRAFT_VERSION_CONFLICT',message:'草稿已有更新'}}})
   body={id:b.id,version:(rows.get(b.id)?.version||0)+1,status:'active',payload:b.payload,project_code:b.payload.project_code,project_name:b.payload.project_name||'未命名项目档案',updated_at:'2026-10-16T15:10:00+08:00'};rows.set(b.id,body)
  }else if(p.startsWith('/api/form-drafts/archive-create/')){
   const id=p.split('/')[4],row=rows.get(id)
   if(!row)return route.fulfill({status:404,json:{detail:'不存在'}})
   if(p.endsWith('/submit')){
    submits++;if(failSubmit)return route.fulfill({status:422,json:{detail:{code:'FIELD_POLICY_VALIDATION_FAILED',fields:[{field_key:'project_name',message:'项目名称需业务确认'}]}}})
    row.status='used';row.archive_id=42;body={id:42}
    if(lostSubmit)return route.abort('failed')
   }else if(m==='DELETE'){rows.delete(id);body={msg:'草稿已删除'}}else {if(holdRestore)await new Promise(resolve=>releaseRestore=resolve);body=row}
  }else if(p==='/api/projects/archives'&&m==='POST')throw new Error('不得走不可核对的重复创建路径')
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/archive')
 await page.addStyleTag({content:'*{animation:none!important;transition:none!important}'})
 await expect(page.getByRole('button',{name:'我的草稿',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'新增档案',exact:true}).click()
 await page.waitForTimeout(500); await page.screenshot({animations:'disabled',path:out+'/opening.jpg'}); fs.writeFileSync(out+'/opening.txt',await page.locator('body').innerText()); const form=page.getByRole('dialog',{name:'新增项目档案',exact:true}),name=form.getByRole('textbox',{name:'项目名称',exact:true}),code=form.getByRole('textbox',{name:'项目编号',exact:true})
 await expect(form).toBeVisible(); await page.screenshot({animations:'disabled',path:out+'/opening.jpg'}); fs.writeFileSync(out+'/opening.txt', await page.locator('body').innerText()); await code.fill('DRAFT-DEMO-01')
 await form.getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect(form).toContainText('请填写项目名称');assert.equal(saveCount,0)
 await code.fill('   ');await form.getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect(form).toContainText('请填写项目编号');assert.equal(saveCount,0)
 await code.fill('DRAFT-DEMO-01');await name.fill('初始草稿')
 await form.getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect.poll(()=>rows.size).toBe(1);assert.equal(submits,0)
 await name.fill('中途保存')
 await form.getByRole('button',{name:'取消',exact:true}).click()
 const close=page.getByRole('dialog',{name:'未保存修改',exact:true})
 await expect(close).toBeVisible();await close.getByRole('button',{name:'继续编辑',exact:true}).click();await expect(name).toHaveValue('中途保存')
 await form.getByRole('button',{name:'取消',exact:true}).click();await close.getByRole('button',{name:'保存草稿并关闭',exact:true}).click();await expect(form).toBeHidden()
 await page.getByRole('button',{name:'我的草稿',exact:true}).click()
 const list=page.getByRole('dialog',{name:'我的草稿',exact:true})
 await expect(list).toContainText('DRAFT-DEMO-01')
 const listBox=await list.boundingBox(),deleteBox=await list.getByRole('button',{name:'删除草稿',exact:true}).boundingBox()
 assert.ok(deleteBox.x+deleteBox.width <= listBox.x+listBox.width-8, '草稿操作必须完整显示，无需横向滚动')
 const deletion=list.getByRole('button',{name:'删除草稿',exact:true})
 const visibleWithinCell=await deletion.evaluate(el=>{const cell=el.closest('.cell'),e=el.getBoundingClientRect(),c=cell.getBoundingClientRect();return e.right<=c.right&&e.left>=c.left})
 assert.equal(visibleWithinCell,true,'删除按钮不得被单元格裁切')
 await page.screenshot({animations:'disabled',path:out+'/draft-list.jpg'})
 await list.getByRole('button',{name:'继续填写',exact:true}).click();await expect(name).toHaveValue('中途保存')
 await code.fill('LOCAL-CONFLICT');conflict=true
 await form.getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect(form).toContainText('草稿已有更新'); await expect(form.getByRole('alert').filter({hasText:'本次输入已保留'})).toBeInViewport();await expect(code).toHaveValue('LOCAL-CONFLICT')
 await page.screenshot({animations:'disabled',path:out+'/draft-conflict.jpg'})
 conflict=false;holdRestore=true
 await form.getByRole('button',{name:'加载最新草稿',exact:true}).click()
 await page.getByRole('dialog',{name:'加载最新草稿',exact:true}).getByRole('button',{name:'确定',exact:true}).click()
 await expect.poll(()=>Boolean(releaseRestore)).toBe(true)
 await expect(name).toHaveAttribute('readonly','')
 await expect(form.getByRole('button',{name:'取消',exact:true})).toBeDisabled()
 holdRestore=false;releaseRestore();await expect(code).toHaveValue('DRAFT-DEMO-01')
 await code.fill('LOCAL-CONFLICT');conflict=true;await form.getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect(form).toContainText('草稿已有更新');conflict=false
 await form.getByRole('button',{name:'另存为新草稿',exact:true}).click()
 await expect.poll(()=>rows.size).toBe(2)
 await form.getByRole('button',{name:'正式保存',exact:true}).click()
 await expect(form).toContainText('请填写quantity');assert.equal(submits,0)
 await expect(form.getByRole('button',{name:'取消',exact:true})).toBeEnabled()
 await form.getByRole('button',{name:'增加数值',exact:true}).click()
 await expect(form.getByRole('spinbutton',{name:'数量',exact:true})).toHaveValue('1')
 await form.getByRole('button',{name:'正式保存',exact:true}).click();await expect(form).toContainText('项目名称需业务确认');await expect(name).toHaveValue('中途保存')
 failSubmit=false;lostSubmit=true;await name.fill('修正后提交');await form.getByRole('button',{name:'正式保存',exact:true}).click()
 await expect(form).toContainText('保存结果尚未确认');await expect(form.getByRole('button',{name:'正式保存',exact:true})).toBeDisabled()
 await form.getByRole('button',{name:'核对保存结果',exact:true}).click();await expect(form).toBeHidden();assert.equal(submits,2)
 await page.getByRole('button',{name:'我的草稿',exact:true}).click();await expect(list).toContainText('DRAFT-DEMO-01');await expect(list).not.toContainText('LOCAL-CONFLICT')
 await list.getByRole('button',{name:'删除草稿',exact:true}).click()
 await page.getByRole('dialog',{name:'删除草稿',exact:true}).getByRole('button',{name:'确定',exact:true}).click()
 await expect(list).toContainText('暂无草稿')
 assert.deepEqual(errors,[])
 console.log('PASS incomplete save, close three choices, cross session restore, conflict keeps input/save-as-new, formal failure retains, unknown submit reconciles once, delete confirm; all API synthetic; real writes=0; saves='+saveCount)
}finally{await browser.close()}
