import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {createServer} from 'vite'
const out='../.runtime/a0-enum-options/evidence/browser'
fs.mkdirSync(out,{recursive:true})
const source=JSON.parse(fs.readFileSync(new URL('./fixtures/archive-field-linkage.json',import.meta.url),'utf8'))
const server=await createServer({server:{host:'127.0.0.1',port:5191,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:8191'}}}})
await server.listen()
const base='http://127.0.0.1:5191',browser=await chromium.launch({channel:'msedge',headless:true})
const pages=[],states=[],checks=[]
async function fixture(){
 const page=await browser.newPage({viewport:{width:1440,height:1000}});pages.push(page);page.setDefaultTimeout(10000)
 const state={disabled:false,fail:false,reads:0,saves:0,submits:0,updates:0,reject:false,errors:[]}
 states.push(state)
 const draft={id:'00000000-0000-4000-8000-000000000099',version:1,status:'active',project_code:'RESTORE-ENUM',project_name:'恢复历史草稿',payload:{project_code:'RESTORE-ENUM',project_name:'恢复历史草稿',archive_category:2,product_line_id:1,machine_model:12,manager_id:1},value_labels:{machine_model:'8" Cssstte Less'},updated_at:'2026-10-21T10:00:00+08:00'}
 const history={id:89,project_code:'ENUM-HISTORY',project_name:'历史枚举档案',customer:'合成客户',product_line_id:1,archive_category:2,machine_model:12,equipment_series:6,quantity:1,quantity_unit:7,manager_id:1,is_enabled:1,can_edit:true,change_mode:'direct',change_version:'a'.repeat(64),erp_sync_status:'historical',governance_legacy:true,created_at:'2026-10-01T10:00:00'}
 await page.addInitScript(()=>localStorage.setItem('access_token','synthetic-a0-session'))
 page.on('pageerror',e=>state.errors.push(e.message))
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),p=url.pathname,m=route.request().method()
  if(url.origin!==base)return route.abort()
  if(!p.startsWith('/api/'))return route.continue()
  let body=[]
  if(p==='/api/auth/me')body={id:1,username:'fixture',real_name:'隔离验收',permissions:['project:archive:view','project:archive:add','project:archive:edit']}
  else if(p==='/api/users/options')body=[{id:1,real_name:'隔离验收',username:'fixture'}]
  else if(['/api/product-lines/options','/api/product-lines/labels','/api/form-drafts/archive-create/product-lines'].includes(p))body={options:source.lines,label_map:Object.fromEntries(source.lines.map(i=>[i.value,i.label]))}
  else if(p==='/api/projects/archives/fields')body=source.metadata
  else if(p.startsWith('/api/dicts/code/')){
   const code=p.split('/').at(-1);body=structuredClone(source.enums[code]||{items:[],label_map:{}})
   if(code==='archive_machine_model'){
    state.reads++
    if(state.fail)return route.fulfill({status:503,json:{detail:'合成选项读取失败'}})
    if(state.disabled){body.items=body.items.filter(i=>String(i.value)!=='12');body.all_items=body.all_items?.map(i=>({...i,status:String(i.value)==='12'?0:i.status}))}
   }
  }else if(p==='/api/projects/archives/list')body={total:1,items:[history]}
  else if(p==='/api/form-drafts/archive-create'&&m==='GET')body={total:1,items:[draft]}
  else if(p==='/api/form-drafts/archive-create'&&m==='POST'){
   state.saves++
   if(state.reject)return route.fulfill({status:422,json:{detail:{code:'ARCHIVE_ENUM_UNAVAILABLE',field_key:'machine_model',message:'机型选项不存在或已禁用，请重新选择'}}})
   const b=route.request().postDataJSON();Object.assign(draft,{id:b.id,version:draft.version+1,payload:b.payload});body=draft
  }else if(p.endsWith('/submit')&&p.startsWith('/api/form-drafts/')){
   state.submits++;return route.fulfill({status:422,json:{detail:{code:'ARCHIVE_ENUM_UNAVAILABLE',field_key:'machine_model',message:'机型选项不存在或已禁用，请重新选择'}}})
  }else if(p.startsWith('/api/form-drafts/archive-create/'))body=draft
  else if(p==='/api/projects/archives/89'&&m==='PUT'){
   state.updates++;return route.fulfill({status:422,json:{detail:{code:'ARCHIVE_ENUM_UNAVAILABLE',field_key:'machine_model',message:'机型选项不存在或已禁用，请重新选择'}}})
  }else if(m!=='GET')throw new Error('unexpected synthetic mutation '+p)
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/archive');await expect(page.getByRole('button',{name:'编辑',exact:true})).toBeVisible()
 return {page,state,form:()=>page.getByRole('dialog',{name:'新增项目档案',exact:true})}
}
const control=(scope,label)=>scope.getByRole('combobox',{name:label,exact:true})
async function openSelect(page,scope,label){await control(scope,label).locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]').click()}
async function choose(page,scope,label,value){await openSelect(page,scope,label);const id=await control(scope,label).getAttribute('aria-controls');await page.locator('[id='+JSON.stringify(id)+']').getByRole('option',{name:value,exact:true}).click()}
try{
 // An already loaded SPA must refresh when opening a new form after external disable.
 let f=await fixture(),before=f.state.reads;f.state.disabled=true
 await f.page.getByRole('button',{name:'新增档案',exact:true}).click();await expect(f.form()).toBeVisible()
 await expect.poll(()=>f.state.reads).toBeGreaterThan(before)
 await choose(f.page,f.form(),'产品线','8吋Bench');await openSelect(f.page,f.form(),'机型')
 await expect(f.page.getByRole('option',{name:'8吋 Cassette Less',exact:true})).toBeVisible()
 await expect(f.page.getByRole('option',{name:'8" Cssstte Less',exact:true})).toHaveCount(0)
 await f.page.keyboard.press('Escape');checks.push('new form refresh excludes disabled values')
 // Begin editing a select again while the same form remains open.
 f.state.disabled=false;await openSelect(f.page,f.form(),'机型');await f.page.getByRole('option',{name:'8" Cssstte Less',exact:true}).click()
 f.state.disabled=true;await openSelect(f.page,f.form(),'机型')
 await expect(f.page.getByRole('option',{name:'8" Cssstte Less',exact:true})).toHaveAttribute('aria-disabled','true')
 await f.page.keyboard.press('Escape');checks.push('select reopening refreshes, preserves disabled current label')
 // Save-time rejection refreshes and locates field without replacing input or retrying writes.
 await f.form().getByRole('textbox',{name:'项目编号',exact:true}).fill('KEEP-ENUM')
 await f.form().getByRole('textbox',{name:'项目名称',exact:true}).fill('输入必须保留')
 await choose(f.page,f.form(),'档案类别','辅机');f.state.reject=true
 await f.form().getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect(f.form()).toContainText('机型选项不存在或已禁用，请重新选择')
 await expect(f.form().getByRole('textbox',{name:'项目名称',exact:true})).toHaveValue('输入必须保留')
 assert.equal(f.state.saves,1);assert.equal(f.state.submits,0)
 await f.page.screenshot({path:out+'/save-rejection.png',animations:'disabled'});checks.push('save rejection locates field and keeps input with no retry')
 // Failed refresh keeps the new form and other inputs; recovery retries only reads.
 f=await fixture();f.state.fail=true;await f.page.getByRole('button',{name:'新增档案',exact:true}).click()
 await expect(f.form()).toContainText('选项读取失败')
 await f.form().getByRole('textbox',{name:'项目名称',exact:true}).fill('读取失败也保留')
 await f.form().getByRole('button',{name:'保存草稿',exact:true}).click();assert.equal(f.state.saves,0)
 f.state.fail=false;f.state.disabled=true;await f.form().getByRole('button',{name:'重试选项',exact:true}).click()
 await expect(f.form().getByText('选项读取失败',{exact:false})).toHaveCount(0)
 await expect(f.form().getByRole('textbox',{name:'项目名称',exact:true})).toHaveValue('读取失败也保留')
 await f.page.screenshot({path:out+'/read-recovered.png',animations:'disabled'});checks.push('failed read blocks saving and retry retains input')
 // Restore re-reads metadata and retains the historical value only as disabled.
 f=await fixture();f.state.disabled=true;await f.page.getByRole('button',{name:'我的草稿',exact:true}).click()
 await f.page.getByRole('dialog',{name:'我的草稿',exact:true}).getByRole('button',{name:'继续填写',exact:true}).click()
 await expect(f.form()).toBeVisible();await openSelect(f.page,f.form(),'机型')
 await expect(f.page.getByRole('option',{name:'8" Cssstte Less',exact:true})).toHaveAttribute('aria-disabled','true')
 await f.page.keyboard.press('Escape');checks.push('restore retains historical disabled label')
 // Existing detail form uses the same fresh selection behavior and structured rejection.
 f=await fixture();f.state.disabled=true;await f.page.getByRole('button',{name:'编辑',exact:true}).click()
 const detail=f.page.getByRole('dialog',{name:'编辑项目档案',exact:true});await expect(detail).toBeVisible()
 await openSelect(f.page,detail,'机型');await expect(f.page.getByRole('option',{name:'8" Cssstte Less',exact:true})).toHaveAttribute('aria-disabled','true')
 await f.page.keyboard.press('Escape');await choose(f.page,detail,'机型','8吋 Cassette Less')
 await detail.getByRole('button',{name:'保存生效',exact:true}).click();await expect(detail).toContainText('机型选项不存在或已禁用，请重新选择')
 assert.equal(f.state.updates,1);await expect(detail.getByText('8吋 Cassette Less',{exact:true})).toBeVisible();checks.push('detail refresh and rejection preserve changed input')
 assert.deepEqual(states.flatMap(state=>state.errors),[])
 for(const p of pages)await p.close()
 fs.writeFileSync(out+'/verification.json',JSON.stringify({passed:true,checks,productionRequests:0,realWrites:0},null,2)+'\n')
 console.log('PASS '+checks.length+' isolated archive enum scenarios; no real writes or external requests')
}finally{await browser.close();await server.close()}
