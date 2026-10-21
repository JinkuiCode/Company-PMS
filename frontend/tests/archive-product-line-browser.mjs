import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {createServer} from 'vite'
const out='../.runtime/p28-product-line/evidence/browser';fs.mkdirSync(out,{recursive:true})
const source=JSON.parse(fs.readFileSync(new URL('./fixtures/archive-field-linkage.json',import.meta.url),'utf8'))
const server=await createServer({server:{host:'127.0.0.1',port:5191,strictPort:true}});await server.listen()
const base='http://127.0.0.1:5191',browser=await chromium.launch({channel:'msedge',headless:true})
const prefKey='pms_project_archive_list_columns_v2:1',schemeKey='pms:query-workspace:v2:1:project-archive'
const contexts=[],errors=[],checks=[]
async function fixture(options={}){
 const context=await browser.newContext({viewport:{width:1440,height:1000}});contexts.push(context)
 const page=await context.newPage();page.setDefaultTimeout(10000)
 await page.addInitScript(({prefKey,schemeKey,options,base})=>{
  if(!sessionStorage.getItem('seeded')){
   localStorage.setItem('access_token','synthetic-p28-session')
   if(options.preference!==undefined)localStorage.setItem(prefKey,typeof options.preference==='string'?options.preference:JSON.stringify(options.preference))
   if(options.schemes)localStorage.setItem(schemeKey,JSON.stringify(options.schemes))
   localStorage.setItem(`pms:theme:v1:${encodeURIComponent(base)}:1`,options.theme||'blue');sessionStorage.setItem('seeded','1')
  }
  if(options.failReadAt){const original=Storage.prototype.getItem;let count=0;Storage.prototype.getItem=function(key){if(key===prefKey&&++count===options.failReadAt)throw new Error('synthetic read interruption');return original.call(this,key)}}
  if(options.failStorage){const original=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(key===prefKey)throw new Error('synthetic storage full');return original.call(this,key,value)}}
 },{prefKey,schemeKey,options,base})
 page.on('pageerror',e=>errors.push(e.message))
 const requests=[]
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),p=url.pathname
  if(url.origin!==base){errors.push('external request');return route.abort()}
  if(!p.startsWith('/api/'))return route.continue()
  requests.push(url.href);assert.equal(route.request().method(),'GET','no business writes in this acceptance')
  let body=[]
  if(p==='/api/auth/me')body={id:1,username:'fixture',real_name:'隔离验收',permissions:['project:archive:view',...(options.selection===false?[]:['project:archive:toggle'])]}
  else if(p==='/api/users/options')body=[{id:1,username:'fixture',real_name:'隔离验收'}]
  else if(p==='/api/projects/archives/fields'){
   body=structuredClone(source.metadata)
   if(options.hiddenLine){const field=body.items.find(i=>i.field_key==='product_line_id');Object.assign(field,{visible:false,list_available:false})}
  }else if(['/api/product-lines/options','/api/product-lines/labels'].includes(p)){
   if(options.failLabels&&p.endsWith('/labels'))return route.fulfill({status:503,json:{detail:'合成名称读取失败'}})
   body={options:source.lines,label_map:Object.fromEntries(source.lines.map(i=>[i.value,i.label]))}
  }else if(p.startsWith('/api/dicts/code/'))body=source.enums[p.split('/').at(-1)]||{items:[],label_map:{}}
  else if(p==='/api/projects/archives/list')body={total:1,items:[{id:89,project_code:'P28-SAMPLE',project_name:'隔离列布局验收',customer:'合成客户',product_line_id:options.unknownLine?99999:1,archive_category:1,manager_id:1,is_enabled:1,can_edit:false,change_version:'a'.repeat(64),erp_sync_status:'historical'}]}
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/archive');await expect(page.getByText('P28-SAMPLE',{exact:true})).toBeVisible()
 return {page,requests}
}
async function columns(page){return page.evaluate(async()=>{let component=document.querySelector('.column-picker-trigger').__vueParentComponent;while(component&&!component.props?.getGridApi)component=component.parent;const api=component?.props.getGridApi();if(!api)throw Error('actual grid API not ready');return {displayed:api.getAllDisplayedColumns().map(c=>c.getColId()),state:api.getColumnState()}})}
const legacy={selected_column_keys:['customer','project_code','project_name'],columnState:[{colId:'customer',width:231,pinned:'left',hide:false,sort:'asc',sortIndex:0},{colId:'project_name',width:291,hide:true},{colId:'project_code',width:161,pinned:null}]}
const scheme={version:2,name:'旧列方案',isDefault:true,definitions:[{field:'customer',shown:true,operator:'contains',value:'合成',valueEnd:null,schemaVersion:2}],preferences:{pageSize:100,columns:legacy}}
const current={layout_version:1,selected_column_keys:['project_name','project_code'],columnState:[{colId:'project_name',width:271,pinned:'left'},{colId:'product_line_id',hide:true,pinned:null},{colId:'project_code',pinned:null,width:162}]}
const local=(page,key)=>page.evaluate(key=>localStorage.getItem(key),key)
const picker=page=>page.locator('.column-picker-panel')
async function openPicker(page){await page.getByRole('button',{name:'打开项目档案列设置',exact:true}).click();await expect(picker(page)).toBeVisible()}
async function choose(page,scope,label,value){const input=scope.getByRole('combobox',{name:label,exact:true});await input.locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]').click();const id=await input.getAttribute('aria-controls');await input.press('ArrowDown');await input.press('Enter')}
async function savePicker(page){await picker(page).getByRole('button',{name:'保存',exact:true}).click();await expect(picker(page)).not.toBeVisible()}
async function leading(page,withSelection=true){await expect.poll(async()=> (await columns(page)).displayed.slice(0,withSelection?3:2)).toEqual(withSelection?['archive_selection','product_line_id','project_code']:['product_line_id','project_code'])}
try{
 let f=await fixture();await leading(f.page)
 let state=(await columns(f.page)).state;assert.equal(state.find(c=>c.colId==='product_line_id').pinned,'left');assert.equal(state.find(c=>c.colId==='project_code').pinned,'left')
 await expect(f.page.locator('.ag-cell[col-id="product_line_id"]')).toHaveText('8吋Bench')
 // Check rendered frozen headers remain in position while the center scrolls.
 const header=f.page.locator('.ag-pinned-left-header [col-id="product_line_id"]');const before=await header.boundingBox()
 await f.page.locator('.ag-center-cols-viewport').evaluate(el=>{el.scrollLeft=900;el.dispatchEvent(new Event('scroll'))})
 assert.equal((await header.boundingBox()).x,before.x)
 await f.page.screenshot({path:out+'/default.png',animations:'disabled'});checks.push('actual default first columns, names, initial freeze and horizontal scroll')
 f=await fixture({selection:false});await leading(f.page,false);checks.push('without selection permission product line is first actual column')
 f=await fixture({preference:legacy});await leading(f.page)
 state=(await columns(f.page)).state
 assert.equal(state.find(c=>c.colId==='customer').width,231);assert.equal(state.find(c=>c.colId==='customer').pinned,'left');assert.equal(state.find(c=>c.colId==='customer').sort,'asc')
 assert.equal(state.find(c=>c.colId==='project_name').width,291);assert.equal(state.find(c=>c.colId==='project_name').hide,true);assert.equal(state.find(c=>c.colId==='project_code').width,161)
 assert.equal(JSON.parse(await local(f.page,prefKey)).layout_version,1,'successful personal compatibility is persisted once')
 checks.push('legacy personal layout migration preserves widths, hidden fields, other freeze and sort')
 // Actual shared picker: unpin and move the line after name, save, refresh.
 await openPicker(f.page);await choose(f.page,picker(f.page),'产品线冻结区域','中间滚动')
 await choose(f.page,picker(f.page),'项目编号冻结区域','中间滚动')
 await picker(f.page).getByRole('button',{name:'下移产品线',exact:true}).click()
 await savePicker(f.page)
 const chosen=(await columns(f.page)).state;assert.equal(chosen.find(c=>c.colId==='product_line_id').pinned,null)
 assert.equal(JSON.parse(await local(f.page,prefKey)).layout_version,1)
 await f.page.reload();await expect(f.page.getByText('P28-SAMPLE',{exact:true})).toBeVisible()
 state=(await columns(f.page)).state;assert.equal(state.find(c=>c.colId==='product_line_id').pinned,null);assert.equal(state.find(c=>c.colId==='project_code').pinned,null)
 assert.deepEqual((await columns(f.page)).displayed,chosen.filter(c=>!c.hide).sort((a,b)=>{const rank=c=>c.pinned==='left'?0:c.pinned==='right'?2:1;return rank(a)-rank(b)}).map(c=>c.colId))
 checks.push('picker move and unpin survive save and reload')
 await openPicker(f.page);await picker(f.page).getByRole('checkbox',{name:'显示产品线列',exact:true}).locator('xpath=ancestor::label').click();await savePicker(f.page)
 await f.page.reload();await expect(f.page.getByText('P28-SAMPLE',{exact:true})).toBeVisible();assert.ok(!(await columns(f.page)).displayed.includes('product_line_id'));checks.push('later deliberate hiding survives reload')
 await openPicker(f.page);await picker(f.page).getByRole('button',{name:'恢复默认',exact:true}).click();await savePicker(f.page);await leading(f.page);checks.push('restore default uses new first-line layout')
 f=await fixture({preference:legacy,failReadAt:2});await leading(f.page);assert.equal((await columns(f.page)).state.find(c=>c.colId==='customer').width,231);const flaky=JSON.parse(await local(f.page,prefKey));assert.equal(flaky.columnState.find(c=>c.colId==='customer').width,231);checks.push('single initial preference snapshot prevents intermittent-read data loss')
 f=await fixture({preference:current});assert.ok(!(await columns(f.page)).displayed.includes('product_line_id'));assert.equal((await columns(f.page)).state.find(c=>c.colId==='project_code').pinned,null);checks.push('current-version preferences never forced back to defaults')
 f=await fixture({schemes:[scheme]});await leading(f.page);assert.ok(f.requests.some(url=>url.includes('/projects/archives/list')&&decodeURIComponent(url).includes('合成')),'named scheme condition must reach query');assert.equal(await local(f.page,schemeKey),JSON.stringify([scheme]),'reading a scheme cannot rewrite it')
 await openPicker(f.page);await picker(f.page).getByRole('checkbox',{name:'显示产品线列',exact:true}).locator('xpath=ancestor::label').click();await savePicker(f.page)
 await f.page.getByRole('button',{name:'方案设置',exact:true}).click();const settings=f.page.getByRole('dialog',{name:'查询方案设置',exact:true});await expect(settings).toBeVisible();await settings.getByRole('button',{name:'保存方案',exact:true}).click()
 const written=JSON.parse(await local(f.page,schemeKey));assert.equal(written[0].preferences.columns.layout_version,1);assert.ok(!written[0].preferences.columns.selected_column_keys.includes('product_line_id'));assert.equal(written[0].preferences.pageSize,100)
 await f.page.reload();await expect(f.page.getByText('P28-SAMPLE',{exact:true})).toBeVisible();assert.ok(!(await columns(f.page)).displayed.includes('product_line_id'));checks.push('old named scheme read-only adaptation and explicit-save marker preserve new choices')
 f=await fixture({hiddenLine:true,preference:legacy});assert.ok(!(await columns(f.page)).displayed.includes('product_line_id'));await openPicker(f.page);await expect(picker(f.page).getByRole('checkbox',{name:'显示产品线列',exact:true})).toHaveCount(0);checks.push('metadata-denied line not exposed or selectable')
 for(const preference of ['{invalid',JSON.stringify({...legacy,layout_version:99})]){
  f=await fixture({preference});await openPicker(f.page);await savePicker(f.page);assert.equal(await local(f.page,prefKey),preference)
 }checks.push('invalid and future storage strings remain intact')
 const old=JSON.stringify(legacy);f=await fixture({preference:old,failStorage:true});await leading(f.page);await openPicker(f.page);await savePicker(f.page);assert.equal(await local(f.page,prefKey),old);await expect(f.page.getByText('列设置无法读取或保存，暂用本次布局；可在列设置中恢复默认后重试',{exact:true})).toBeVisible();checks.push('write failure retains original preferences with warning')
 const failOptions={failLabels:true};f=await fixture(failOptions);await leading(f.page);await expect(f.page.locator('.ag-cell[col-id="product_line_id"]')).toHaveText('名称暂不可用');await f.page.getByRole('button',{name:'查看',exact:true}).click();await expect(f.page.getByRole('button',{name:'重试产品线名称',exact:true})).toBeVisible();failOptions.failLabels=false;await f.page.getByRole('button',{name:'重试产品线名称',exact:true}).click();await expect(f.page.locator('.ag-cell[col-id="product_line_id"]')).toHaveText('8吋Bench');checks.push('label failure never shows ID and existing retry recovers name')
 f=await fixture({unknownLine:true});await leading(f.page);await expect(f.page.locator('.ag-cell[col-id="product_line_id"]')).toHaveText('名称暂不可用');checks.push('unknown historical line uses existing safe label')
 for(const theme of ['blue','teal','graphite']){f=await fixture({theme});await leading(f.page);await expect(f.page.locator('html')).toHaveAttribute('data-pms-theme',theme);await f.page.screenshot({path:out+'/theme-'+theme+'.png',animations:'disabled'})}checks.push('three existing themes retain actual first-column and frozen layout')
 assert.deepEqual(errors,[])
 fs.writeFileSync(out+'/verification.json',JSON.stringify({passed:true,checks,errors,externalRequests:0,businessWrites:0},null,2)+'\n')
 console.log('PASS '+checks.length+' P28 scenarios')
}finally{await browser.close();await server.close()}
