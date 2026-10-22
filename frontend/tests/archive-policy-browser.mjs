/** Real production-build UI; all API routes are synthetic and isolated. */
import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {preview} from 'vite'
const data=JSON.parse(fs.readFileSync(new URL('./fixtures/archive-policy.json',import.meta.url),'utf8'))
const out='../.runtime/a1-archive-policy/evidence/browser';fs.mkdirSync(out,{recursive:true})
const server=await preview({preview:{host:'127.0.0.1',port:5191,strictPort:true}})
const base='http://127.0.0.1:5191',browser=await chromium.launch({channel:'msedge',headless:true}),errors=[],checks=[]
async function setup(theme='blue',seriesEditable=true){
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message))
 await page.addInitScript(({base,theme})=>{localStorage.setItem('access_token','synthetic-a1-session');localStorage.setItem(`pms:theme:v1:${encodeURIComponent(base)}:1`,theme)},{base,theme})
 const rows=new Map(),writes=[];let conflict=false,versionConflict=false
 const history={id:89,project_code:'A1-FORMAL',project_name:'历史非主机',archive_category:2,product_line_id:1,manager_id:2,equipment_series:8,serial_no:'FORMAL-OLD',quantity:1,quantity_unit:7,remarks:'历史备注',is_enabled:1,can_edit:true,change_mode:'direct',governance_legacy:true,created_at:'2020-01-01',change_version:'a'.repeat(64)}
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname,m=req.method()
  if(url.origin!==base){errors.push('external request');return route.abort()}
  if(!p.startsWith('/api/'))return route.continue()
  let body=[]
  if(p==='/api/auth/me')body={id:1,username:'fixture',real_name:'合成操作者',permissions:['project:archive:view','project:archive:add','project:archive:edit']}
  else if(p==='/api/users/options')body=[{id:1,real_name:'合成操作者'},{id:2,real_name:'原草稿负责人'}]
  else if(['/api/product-lines/options','/api/product-lines/labels','/api/form-drafts/archive-create/product-lines'].includes(p))body={options:data.lines,label_map:Object.fromEntries(data.lines.map(i=>[i.value,i.label]))}
  else if(p==='/api/projects/archives/fields'){body=structuredClone(data.metadata);body.items.find(f=>f.field_key==='equipment_series').editable=seriesEditable}
  else if(p.startsWith('/api/dicts/code/'))body=data.enums[p.split('/').at(-1)]||{items:[],label_map:{}}
  else if(p==='/api/projects/archives/regions')body=[]
  else if(p==='/api/projects/archives/list')body={total:1,items:[history]}
  else if(p==='/api/projects/archives/89'&&m==='PUT'){const b=req.postDataJSON();writes.push(b);Object.assign(history,b);body={msg:'合成保存成功',sync_queued:false}}
  else if(p==='/api/form-drafts/archive-create'&&m==='GET')body={items:[...rows.values()],total:rows.size}
  else if(p==='/api/form-drafts/archive-create'&&m==='POST'){
   const b=req.postDataJSON();writes.push(b.payload)
   if(versionConflict){versionConflict=false;return route.fulfill({status:409,json:{detail:{code:'DRAFT_VERSION_CONFLICT',message:'草稿已有更新'}}})}
   if(conflict){conflict=false;return route.fulfill({status:409,json:{detail:{code:'ARCHIVE_UNIQUE_CONFLICT',field_key:'serial_no',message:'序列号已被使用，请更换'}}})}
   body={id:b.id,version:(rows.get(b.id)?.version||0)+1,status:'active',payload:{...rows.get(b.id)?.payload,...b.payload},project_code:b.payload.project_code,project_name:b.payload.project_name,updated_at:'2026-10-21T10:00:00+08:00'};rows.set(b.id,body)
  }else if(p.endsWith('/submit')&&m==='POST')body={id:10001,msg:'合成正式保存成功'}
  else if(p.startsWith('/api/form-drafts/archive-create/')&&m==='GET')body=rows.get(p.split('/')[4])
  else if(m!=='GET')throw Error('unexpected mutation '+m+' '+p)
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/archive');await expect(page.getByRole('button',{name:'新增档案',exact:true})).toBeVisible()
 const form=page.getByRole('dialog',{name:'新增项目档案',exact:true}),detail=page.getByRole('dialog',{name:'编辑项目档案',exact:true})
 const field=(key,scope=form)=>scope.locator(`#${scope===form?'archive-create':'archive-drawer'}-${key}`)
 async function pick(name,label,scope=form){const input=scope.getByRole('combobox',{name,exact:true});await input.locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]').click();await page.getByRole('option',{name:label,exact:true}).click()}
 async function restore(payload){rows.clear();rows.set('history-draft',{id:'history-draft',version:3,status:'active',project_code:'A1-HISTORY',project_name:'历史合成草稿',updated_at:'2026-10-21T09:00:00+08:00',payload:{project_code:'A1-HISTORY',project_name:'历史合成草稿',archive_category:2,product_line_id:1,manager_id:2,...payload}});await page.getByRole('button',{name:'我的草稿',exact:true}).click();await page.getByRole('dialog',{name:'我的草稿',exact:true}).getByRole('button',{name:'继续填写',exact:true}).click();await expect(form).toBeVisible()}
 return {page,form,detail,pick,field,restore,rows,writes,setConflict:()=>{conflict=true},setVersionConflict:()=>{versionConflict=true}}
}
try{
 let f=await setup();await f.page.getByRole('button',{name:'新增档案',exact:true}).click();await expect(f.form).toBeVisible()
 await expect(f.field('quantity')).toHaveValue('1');await expect(f.form.getByText('pcs',{exact:true})).toBeVisible();await expect(f.form.getByText('合成操作者',{exact:true})).toBeVisible();await expect(f.form.locator('label[for="archive-create-sales_company"]')).toBeVisible()
 for(const key of ['customer_full_name','legacy_archive_status','legacy_code_date','legacy_updated_date','delivery_note','remarks'])await expect(f.form.locator(`label[for="archive-create-${key}"]`)).toHaveCount(0)
 checks.push('fresh defaults, original owner, sales company and regional hiding')
 await f.pick('产品线','8吋Bench');await f.pick('档案类别','主机');await f.field('serial_no').fill('KEEP-SERIAL');await f.pick('设备系列','DF-2000B');await f.pick('档案类别','辅机')
 await expect(f.field('serial_no')).toHaveCount(0);await expect(f.field('equipment_series')).toHaveCount(0);await expect(f.field('customer')).toBeVisible();await expect(f.field('machine_model')).toBeVisible()
 await f.pick('档案类别','主机');await expect(f.field('serial_no')).toHaveValue('KEEP-SERIAL');await expect(f.form.getByText('DF-2000B',{exact:true})).toBeVisible();await f.pick('档案类别','辅机')
 await f.field('project_code').fill('A1-NEW');await f.field('project_name').fill('合成新建档案');await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect.poll(()=>f.rows.size).toBe(1)
 assert.equal(f.writes[0].quantity,1);assert.equal(f.writes[0].quantity_unit,7);assert.equal(f.writes[0].serial_no,'KEEP-SERIAL');assert.ok(!Object.hasOwn(f.writes[0],'remarks'));checks.push('category switch preserves values and hidden defaults are never written')
 await f.form.getByRole('button',{name:'取消',exact:true}).click();await expect(f.form).toBeHidden();await f.restore({serial_no:'CONFLICT-OLD',remarks:'保留隐藏备注'})
 await expect(f.field('quantity')).toHaveValue('');await expect(f.form.getByText('原草稿负责人',{exact:true})).toBeVisible();await expect(f.field('serial_no')).toHaveCount(0);checks.push('old draft omissions and original owner restored without defaults')
 f.setConflict();await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect(f.field('serial_no')).toBeVisible();await expect(f.field('serial_no')).toHaveValue('CONFLICT-OLD');await expect(f.form.getByText('序列号已被使用，请更换',{exact:true})).toBeVisible()
 await f.field('serial_no').fill('');await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect.poll(()=>f.rows.get('history-draft').version).toBe(4);assert.equal(f.writes.at(-1).serial_no,null);await expect(f.field('serial_no')).toHaveCount(0);assert.ok(!Object.hasOwn(f.writes.at(-1),'remarks'));checks.push('permitted historical serial conflict corrected explicitly, then hidden')
 await f.form.getByRole('button',{name:'正式保存',exact:true}).click();await expect(f.form).toBeHidden();checks.push('non-main five-field formal submission with null optional values')
 f=await setup();await f.restore({equipment_series:8,serial_no:'KEEP-SERIAL'})
 await f.pick('产品线','12吋Bench');await expect(f.field('equipment_series')).toBeVisible();await expect(f.form.getByText('DF-2000B',{exact:true})).toBeVisible();await expect(f.field('serial_no')).toHaveCount(0)
 await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();assert.equal(f.writes.length,0)
 await f.pick('产品线','8吋Bench');await expect(f.form.getByText('DF-2000B',{exact:true})).toBeVisible();await f.pick('产品线','12吋Bench');await f.pick('设备系列','DF-3000B');await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect.poll(()=>f.rows.get('history-draft').version).toBe(4);assert.equal(f.writes.at(-1).equipment_series,12);await expect(f.field('equipment_series')).toHaveCount(0);checks.push('hidden historical series retained across line switches, block until explicit correction, hide on success')
 await f.form.getByRole('button',{name:'取消',exact:true}).click();await f.page.getByRole('button',{name:'编辑',exact:true}).click();await expect(f.detail).toBeVisible();await f.pick('产品线','12吋Bench',f.detail);await expect(f.field('equipment_series',f.detail)).toBeVisible();await expect(f.detail.getByText('DF-2000B',{exact:true})).toBeVisible();await f.detail.getByRole('button',{name:'保存生效',exact:true}).click();assert.equal(f.writes.filter(w=>w.expected_version).length,0);await f.pick('设备系列','DF-3000B',f.detail);await f.detail.getByRole('button',{name:'保存生效',exact:true}).click();await expect.poll(()=>f.writes.filter(w=>w.expected_version).length).toBe(1);assert.equal(f.writes.at(-1).equipment_series,12);assert.ok(!Object.hasOwn(f.writes.at(-1),'serial_no'));await expect(f.field('equipment_series',f.detail)).toHaveCount(0);checks.push('formal detail blocks incompatibility, saves explicit correction without clearing hidden history')
 const denied=await setup('blue',false);await denied.restore({equipment_series:8});await denied.pick('产品线','12吋Bench');await expect(denied.field('equipment_series')).toHaveCount(0);await denied.form.getByRole('button',{name:'保存草稿',exact:true}).click();assert.equal(denied.writes.length,0);checks.push('readonly series never exposed or bypassed on incompatible line change')
 const copy=await setup();await copy.restore({equipment_series:8,serial_no:'COPY-HISTORY',remarks:'复制保留备注'});copy.setVersionConflict();await copy.form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect(copy.form.getByRole('button',{name:'另存为新草稿',exact:true})).toBeVisible();await copy.field('project_code').fill('A1-COPY');await copy.form.getByRole('button',{name:'另存为新草稿',exact:true}).click();await expect.poll(()=>copy.rows.size).toBe(2);assert.equal(copy.writes.at(-1).serial_no,'COPY-HISTORY');assert.equal(copy.writes.at(-1).equipment_series,8);assert.equal(copy.writes.at(-1).remarks,'复制保留备注');assert.equal(copy.rows.get('history-draft').version,3);checks.push('save as new keeps editable regional history without replacing original draft')
 const cleared=await setup();await cleared.restore({archive_category:1,equipment_series:8,serial_no:'EXPLICIT-CLEAR'});await cleared.field('serial_no').fill('');const seriesWrapper=cleared.field('equipment_series').locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]');await seriesWrapper.hover();await seriesWrapper.locator('.el-select__clear').click();await cleared.pick('档案类别','辅机');await cleared.form.getByRole('button',{name:'保存草稿',exact:true}).click();await expect.poll(()=>cleared.rows.get('history-draft').version).toBe(4);assert.equal(cleared.writes.at(-1).equipment_series,null);assert.equal(cleared.writes.at(-1).serial_no,null);checks.push('explicit selector/text clear survives category hiding and overrides retained history')
 for(const theme of ['blue','teal','graphite']){const t=await setup(theme);await t.page.getByRole('button',{name:'新增档案',exact:true}).click();await t.pick('档案类别','辅机');await expect(t.form.getByText('辅机',{exact:true})).toBeVisible();await expect(t.field('serial_no')).toHaveCount(0);await t.page.screenshot({path:out+`/non-main-${theme}.png`,animations:'disabled'});await t.pick('档案类别','主机');await expect(t.field('serial_no')).toBeVisible();await expect(t.field('equipment_series')).toBeVisible();await t.page.screenshot({path:out+`/main-${theme}.png`,animations:'disabled'})}
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/verification.json',JSON.stringify({passed:true,checks,productionBuild:true,realWrites:0,externalRequests:0,pageErrors:errors},null,2));console.log('PASS',checks.length,'A1 browser flows; real writes=0')
}finally{await browser.close();await server.httpServer.close()}
