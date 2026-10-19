import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {createServer} from 'vite'
const fixture=JSON.parse(fs.readFileSync(new URL('./fixtures/archive-field-linkage.json',import.meta.url),'utf8'))
const out='../outputs/archive-field-linkage-20261019/linkage-browser'
fs.mkdirSync(out,{recursive:true})
const server=await createServer({server:{host:'127.0.0.1',port:0}});await server.listen()
const base=`http://127.0.0.1:${server.httpServer.address().port}`
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],writes=[]
 page.setDefaultTimeout(8000);page.on('pageerror',error=>errors.push(error.message))
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-linkage-test'))
 const rows=new Map(),history={id:89,project_code:'HISTORY-LINKAGE',project_name:'历史不匹配档案',product_line_id:1,archive_category:2,machine_model:1,equipment_series:14,quantity:1,quantity_unit:7,manager_id:2,is_enabled:1,can_edit:true,can_maintain:false,change_mode:'direct',erp_sync_status:'historical',governance_legacy:true}
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url()),p=u.pathname,m=route.request().method()
  if(u.origin!==base)return route.abort()
  if(!p.startsWith('/api/'))return route.continue()
  let body=[]
  if(p==='/api/auth/me')body={id:1,username:'fixture',real_name:'当前操作者',permissions:['project:archive:view','project:archive:add','project:archive:edit']}
  else if(p==='/api/users/options')body=[{id:1,real_name:'当前操作者'},{id:2,real_name:'原草稿负责人'}]
  else if(p==='/api/product-lines/options'||p==='/api/product-lines/labels'||p==='/api/form-drafts/archive-create/product-lines')body={options:fixture.lines,label_map:Object.fromEntries(fixture.lines.map(i=>[i.value,i.label]))}
  else if(p==='/api/projects/archives/fields')body=fixture.metadata
  else if(p.startsWith('/api/dicts/code/'))body=fixture.enums[p.split('/').at(-1)]||{items:[],label_map:{}}
  else if(p==='/api/projects/archives/list')body={total:1,items:[history]}
  else if(p==='/api/form-drafts/archive-create'&&m==='GET')body={items:[...rows.values()],total:rows.size}
  else if(p==='/api/form-drafts/archive-create'&&m==='POST'){
   const b=route.request().postDataJSON();writes.push(b.payload)
   body={id:b.id,version:(rows.get(b.id)?.version||0)+1,status:'active',payload:b.payload,project_code:b.payload.project_code,project_name:b.payload.project_name,updated_at:'2026-10-19T11:00:00+08:00'};rows.set(b.id,body)
  }else if(p.startsWith('/api/form-drafts/archive-create/'))body=rows.get(p.split('/')[4])
  else if(m!=='GET')throw new Error('unexpected mutation: '+p)
  return route.fulfill({json:body})
 })
 const control=(scope,name)=>scope.getByRole('combobox',{name,exact:true})
 async function open(scope,name){await control(scope,name).locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]').click()}
 async function pick(scope,name,label){await open(scope,name);await page.getByRole('option',{name:label,exact:true}).click()}
 async function options(scope,name){await open(scope,name);const visible=page.getByRole('listbox').filter({visible:true});await expect(visible.getByRole('option').first()).toBeVisible();const values=await visible.getByRole('option').allTextContents();await page.keyboard.press('Escape');return values.map(x=>x.trim())}
 await page.goto(base+'/project/archive');await page.addStyleTag({content:'*{animation:none!important;transition:none!important}'})
 await page.getByRole('button',{name:'新增档案',exact:true}).click()
 const form=page.getByRole('dialog',{name:'新增项目档案',exact:true})
 await expect(form).toBeVisible()
 await expect(form.getByText('当前操作者',{exact:true})).toBeVisible()
 for(const key of ['project_code','project_name','product_line_id','archive_category'])await expect(form.locator(`label[for="archive-create-${key}"] .pms-form-field__required`)).toBeVisible()
 await expect(form.locator('label[for="archive-create-machine_model"] .pms-form-field__required')).toHaveCount(0)
 const units=await options(form,'单位');assert.equal(units[0],'台');assert.deepEqual(units.slice(1),['个','米','㎡','包','卷','只','块','套','对','批','根','次','段','片','给','颗'])
 await pick(form,'产品线','8吋Bench')
 let models=await options(form,'机型');assert.ok(models.includes('8吋 Cassette Less'));assert.ok(models.includes('HOT SPM'));assert.ok(models.includes('辅机'));assert.ok(!models.includes('12吋 Single'));assert.ok(!models.includes('12吋 Cassette Less'))
 let series=await options(form,'设备系列');assert.ok(series.includes('DF-2000B'));assert.ok(!series.includes('DF-3000B'));assert.ok(series.includes('软件'))
 await pick(form,'机型','8吋 Cassette Less');await pick(form,'设备系列','DF-2000B')
 await pick(form,'产品线','12吋Bench');await expect(page.getByText('已清除与新产品线不匹配的选项，请重新选择机型或设备系列',{exact:true})).toBeVisible()
 await expect(control(form,'机型')).toHaveValue('');await expect(control(form,'设备系列')).toHaveValue('')
 models=await options(form,'机型');assert.ok(models.includes('12吋 Cassette Less'));assert.ok(!models.includes('8吋 Cassette Less'))
 await pick(form,'机型','辅机');await pick(form,'设备系列','软件');await pick(form,'产品线','Single')
 await expect(form.getByText('辅机',{exact:true})).toBeVisible();await expect(form.getByText('软件',{exact:true})).toBeVisible()
 models=await options(form,'机型');assert.ok(models.includes('12吋 Single'));assert.ok(models.includes('8吋 Single'));assert.ok(!models.includes('12吋 Cassette Less'))
 series=await options(form,'设备系列');assert.ok(series.includes('FY-2000S'));assert.ok(!series.includes('DF-2000B'))
 await pick(form,'产品线','光伏');assert.equal((await options(form,'机型')).length,16);assert.equal((await options(form,'设备系列')).length,18)
 await pick(form,'产品线','12吋Bench');await pick(form,'机型','12吋 Cassette Less');await pick(form,'负责人','原草稿负责人')
 await form.getByRole('textbox',{name:'项目编号',exact:true}).fill('LINKAGE-DRAFT');await form.getByRole('textbox',{name:'项目名称',exact:true}).fill('联动验收')
 await form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect(form).toContainText('请选择档案类别');assert.equal(writes.length,0)
 await pick(form,'档案类别','辅机');await form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect.poll(()=>rows.size).toBe(1)
 assert.equal(writes[0].manager_id,2);assert.equal(writes[0].archive_category,2)
 // Simulate the existing draft response's saved label cache, then open formal
 // history with a different incompatible value: the cache must not cross forms.
 const row=[...rows.values()][0];row.value_labels={machine_model:'12吋 Cassette Less'}
 await page.screenshot({path:out+'/draft-fields.png',animations:'disabled'})
 await form.getByRole('button',{name:'取消',exact:true}).click();await expect(form).toBeHidden()
 await page.getByRole('button',{name:'我的草稿',exact:true}).click();await page.getByRole('dialog',{name:'我的草稿',exact:true}).getByRole('button',{name:'继续填写',exact:true}).click()
 await expect(form.getByText('原草稿负责人',{exact:true})).toBeVisible();await expect(form.getByText('12吋 Cassette Less',{exact:true})).toBeVisible()
 await form.getByRole('button',{name:'取消',exact:true}).click()
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 const detail=page.getByRole('dialog',{name:'编辑项目档案',exact:true})
 await expect(detail).toBeVisible();await expect(detail.getByText('12吋 Single',{exact:true})).toBeVisible()
 await open(detail,'机型');await expect(page.getByRole('option',{name:'12吋 Single',exact:true})).toHaveAttribute('aria-disabled','true');await page.keyboard.press('Escape')
 await page.screenshot({path:out+'/historical-value.png',animations:'disabled'})
 assert.deepEqual(errors,[])
 fs.writeFileSync(out+'/verification.json',JSON.stringify({passed:true,realWrites:0,syntheticDraftSaves:writes.length,categoryRequired:true,managerDefaultAndRestore:true,unitPriority:true,threeProfiles:true,genericOptionsPreserved:true,parentClearsIncompatible:true,historicalLabelCorrect:true,errors},null,2))
 console.log('PASS category/default owner/unit priority/three scoped profiles/parent clearing/general choices/draft restore/history labels; real writes=0')
}finally{await browser.close();await server.close()}
