import assert from 'node:assert/strict'
import { chromium } from '@playwright/test'

const base = process.env.PMS_TEST_URL || 'http://127.0.0.1:5174'
const permissions = ['system:user:view','system:role:view','system:parameter:view','system:dict:view','system:enum:view','system:field:view','system:field-policy:view','system:product-line:view','system:operation-log:view','system:sync:view','project:list:view']
const users = [{id:1,username:'alpha',real_name:'Alpha',status:1,role_names:['查询角色'],dept_id:1},{id:2,username:'beta',real_name:'Beta',status:0,role_names:['查询角色'],dept_id:1}]
const catalog = users.map(row => ({module:'user',module_name:'用户管理',group:'用户字段',field_name:row.real_name,field_code:row.username,value_type:'text',source_type:'database',editable:false,description:''}))
const parameters = users.map(row => ({code:row.username,name:row.real_name,group:'测试分组',description:'测试用途',sensitive:false,configured:false,value:null}))
const policies = users.map(row => ({field_key:row.username,label:row.real_name,group:'base',group_label:'基本信息',source_type:'detail',value_type:'text',visible:true,editable:false,required:false,list_available:true}))
const enumDef = {dict_code:'task_status',dict_name:'任务状态',items:[{value:'1',label:'启用'}],all_items:[{value:'1',label:'启用'},{value:'2',label:'历史禁用',status:0}],label_map:{1:'启用',2:'历史禁用'}}
let serverVersion = 2
const browser = await chromium.launch({headless:true,channel:'chrome'})
const context = await browser.newContext({viewport:{width:1440,height:950}})
let legacyComponent = ''
// Exercise dormant child lists without changing production routes.
await context.route(`${base}/src/router/index.ts`, async route => {
  const response = await route.fetch()
  const source = await response.text()
  await route.fulfill({response,body:legacyComponent ? source.replace('/src/views/system/EnumList.vue', `/src/views/system/${legacyComponent}.vue`) : source})
})
await context.addInitScript(() => localStorage.setItem('access_token','isolated-query-test'))
const calls = [], errors = [], writes = []
await context.route(`${base}/api/**`, async route => {
  const req = route.request(), url = new URL(req.url()), path = url.pathname.slice(4)
  calls.push(path + url.search)
  if (req.method() !== 'GET') { writes.push(path); await route.abort(); return }
  const page = Number(url.searchParams.get('page') || 1)
  let result = []
  if (path === '/auth/me') result = {id:701,username:'query-test',real_name:'查询测试',permissions,role_codes:[],status:1,data_scope:1,product_line_ids:[]}
  else if (path === '/users') result = {items:users.slice(page-1,page),total:2}
  else if (path === '/users/options') result = users
  else if (path === '/depts/tree' || path === '/depts/options') result = [{id:1,dept_name:'测试部门',children:[]}]
  else if (path === '/roles/options') result = [{id:1,role_name:'查询角色',status:1}]
  else if (path === '/roles') result = users.map(row => ({id:row.id,role_name:row.real_name,role_code:row.username,status:row.status,data_scope:1,product_line_ids:[]}))
  else if (path === '/parameters') result = {items:parameters}
  else if (path === '/field-catalog') result = {items:catalog.slice(page-1,page),total:2,modules:[{value:'user',label:'用户管理',count:2}]}
  else if (path === '/field-policies') result = {items:policies,groups:[{key:'base',label:'基本信息'}]}
  else if (path === '/product-lines') result = {items:users.slice(page-1,page).map(row => ({id:row.id,display_name:row.real_name,organization_code:row.username,organization_name:row.real_name,is_enabled:row.status,sort:0})),total:2}
  else if (path === '/product-lines/role-options') result = {items:[]}
  else if (path === '/dicts') result = [{id:1,dict_code:'task_status',dict_name:'任务状态',mode:'configurable',item_count:2,bindings:[]}]
  else if (path === '/dicts/1/items') result = users.map(row => ({id:row.id,item_value:String(row.id),item_label:row.real_name,status:row.status,sort:0,reference_count:0}))
  else if (path.startsWith('/dicts/code/')) result = enumDef
  else if (path === '/projects/1/tasks') result = users.map(row => ({id:row.id,task_name:row.real_name,status:row.id,assignee_name:row.real_name,progress:0,sort:row.id}))
  else if (path === '/projects/sheet-fields') result = {fields:[],groups:[],policies:[]}
  else if (path === '/projects/archives/options') result = []
  else if (path === '/projects') result = {items:users.map(row => ({id:row.id,project_code:row.username,project_name:row.real_name,status:row.id,dept_id:1,dept_name:'测试部门',pm_id:row.id,pm_name:row.real_name,total_progress:0,sheet_fields:{}})),total:2}
  else if (path.startsWith('/operation-logs') || path.startsWith('/sync-tasks')) {
    const source = users.map(row => ({id:row.id,archive_id:row.id,project_code:row.real_name,project_name:row.real_name,operator_name:row.real_name,entity_name:row.real_name,module:'系统管理',action:'update',status:row.status?'success':'failed',status_label:row.status?'同步成功':'同步失败',summary:row.real_name,created_at:'2026-10-11T10:00:00',attempts:1,message:''}))
    const filters = JSON.parse(url.searchParams.get('filters') || '[]')
    const columns = JSON.parse(url.searchParams.get('column_filters') || '[]')
    const matched = source.filter(row => filters.every(c => c.operator === 'contains' ? String(row[c.field]).includes(String(c.value)) : c.operator === 'reference' || c.operator === 'in' ? c.value.includes(row[c.field]) : row[c.field] === c.value) && columns.every(c => c.mode !== 'values' || c.values.includes(row[c.field])))
    if (path.endsWith('/column-values')) result = {items:[...new Set(matched.map(row => row[url.searchParams.get('field')]))].map(value => ({value,label:value==='failed'?'失败':value==='success'?'成功':String(value),count:matched.filter(row => row[url.searchParams.get('field')]===value).length})),hasMore:false}
    else result = {query_version:serverVersion,items:matched.slice(page-1,page),total:matched.length,worker_enabled:false}
  }
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(result)})
})
const page = await context.newPage()
page.on('pageerror', error => { errors.push(error.stack || error.message); console.error(error.stack || error.message) })
try {
  await page.goto(`${base}/system/user`)
  const table = page.locator('.el-table__body-wrapper')
  await table.getByText('Beta',{exact:true}).waitFor()
  assert.ok(calls.some(call => call.startsWith('/users?') && call.includes('page=2')), '用户完整读取第二页')
  await page.getByRole('textbox',{name:'查询2值',exact:true}).fill('Beta')
  assert.equal(await table.getByText('Alpha',{exact:true}).count(),1,'改草稿仍保留原结果')
  await page.locator('.pms-query-workspace').getByRole('button',{name:'查询',exact:true}).click()
  await table.getByText('Alpha',{exact:true}).waitFor({state:'hidden'})
  assert.equal(await table.getByText('Beta',{exact:true}).count(),1)
  await page.locator('button[aria-label="状态列筛选"]:visible').click()
  const panel = page.getByRole('dialog',{name:'状态列筛选面板'})
  await panel.getByText('禁用',{exact:true}).waitFor()
  assert.equal(await panel.getByText('启用',{exact:true}).count(),0,'候选值受已提交顶部结果约束')
  await panel.locator('.pms-column-filter-values label').last().click()
  await panel.getByRole('button',{name:'应用',exact:true}).click()
  await table.getByText('Beta',{exact:true}).waitFor({state:'hidden'})
  await page.getByRole('button',{name:'重置',exact:true}).click()
  await table.getByText('Beta',{exact:true}).waitFor()
  await page.locator('.pms-query-workspace').getByRole('button',{name:'查询',exact:true}).click()
  await table.getByText('Alpha',{exact:true}).waitFor()
  assert.equal(await page.getByRole('button',{name:'新增用户',exact:true}).count(),0,'只读权限不增加业务写操作')
  await page.screenshot({path:'/private/tmp/pms-system-query-user-desktop.png'})
  for (const path of ['/system/role','/system/parameter','/system/dict','/system/field-policy','/system/product-line','/system/enum','/project/list','/project/1/progress']) {
    await page.goto(base + path)
    await page.locator('.pms-query-workspace').waitFor()
    const cells = page.locator('.el-table__body-wrapper, .ag-row')
    await cells.getByText('Beta',{exact:true}).first().waitFor()
    if (path.startsWith('/project/')) assert.equal(await page.locator('button[aria-label$="列筛选"]:visible').first().isDisabled(),true,'项目未提交查询不取全量候选')
    await page.getByRole('textbox',{name:path === '/project/list'?'查询2值':'查询1值',exact:true}).fill('Beta')
    await page.locator('.pms-query-workspace').getByRole('button',{name:'查询',exact:true}).click()
    await cells.getByText('Alpha',{exact:true}).first().waitFor({state:'hidden'})
    assert.ok(await cells.getByText('Beta',{exact:true}).count() > 0, path + ' 显式查询保留匹配行')
    console.log(`system-query browser smoke: ${path}`)
  }
  for (const path of ['/system/operation-log','/system/sync']) {
    await page.goto(base + path)
    const cells = page.locator('.el-table__body-wrapper')
    await cells.getByText('Alpha',{exact:true}).first().waitFor()
    assert.equal(await page.locator('button[aria-label$="列筛选"]:visible').first().isDisabled(),true,'后台页未提交查询不取全量候选')
    const input = page.getByRole('textbox',{name:path.endsWith('operation-log')?'查询4值':'查询1值',exact:true})
    await input.fill('Beta')
    assert.equal(await cells.getByText('Beta',{exact:true}).count(),0,'服务端第二页尚未显示')
    await page.locator('.pms-query-workspace').getByRole('button',{name:'查询',exact:true}).click()
    await cells.getByText('Beta',{exact:true}).first().waitFor()
    assert.equal(await cells.getByText('Alpha',{exact:true}).count(),0,'服务端完整范围过滤后分页')
    await page.locator(`button[aria-label="${path.endsWith('operation-log')?'状态':'同步状态'}列筛选"]:visible`).click()
    await page.getByRole('dialog').getByText('失败',{exact:true}).waitFor()
    assert.ok(calls.some(call => call.startsWith(path.endsWith('operation-log')?'/operation-logs/column-values':'/sync-tasks/column-values')),'使用真实候选endpoint协议')
    await page.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).click()
    console.log(`system-query server browser protocol: ${path}`)
  }
  for (const component of ['MenuList','FieldList']) {
    legacyComponent = component
    await page.goto(base + '/system/enum')
    await page.locator(component === 'MenuList' ? '.dict-item' : '.field-item').first().click()
    const cells = page.locator('.el-table__body-wrapper')
    await cells.getByText('Beta',{exact:true}).first().waitFor()
    await page.getByRole('textbox',{name:'查询1值',exact:true}).fill('Beta')
    await page.locator('.pms-query-workspace').getByRole('button',{name:'查询',exact:true}).click()
    await cells.getByText('Alpha',{exact:true}).waitFor({state:'hidden'})
    assert.equal(await cells.getByText('Beta',{exact:true}).count(),1)
    console.log(`system-query child browser: ${component}`)
  }
  legacyComponent = ''
  serverVersion = 0
  await page.goto(base + '/system/sync')
  await page.getByText('同步任务接口尚未声明查询 v2 支持', {exact:false}).waitFor()
  assert.equal(await page.locator('.pms-query-workspace').getByRole('button',{name:'查询',exact:true}).isDisabled(),true,'旧接口显式拒绝，不静默忽略条件')
  assert.deepEqual(errors,[],'页面运行时无错误')
  assert.deepEqual(writes,[],'只读测试没有业务写请求')
  console.log('system-query browser passed: complete data, explicit submit, column candidates, clear, read-only routes')
} catch (error) {
  console.error({url:page.url(),errors,calls,body:(await page.locator('body').innerText()).slice(0,4000)})
  throw error
} finally { await browser.close() }
