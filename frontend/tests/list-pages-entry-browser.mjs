import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { chromium, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
const server=await createServer({server:{host:'127.0.0.1',port:19264,strictPort:true},cacheDir:'../.runtime/list-pages-entry-cache',optimizeDeps:{entries:['index.html']}})
let browser, page
const field=(key,label,value_type='text')=>({key,label,value_type,width:140,group:'基本信息'})
const organizations=[{value:2,label:'8吋Bench'}]
const purchase={organizations,fields:[field('product_line_name','产品线'),field('project_code','项目编码'),field('bill_no','申请单编号')],overview_fields:[field('product_line_name','产品线'),field('project_code','项目编码'),field('completion_rate','申请行入库率','number'),field('conversion_rate','申请行转单率','number'),field('total_lines','申请行数','number')],query_fields:[{field:'application_date',label:'申请日期',type:'date'}],document_status_labels:{C:'已审核'},progress_labels:{complete:'已完成'},start_date:'2026-01-01'}
const stock={organizations,fields:[field('material_code','物料编码'),field('income_qty','收入','number')],query_fields:[]}
const inventory={organizations,fields:[field('product_line_name','产品线'),field('MaterialName','物料名称')],query_fields:[]}
const calls={archive:[],project:[],report:[],role:[]},errors=[]
try{
 await server.listen();browser=await chromium.launch({channel:'msedge',headless:true})
 page=await browser.newPage({viewport:{width:1366,height:768}});page.setDefaultTimeout(10000)
 page.on('pageerror',e=>errors.push(e.message))
 page.on('console',m=>{if(m.type()==='error')console.error(m.text())})
 page.on('requestfailed',r=>console.error(r.url(),r.failure()))
 await page.addInitScript(()=>{
  localStorage.setItem('access_token','isolated-list-entry-test')
  localStorage.setItem('pms:query-workspace:v2:777:project-archive',JSON.stringify([{version:2,name:'本人默认',isDefault:true,definitions:[{field:'project_code',shown:true,operator:'equals',value:'A-202503',valueEnd:null}],preferences:{pageSize:100,columns:{selected_column_keys:['customer'],columnState:[{colId:'project_code',width:245},{colId:'archive_actions',width:500,flex:2}]}}}]))
  localStorage.setItem('pms:purchase-overview:v1:777',JSON.stringify({metricLayoutVersion:1,reportIdentityVersion:1,columns:[{colId:'purchase_actions',width:500,flex:1,hide:true}]}))
  localStorage.setItem('pms:query-workspace:v2:777:project-progress-list',JSON.stringify([{version:2,name:'旧操作列默认',isDefault:true,definitions:[{field:'project_code',shown:true,operator:'contains',value:null,valueEnd:null}],preferences:{columnState:[{colId:'progress_actions',hide:true,pinned:null,flex:2,width:500}]}}]))
 })
 await page.route('**/api/**',async route=>{
  const u=new URL(route.request().url()),path=u.pathname;let body=[]
  if(!path.startsWith('/api/'))return route.continue()
 if(path==='/api/auth/me')body={id:777,username:'fixture',real_name:'隔离验收',permissions:['project:archive:view','project:list:view','project:list:delete','system:role:view','system:role:edit','report:purchase:view','report:inventory:view','report:stock-detail:list'],data_scope:4}
  else if(path==='/api/auth/product-categories')body={unrestricted:true}
  else if(path==='/api/product-lines/options')body={options:[{id:2,label:'8吋Bench'}],label_map:{2:'8吋Bench'}}
  else if(path.includes('/dicts/code/'))body={items:[],all_items:[],label_map:{}}
  else if(path==='/api/projects/archives/fields'||path==='/api/projects/sheet-fields')body={items:[]}
  else if(path==='/api/projects/archives/list'){calls.archive.push(Object.fromEntries(u.searchParams));body={items:[{id:1,project_code:'A-202503',project_name:'测试项目',customer:'测试客户',is_enabled:1,can_delete:false}],total:1}}
  else if(path==='/api/projects'){calls.project.push(Object.fromEntries(u.searchParams));body={items:[{id:2,archive_id:1,project_code:'A-202503',project_name:'测试进度',status:1,sheet_fields:{}}],total:1}}
  else if(path.endsWith('/metadata'))body=path.includes('inventory')?inventory:path.includes('stock-detail')?stock:purchase
  else if(path==='/api/reports/purchase/overview'){calls.report.push(path);body={items:[{id:'2:A-202503',organization_id:2,product_line_name:'8吋Bench',project_code:'A-202503',completion_rate:90.7,conversion_rate:96.3,total_lines:216}],total:1,total_lines:216,complete_lines:196,review_lines:0}}
  else if(['/api/reports/inventory','/api/reports/purchase','/api/reports/stock-detail'].includes(path)){calls.report.push(path);body={items:[],total:0}}
  else if(path==='/api/roles'&&route.request().method()==='GET')body=[{id:1,role_name:'仅查看测试角色',role_code:'test',status:1,data_scope:1}]
  else if(path==='/api/menus/tree')body=[{id:10,parent_id:0,menu_type:'C',menu_name:'问题提报',path:'/feedback',status:1,visible:1,permission_code:'feedback:view',children:[{id:11,parent_id:10,menu_type:'B',menu_name:'新增',permission_code:'feedback:add',status:1},{id:12,parent_id:10,menu_type:'B',menu_name:'处理全部提报',permission_code:'feedback:handle',status:1}]}]
  else if(path==='/api/roles/1/menus')body={menu_ids:[10]}
  else if(path==='/api/product-lines/role-options')body={items:[]}
  else if(path==='/api/roles/1'&&route.request().method()==='PUT'){calls.role.push(route.request().postDataJSON());body={id:1}}
  await route.fulfill({json:body})
 })
 const base='http://127.0.0.1:19264'
 await page.goto(base+'/project/archive')
 await expect(page.getByText('共 1 条',{exact:true})).toBeVisible()
 assert.equal(calls.archive.length,1,'单据首查不重复')
 assert.equal(calls.archive[0].page_size,'100')
 assert.ok(JSON.parse(calls.archive[0].filters).some(f=>f.field==='project_code'&&f.value==='A-202503'))
 const width=key=>page.locator(`.ag-header-cell[col-id="${key}"]`).evaluate(e=>Math.round(e.getBoundingClientRect().width))
 assert.equal(await width('archive_actions'),64)
 assert.equal(await width('project_code'),245,'个人业务列宽度保留')
 await page.goto(base+'/reports/purchase-progress')
 await expect(page.locator('.purchase-overview-page .pms-query-workspace')).toBeVisible()
 assert.equal(calls.report.length,0)
 assert.equal(await width('purchase_actions'),64,'旧500px操作列迁移')
 await page.getByRole('button',{name:'查询',exact:true}).click()
 await expect.poll(()=>calls.report.length).toBe(1)
 await page.getByRole('button',{name:'明细',exact:true}).click()
 await expect.poll(()=>calls.report.length).toBe(2)
 assert.equal(calls.report[1],'/api/reports/purchase','保持显式下钻联动')
 await page.goto(base+'/reports/inventory')
 await expect(page.locator('.pms-query-workspace')).toBeVisible()
 assert.equal(calls.report.length,2)
 assert.equal(await page.locator('.ag-header-cell[col-id="purchase_actions"]').count(),0)
 await page.goto(base+'/reports/stock-detail')
 await expect(page.locator('[data-field="material"] .pms-condition-required')).toBeVisible()
 await expect(page.locator('[data-field="organization_ids"] .pms-condition-required')).toBeVisible()
 await expect(page.getByRole('button',{name:'查询',exact:true})).toBeDisabled()
 assert.equal(calls.report.length,2)
 assert.ok(!await page.locator('.pms-condition-field').allTextContents().then(values=>values.join('')).then(text=>text.includes('必填')||text.includes('必选')))
 await mkdir('../outputs/list-entry-20261013',{recursive:true})
 await page.screenshot({path:'../outputs/list-entry-20261013/stock-required-isolated.png'})
 await page.goto(base+'/project/archive')
 await expect.poll(()=>calls.archive.length).toBe(2,'重新进入单据刷新')
 await page.goto(base+'/project/list')
 await expect(page.locator('.ag-header-cell[col-id="progress_actions"]')).toBeVisible()
 await expect.poll(()=>calls.project.length).toBe(1)
 assert.equal(await width('progress_actions'),96)
 await expect(page.getByRole('button',{name:'项目编号列筛选',exact:true})).toBeEnabled()
 await page.goto(base+'/system/role')
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 const drawer=page.locator('.pms-form-drawer:visible')
 const choice=id=>drawer.locator('.el-tree-node__content').filter({has:page.locator(`.perm-node[data-id="${id}"]`)}).locator('.el-checkbox')
 await expect(choice(-10).getByRole('checkbox')).toBeChecked()
 await expect(choice(11).getByRole('checkbox')).not.toBeChecked()
 await choice(11).click()
 await expect(choice(-10).getByRole('checkbox')).toBeChecked()
 await expect(choice(12).getByRole('checkbox')).not.toBeChecked()
 await drawer.getByRole('button',{name:'保存',exact:true}).click()
 await expect.poll(()=>calls.role.length).toBe(1)
 assert.deepEqual(calls.role[0].menu_ids.sort((a,b)=>a-b),[10,11],'真实角色页面只提交现有查看和新增ID')
 assert.deepEqual(errors,[])
 console.log('Actual pages passed: archive default once/reentry/old columns, progress ready, 3 reports idle, drilldown, required, menu-level view role')
}catch(error){console.error(JSON.stringify({errors,calls,url:page?.url(),body:await page?.locator('body').innerText()}));throw error}
finally{await browser?.close();await server.close()}
