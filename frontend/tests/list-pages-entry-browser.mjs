import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { chromium, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
const server=await createServer({server:{host:'127.0.0.1',port:19264,strictPort:true},cacheDir:'../.runtime/list-pages-entry-cache',optimizeDeps:{entries:['index.html']}})
let browser, page
const field=(key,label,value_type='text')=>({key,label,value_type,width:140,group:'基本信息'})
const organizations=[{value:2,label:'8吋Bench'}]
const purchase={organizations,fields:[field('product_line_name','产品线'),field('project_code','项目编码'),field('bill_no','申请单编号')],overview_fields:[field('product_line_name','产品线'),field('project_code','项目编码'),field('completion_rate','申请行入库率','number'),field('conversion_rate','申请行转单率','number'),field('total_lines','申请行数','number')],query_fields:[{field:'bill_no',label:'申请单编号',type:'text'},{field:'application_date',label:'申请日期',type:'date'}],document_status_labels:{C:'已审核'},progress_labels:{complete:'已完成'},start_date:'2026-01-01'}
const stock={organizations,fields:[field('material_code','物料编码'),field('income_qty','收入','number')],query_fields:[]}
const inventory={organizations,fields:[field('product_line_name','产品线'),field('MaterialName','物料名称')],query_fields:[{field:'MaterialCode',label:'物料编码',type:'text'}]}
const calls={archive:[],project:[],report:[],role:[],stock:[]},errors=[]
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
 if(path==='/api/auth/me')body={id:777,username:'fixture',real_name:'隔离验收',permissions:['project:archive:view','project:list:view','project:list:delete','system:role:view','system:role:edit','report:purchase:view','report:inventory:view','report:stock-detail:list','feedback:view'],data_scope:4}
  else if(path==='/api/auth/product-categories')body={unrestricted:true}
  else if(path==='/api/product-lines/options')body={options:[{id:2,label:'8吋Bench'}],label_map:{2:'8吋Bench'}}
  else if(path.includes('/dicts/code/'))body={items:[],all_items:[],label_map:{}}
  else if(path==='/api/projects/archives/fields'||path==='/api/projects/sheet-fields')body={items:[]}
  else if(path==='/api/projects/archives/list'){calls.archive.push(Object.fromEntries(u.searchParams));body={items:[{id:1,project_code:'A-202503',project_name:'测试项目',customer:'测试客户',is_enabled:1,can_delete:false}],total:1}}
  else if(path==='/api/projects'){calls.project.push(Object.fromEntries(u.searchParams));body={items:[{id:2,archive_id:1,project_code:'A-202503',project_name:'测试进度',status:1,sheet_fields:{}}],total:1}}
  else if(path.endsWith('/metadata'))body=path.includes('inventory')?inventory:path.includes('stock-detail')?stock:purchase
  else if(path==='/api/reports/purchase/overview'){calls.report.push(path);body={items:[{id:'2:A-202503',organization_id:2,product_line_name:'8吋Bench',project_code:'A-202503',completion_rate:90.7,conversion_rate:96.3,total_lines:216}],total:1,total_lines:216,complete_lines:196,review_lines:0}}
  else if(['/api/reports/inventory','/api/reports/purchase','/api/reports/stock-detail'].includes(path)){calls.report.push(path);if(path.endsWith('stock-detail'))calls.stock.push(Object.fromEntries(u.searchParams));body={items:[],total:0}}
  else if(path==='/api/roles'&&route.request().method()==='GET')body=[{id:1,role_name:'仅查看测试角色',role_code:'test',status:1,data_scope:1}]
  else if(path==='/api/menus/tree')body=[{id:10,parent_id:0,menu_type:'C',menu_name:'问题提报',path:'/feedback',status:1,visible:1,permission_code:'feedback:view',children:[{id:11,parent_id:10,menu_type:'B',menu_name:'新增',permission_code:'feedback:add',status:1},{id:12,parent_id:10,menu_type:'B',menu_name:'处理全部提报',permission_code:'feedback:handle',status:1}]}]
  else if(path==='/api/roles/1/menus')body={menu_ids:[10]}
  else if(path==='/api/product-lines/role-options')body={items:[]}
  else if(path==='/api/feedback')body={items:[],total:0}
  else if(path==='/api/feedback/stats')body={total:0,open:0,completed:0,issues:0,requests:0,statuses:{},modules:[],categories:[]}
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
 await expect(page.locator('[data-field="material_code"] .pms-condition-required')).toBeVisible()
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
 await expect(drawer).not.toBeVisible()
 assert.deepEqual(calls.role[0].menu_ids.sort((a,b)=>a-b),[10,11],'真实角色页面只提交现有查看和新增ID')
 await page.goto(base+'/reports/stock-detail')
 await expect(page.locator('[data-field="material_code"]')).toBeVisible()
 await page.locator('[data-field="material_code"] .pms-condition-field .el-select__wrapper').click()
 await page.getByRole('option',{name:'物料名称',exact:true}).click()
 await page.getByRole('textbox',{name:'查询1值',exact:true}).fill('PFA')
 await page.getByRole('button',{name:'查询2引用值',exact:true}).click()
 const reference=page.getByRole('dialog')
 await reference.getByRole('table',{name:'引用记录列表'}).getByRole('row').filter({hasText:'8吋Bench'}).locator('.el-checkbox').click()
 await reference.getByRole('button',{name:'确认引用',exact:true}).click()
 await expect(reference).not.toBeVisible()
 await expect(page.locator('[data-field="material_name"] .pms-condition-required')).toBeVisible()
 await expect(page.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
 await page.getByRole('button',{name:'查询',exact:true}).click()
 await expect.poll(()=>calls.stock.length).toBe(1)
 assert.equal(calls.stock[0].material_field,'material_name')
 assert.equal(calls.stock[0].material,'PFA')
 assert.equal(calls.stock[0].material_operator,'contains')
 assert.equal(JSON.parse(calls.stock[0].filters)[0].field,'material_name')
 await expect(page.locator('.pms-query-workspace').getByRole('button',{name:'查询',exact:true})).not.toHaveClass(/is-loading/)
 await page.addInitScript(()=>localStorage.setItem('pms:query-workspace:v2:777:project-archive',JSON.stringify([{version:2,name:'旧综合搜索',isDefault:true,definitions:[{field:'keyword',shown:true,operator:'contains',value:'M1',valueEnd:null}],preferences:{}}])))
 await page.goto(base+'/project/archive')
 await expect(page.getByRole('alert')).toContainText('包含已取消的字段')
 await expect(page.getByRole('button',{name:'查询',exact:true})).toBeDisabled()
 assert.equal(calls.archive.length,2,'失效综合条件不得静默丢弃后首查')
 assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('pms:query-workspace:v2:777:project-archive'))[0].definitions[0].value),'M1')
 await page.goto(base+'/feedback')
 await page.getByRole('button',{name:'说明',exact:true}).click()
 await expect(page.getByRole('dialog')).toContainText('邮件收件人')
 await page.getByRole('button',{name:'字段逻辑',exact:true}).click()
 const popup=page.context().waitForEvent('page')
 await page.getByRole('link',{name:'新页签打开',exact:true}).click()
 const guidePage=await popup
 await guidePage.waitForURL('**/page-guide/feedback#**')
 await expect(guidePage.getByRole('heading',{name:'问题提报',exact:true})).toBeVisible()
 await expect(guidePage.getByRole('rowheader',{name:'跟进 处理状态',exact:true})).toBeVisible()
 await guidePage.close()
 await page.goto(base+'/reports/stock-detail')
 await page.getByRole('button',{name:'方案设置',exact:true}).click()
 const settings=page.locator('.pms-query-settings-drawer:visible')
 await expect(settings.getByRole('checkbox',{name:'物料编码默认展示',exact:true})).toBeEnabled()
 await settings.getByRole('checkbox',{name:'物料编码默认展示',exact:true}).locator('..').click()
 await settings.getByRole('textbox',{name:'方案名称',exact:true}).fill('名称单字段方案')
 await settings.getByRole('button',{name:'保存方案',exact:true}).click()
 await expect(settings.getByText('物料至少展示一项正向匹配条件',{exact:true})).toBeVisible()
 await settings.getByRole('checkbox',{name:'物料名称默认展示',exact:true}).locator('..').click()
 await settings.getByRole('textbox',{name:'默认物料名称值',exact:true}).fill('PFA')
 await settings.getByRole('textbox',{name:'方案名称',exact:true}).fill('名称单字段方案')
 await settings.getByRole('button',{name:'保存方案',exact:true}).click()
 await expect(settings).not.toBeVisible()
 await expect(page.locator('[data-field="material_code"]')).toHaveCount(0)
 await expect(page.locator('[data-field="material_name"] .pms-condition-required')).toBeVisible()
 assert.equal(calls.stock.length,1,'保存方案不自动读取报表')
 assert.deepEqual(errors,[])
 console.log('Actual pages passed: default/reentry, reports idle, single material query, legacy scheme blocked, name-only settings/error, feedback guide/new tab, role view')
}catch(error){console.error(JSON.stringify({errors,calls,url:page?.url(),body:await page?.locator('body').innerText()}));throw error}
finally{await browser?.close();await server.close()}
