import {createServer} from 'vite'
import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
import {fixtureResponse,pages} from './fixtures/theme-application-api.mjs'
const server=await createServer({server:{host:'127.0.0.1',port:0}})
let browser
const errors=[],requests=[],unknown=[],checks=[]
const output=new URL('../../outputs/theme-application/',import.meta.url)
await mkdir(output,{recursive:true})
try{
  await server.listen()
  const base=`http://127.0.0.1:${server.httpServer.address().port}`
  browser=await chromium.launch({channel:'msedge',headless:true})
  const context=await browser.newContext({viewport:{width:1440,height:900}})
  context.setDefaultTimeout(12000)
  await context.addInitScript(()=>localStorage.setItem('access_token','isolated-theme-test'))
  const page=await context.newPage()
  page.setDefaultTimeout(15000)
  page.on('pageerror',e=>errors.push(e.message))
  await context.route('**/api/**',route=>{
    const request=route.request(),url=new URL(request.url()),path=url.pathname.replace(/^\/api/,'')
    if(!url.pathname.startsWith('/api/'))return route.continue()
    requests.push({path,method:request.method(),query:Object.fromEntries(url.searchParams)})
    try{return route.fulfill({json:fixtureResponse(path,url.searchParams,request.method(),request.postData()?request.postDataJSON():{})})}
    catch(error){unknown.push(String(error));return route.fulfill({status:501,json:{detail:String(error)}})}
  })
  await page.goto(base+'/reports/purchase-progress')
  try{await expect(page.getByRole('button',{name:'切换外观',exact:true})).toBeVisible({timeout:15000})}catch(error){console.error({errors,unknown,url:page.url(),body:await page.locator('body').innerText()});throw error}
  checks.push('actual application shell has the shared appearance switcher')
  await expect(page.locator('.purchase-overview-page').getByRole('button',{name:'查询',exact:true})).toBeEnabled()
  assert.equal(requests.filter(r=>r.path==='/reports/purchase/overview').length,0,'report queried on entry')
  for(const [id,name] of [['blue','办公蓝'],['teal','青绿'],['graphite','石墨']]){
    await page.getByRole('button',{name:'切换外观',exact:true}).click()
    await page.getByRole('menuitem',{name,exact:true}).click()
    await expect(page.locator('html')).toHaveAttribute('data-pms-theme',id)
    assert.equal(requests.filter(r=>r.path==='/reports/purchase/overview').length,0)
  }
  await page.locator('.purchase-overview-page').getByRole('button',{name:'查询',exact:true}).click()
  await expect(page.getByRole('progressbar').first()).toBeVisible()
  for(const stage of ['low','mid','complete'])await expect(page.locator(`[data-progress-stage="${stage}"]`).first()).toBeVisible()
  await expect(page.locator('[row-id="line1:5"] [col-id="completion_rate"] [data-progress-stage="mid"]').first()).toContainText('100.0%')
  for(const name of ['办公蓝','青绿','石墨']){
    await page.getByRole('button',{name:'切换外观',exact:true}).click();await page.getByRole('menuitem',{name,exact:true}).click()
    for(const [stage,color] of [['low','rgb(200, 52, 52)'],['mid','rgb(182, 139, 0)'],['complete','rgb(8, 126, 101)']])await expect(page.locator(`[data-progress-stage="${stage}"] .pms-progress-indicator__track>span`).first()).toHaveCSS('background-color',color)
  }
  checks.push('three themes preserve pending report entry and approved progress stages')
  await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
  await expect(page.locator('.purchase-page')).toBeVisible()
  checks.push('actual purchase overview/detail switch remains functional')
  for(const [path,title] of [...pages,['/project/1/progress','进度填报']]){
    await page.goto(base+path)
    await expect(page.locator('.app-header')).toContainText(title,{timeout:15000})
    await expect(page.locator('.el-loading-mask:visible,.ag-overlay-loading-center:visible')).toHaveCount(0,{timeout:15000})
    const query=page.getByRole('button',{name:'查询',exact:true}).first()
    if(await query.count()&&path!=='/reports/stock-detail')await expect(query).toBeEnabled({timeout:15000})
    for(const [id,name] of [['blue','办公蓝'],['teal','青绿'],['graphite','石墨']]){
      const before=requests.length
      await page.getByRole('button',{name:'切换外观',exact:true}).click()
      await page.getByRole('menuitem',{name,exact:true}).click()
      await expect(page.locator('html')).toHaveAttribute('data-pms-theme',id)
      assert.equal(requests.length,before,`${path}: theme triggered a data request`)
      const remnants=await page.evaluate(()=>{
        const old=new Set(['rgb(79, 70, 229)','rgb(89, 99, 142)','rgb(238, 242, 255)','rgb(199, 210, 254)','rgb(64, 158, 255)'])
        return [...document.body.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().width&&e.getBoundingClientRect().height).flatMap(e=>{const s=getComputedStyle(e);return ['color','backgroundColor','borderTopColor'].filter(k=>old.has(s[k])).map(k=>({element:e.tagName+'.'+String(e.className),property:k,color:s[k]}))}).slice(0,8)
      })
      assert.deepEqual(remnants,[],`${path}: leftover old theme colors`)
      await page.screenshot({path:new URL(path.replaceAll('/','-').slice(1)+'-'+id+'.png',output).pathname,animations:'disabled'})
    }
    checks.push(`${path}: actual page renders in three themes, no theme-triggered data query or old accent`)
  }
  const choose=async(name)=>{await page.getByRole('button',{name:'切换外观',exact:true}).click();await page.getByRole('menuitem',{name,exact:true}).click()}
  const openControl=async(name,scope=page)=>{await scope.locator('.pms-form-control').filter({has:page.getByRole('combobox',{name,exact:true})}).click()}
  const screenshot=async name=>page.screenshot({path:new URL(name+'.png',output).pathname,animations:'disabled'})
  await page.goto(base+'/reports/inventory')
  await expect(page.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
  const inventoryReads=requests.filter(r=>r.path==='/reports/inventory').length
  await page.getByRole('button',{name:'查询',exact:true}).click()
  await expect(page.locator('.ag-row[role="row"]').first()).toBeVisible()
  assert.equal(requests.filter(r=>r.path==='/reports/inventory').length,inventoryReads+1)
  for(const name of ['办公蓝','青绿','石墨']){
    const before=requests.length
    await choose(name)
    await openControl('查询1字段名')
    await expect(page.getByRole('option',{name:'物料名称',exact:true})).toBeVisible()
    await screenshot('inventory-field-'+name);await page.keyboard.press('Escape')
    await page.getByRole('button',{name:'物料编码列筛选',exact:true}).click()
    await expect(page.getByRole('dialog',{name:'物料编码列筛选面板',exact:true})).toContainText('仅筛选当前页')
    await screenshot('inventory-filter-'+name)
    await page.getByRole('button',{name:'物料名称列筛选',exact:true}).click()
    await expect(page.locator('.pms-column-filter-panel')).toHaveCount(1)
    await page.locator('.header-title').click();await expect(page.locator('.pms-column-filter-panel')).toHaveCount(0)
    await page.locator('.pagination-right .el-select__wrapper').click()
    await expect(page.getByRole('option',{name:'500 条/页',exact:true})).toBeVisible()
    await screenshot('inventory-pagination-'+name);await page.keyboard.press('Escape')
    assert.equal(requests.length,before,'theme/control expansion queried business data')
  }
  checks.push('inventory: real query, three-theme field/filter/pagination expansion, single popup and outside close')
  await page.goto(base+'/reports/stock-detail')
  await expect(page.locator('.pms-condition-row[data-field="material_code"]')).toBeVisible()
  await expect(page.getByRole('button',{name:'查询',exact:true})).toBeDisabled()
  await expect(page.locator('.pms-condition-required')).toHaveCount(3)
  await page.locator('.pms-condition-row[data-field="material_code"]').getByRole('textbox').fill('MAT-1')
  await expect(page.getByRole('button',{name:'查询',exact:true})).toBeDisabled()
  await page.locator('.pms-condition-row[data-field="organization_ids"] .pms-condition-reference').click()
  const reference=page.getByRole('dialog',{name:'引用产品线',exact:true})
  await expect(reference).toBeVisible()
  await expect(reference.getByRole('columnheader',{name:'编码',exact:true})).toHaveCount(0)
  await reference.locator('.reference-table tbody tr').filter({hasText:'8吋Bench'}).locator('.el-checkbox__inner').click()
  await reference.getByRole('button',{name:'确认引用',exact:true}).click()
  await expect(reference).not.toBeVisible()
  await expect(page.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
  await page.getByRole('button',{name:'查询',exact:true}).click()
  await expect(page.locator('[col-id="income_qty"][role="gridcell"]').first()).toHaveText('6.00')
  for(const name of ['办公蓝','青绿','石墨']){
    await choose(name)
    await page.locator('.pms-condition-row[data-field="bill_date"] .el-date-editor').first().click()
    await expect(page.locator('.el-picker-panel:visible')).toHaveCount(1)
    await screenshot('stock-calendar-'+name);await page.keyboard.press('Escape')
  }
  checks.push('stock: required material/product-line/date rules, names-only line reference, real query and themed calendars')
  await page.goto(base+'/feedback')
  await expect(page.getByRole('button',{name:'新增提报',exact:true})).toBeEnabled()
  await page.getByRole('button',{name:'新增提报',exact:true}).click()
  const feedback=page.getByRole('dialog',{name:'新增提报',exact:true})
  await expect(feedback).toBeVisible()
  await feedback.getByRole('textbox',{name:'标题',exact:true}).fill('仅隔离主题草稿')
  for(const name of ['办公蓝','青绿','石墨']){
    const writes=requests.filter(r=>r.method!=='GET').length
    await choose(name)
    await expect(feedback.getByRole('textbox',{name:'标题',exact:true})).toHaveValue('仅隔离主题草稿')
    await openControl('提报类型',feedback)
    await expect(page.getByRole('option',{name:'问题',exact:true})).toBeVisible()
    await screenshot('feedback-draft-'+name);await page.keyboard.press('Escape')
    assert.equal(requests.filter(r=>r.method!=='GET').length,writes)
  }
  checks.push('feedback: actual required-type dropdown and dirty draft survive theme changes without a write')
  await page.goto(base+'/system/user')
  await page.getByRole('button',{name:'新增用户',exact:true}).click()
  const user=page.getByRole('dialog',{name:'新增用户',exact:true})
  await expect(user).toBeVisible()
  for(const name of ['办公蓝','青绿','石墨']){
    await choose(name)
    await openControl('部门',user)
    await expect(page.getByRole('treeitem').filter({hasText:'示例项目部'}).first()).toBeVisible()
    await screenshot('user-tree-'+name);await page.keyboard.press('Escape')
    await openControl('角色',user)
    await expect(page.getByRole('option',{name:'试点角色',exact:true})).toBeVisible()
    await screenshot('user-role-'+name);await page.keyboard.press('Escape')
  }
  checks.push('user management: actual drawer, tree and multi-select match each theme')
  await page.goto(base+'/system/role')
  await page.getByRole('button',{name:'新增角色',exact:true}).click()
  const role=page.getByRole('dialog',{name:'新增角色',exact:true})
  await expect(role).toBeVisible()
  for(const name of ['办公蓝','青绿','石墨']){
    await choose(name);await openControl('数据权限',role)
    await expect(page.getByRole('option').filter({hasText:'全部'}).first()).toBeVisible()
    await screenshot('role-scope-'+name);await page.keyboard.press('Escape')
  }
  checks.push('role management: permissions drawer and scope dropdown match each theme; no role changes submitted')
  await page.goto(base+'/reports/purchase-progress')
  await expect(page.getByRole('button',{name:'切换外观',exact:true})).toBeVisible()
  await choose('青绿')
  const guide=await context.newPage()
  guide.on('pageerror',e=>errors.push(e.message))
  const authBefore=requests.filter(r=>r.path==='/auth/me').length
  await guide.goto(base+'/page-guide/purchase#section=fields&group=全部&search=转单率')
  await expect(guide.locator('.pms-guide-page')).toBeVisible()
  await expect(guide.locator('html')).toHaveAttribute('data-pms-theme','teal')
  assert.equal(requests.filter(r=>r.path==='/auth/me').length,authBefore,'public guide initialized an identity')
  await choose('石墨')
  await expect(guide.locator('html')).toHaveAttribute('data-pms-theme','graphite')
  await guide.screenshot({path:new URL('public-guide-theme.png',output).pathname,animations:'disabled'})
  await guide.close()
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-pms-theme','graphite')
  checks.push('public help inherits and follows appearance without auth lookup; authenticated preference survives reload')
  assert.deepEqual(errors,[]);assert.deepEqual(unknown,[])
  await writeFile(new URL('browser-result.json',output),JSON.stringify({passed:true,checks,errors,unknown,requests,realBackend:false},null,2))
  console.log(JSON.stringify({passed:true,checks},null,2))
}catch(error){console.error({errors,unknown,checks,requests:requests.slice(-8)});throw error}
finally{await browser?.close();await server.close()}
