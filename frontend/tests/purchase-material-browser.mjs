import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {readFile,stat,mkdir,writeFile} from 'node:fs/promises'
import path from 'node:path'
import {chromium,expect} from '@playwright/test'
import {fixtureResponse} from './fixtures/theme-application-api.mjs'

const root=path.resolve(import.meta.dirname,'../..'),dist=path.join(root,'frontend/dist')
const out=path.join(root,'.runtime/purchase-material-code-20261021/browser')
await mkdir(out,{recursive:true})
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.svg':'image/svg+xml'}
const server=createServer(async(req,res)=>{
  try{
    let file=path.resolve(dist,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname))
    if(!file.startsWith(dist+path.sep)){res.writeHead(403);res.end();return}
    try{if(!(await stat(file)).isFile())file=path.join(dist,'index.html')}catch{file=path.join(dist,'index.html')}
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});res.end(await readFile(file))
  }catch{res.writeHead(500);res.end()}
})
const key='pms:purchase-report:v1:997',schemeKey='pms:query-workspace:v2:997:report-purchase-progress'
const errors=[],unknown=[],checks=[],calls=[]
let browser
try{
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(5192,'127.0.0.1',resolve)})
  const base='http://127.0.0.1:5192'
  browser=await chromium.launch({channel:'msedge',headless:true})
  async function open(seed={}){
    const context=await browser.newContext({viewport:{width:1440,height:900}})
    await context.addInitScript(seed=>{
      localStorage.setItem('access_token','isolated-purchase-material-test')
      for(const [key,value] of Object.entries(seed))if(localStorage.getItem(key)===null)localStorage.setItem(key,JSON.stringify(value))
    },seed)
    await context.route('**/*',route=>{
      const request=route.request(),url=new URL(request.url())
      if(url.origin!==base){unknown.push('External request: '+url.origin);return route.abort()}
      if(!url.pathname.startsWith('/api/'))return route.continue()
      const routePath=url.pathname.slice(4)
      calls.push({path:routePath,method:request.method(),query:Object.fromEntries(url.searchParams)})
      if(request.method()!=='GET'){unknown.push('Unexpected business write '+routePath);return route.abort()}
      try{return route.fulfill({json:fixtureResponse(routePath,url.searchParams,request.method())})}
      catch(error){unknown.push(String(error));return route.fulfill({status:501,json:{detail:String(error)}})}
    })
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
    await page.goto(base+'/reports/purchase-progress')
    await expect(page.locator('.purchase-overview-page').getByRole('button',{name:'查询',exact:true})).toBeEnabled()
    await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
    const detail=page.locator('.purchase-page')
    await expect(detail).toBeVisible()
    await expect(detail.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
    return {context,page,detail}
  }
  const header=(scope,key)=>scope.locator(`[role="columnheader"][col-id="${key}"]`)
  async function adjacent(detail){
    await expect(header(detail,'material_code')).toBeVisible()
    await expect(header(detail,'material_name')).toBeVisible()
    await expect.poll(async()=>{
      const a=await header(detail,'material_code').boundingBox(),b=await header(detail,'material_name').boundingBox()
      return a&&b?Math.abs(a.x+a.width-b.x):Infinity
    },{message:'code and name settle adjacent after AG Grid column-move animation'}).toBeLessThan(2)
  }
  async function selectScheme(page,detail,name){
    await detail.locator('.pms-query-scheme-select .pms-form-control').click()
    await page.getByRole('option',{name,exact:true}).click()
  }
  {
    const {context,page,detail}=await open()
    assert.equal(calls.filter(c=>c.path==='/reports/purchase').length,0)
    await adjacent(detail)
    assert.equal(await detail.locator('.ag-pinned-left-header .ag-header-cell').first().getAttribute('col-id'),'product_line_name')
    for(const [id,name] of [['blue','办公蓝'],['teal','青绿'],['graphite','石墨']]){
      await page.getByRole('button',{name:'切换外观',exact:true}).click();await page.getByRole('menuitem',{name,exact:true}).click()
      await expect(page.locator('html')).toHaveAttribute('data-pms-theme',id)
      await adjacent(detail)
      await page.screenshot({path:path.join(out,`new-${id}.png`),animations:'disabled'})
    }
    checks.push('new detail: pending query, prefix retained, adjacent code/name in all three themes')
    await detail.getByRole('button',{name:'打开采购进度列设置',exact:true}).click()
    const picker=page.locator('.column-picker-panel:visible')
    await picker.getByRole('button',{name:'下移物料编码',exact:true}).click()
    await picker.getByRole('button',{name:'保存',exact:true}).click()
    let state=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key)
    assert.equal(state.purchaseMaterialLayoutVersion,1)
    assert.ok(state.columns.findIndex(c=>c.colId==='material_code')>state.columns.findIndex(c=>c.colId==='material_name'))
    await detail.getByRole('button',{name:'打开采购进度列设置',exact:true}).click()
    await picker.locator('[data-column="material_code"] .el-checkbox__inner').click()
    await picker.getByRole('button',{name:'保存',exact:true}).click()
    await expect(header(detail,'material_code')).toHaveCount(0)
    await page.reload()
    await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
    await expect(header(detail,'material_code')).toHaveCount(0)
    state=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key)
    assert.ok(!state.visible.includes('material_code'))
    checks.push('user moves and hides code via actual column settings; choice survives reload')
    await context.close()
  }
  {
    const initial={reportIdentityVersion:1,visible:['product_line_name','project_code','material_name','bill_no'],columns:[
      {colId:'product_line_name',pinned:'left',width:144},{colId:'project_code',pinned:'left',width:175},
      {colId:'bill_no',width:211,sort:'desc'},{colId:'material_name',pinned:'right',width:241},
      {colId:'material_code',hide:true,pinned:'left',width:167},
    ],custom:'keep',pageSize:200}
    const {context,page,detail}=await open({[key]:initial})
    await adjacent(detail)
    await expect(detail.locator('.ag-pinned-right-header [col-id="material_code"]')).toBeVisible()
    const state=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key)
    for(const column of initial.columns.filter(c=>c.colId!=='material_code')){
      const actual=state.columns.find(c=>c.colId===column.colId)
      for(const [name,value] of Object.entries(column))assert.equal(actual[name],value)
    }
    assert.equal(state.custom,'keep');assert.equal(state.pageSize,200)
    await detail.getByRole('button',{name:'查询',exact:true}).click()
    await expect(detail.locator('[role="gridcell"][col-id="material_code"]').first()).toHaveText('MAT-1')
    await page.screenshot({path:path.join(out,'old-frozen.png'),animations:'disabled'})
    checks.push('old frozen layout: code follows name pin zone, exact widths and unrelated preferences retained')
    await context.close()
  }
  {
    const plans=[{version:2,name:'旧编码方案',isDefault:false,definitions:[{field:'bill_no',shown:true,operator:'equals',value:'REQ-1',valueEnd:null,schemaVersion:2}],preferences:{reportIdentityVersion:1,visible:['material_name','bill_no'],columns:[{colId:'material_name',width:224},{colId:'bill_no',width:177}],pageSize:100}}]
    const {context,page,detail}=await open({[schemeKey]:plans})
    await selectScheme(page,detail,'旧编码方案')
    await detail.getByRole('button',{name:'查询',exact:true}).click()
    await adjacent(detail)
    assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),schemeKey),plans,'merely applying old plan must not persist it')
    assert.equal(calls.filter(c=>c.path==='/reports/purchase').at(-1).query.page_size,'100')
    assert.match(calls.filter(c=>c.path==='/reports/purchase').at(-1).query.filters,/REQ-1/)
    await detail.getByRole('button',{name:'方案设置',exact:true}).click()
    const drawer=page.getByRole('dialog',{name:'查询方案设置',exact:true})
    await drawer.getByRole('button',{name:'保存方案',exact:true}).click()
    await expect(drawer).not.toBeVisible()
    const saved=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),schemeKey)
    assert.equal(saved[0].preferences.purchaseMaterialLayoutVersion,1)
    assert.equal(saved[0].preferences.columns.find(c=>c.colId==='material_name').width,224)
    await selectScheme(page,detail,'旧编码方案')
    await detail.getByRole('button',{name:'查询',exact:true}).click();await adjacent(detail)
    checks.push('old scheme applies without write, preserves conditions/page size, explicit save and reselection retain migrated layout')
    await context.close()
  }
  {
    const preferences={reportIdentityVersion:1,purchaseMaterialLayoutVersion:1,visible:['product_line_name','project_code','bill_no','unit_name','material_name'],columns:[
      {colId:'product_line_name',pinned:'left',width:140},{colId:'project_code',pinned:'left',width:145},
      {colId:'bill_no',width:178},{colId:'unit_name',width:91},{colId:'material_name',pinned:'right',width:224},{colId:'material_code',hide:true,pinned:null,width:167},
    ]}
    const plans=['仅显示字段','缺省冻结'].map((name,i)=>({version:2,name,isDefault:false,definitions:[],preferences:{reportIdentityVersion:1,
      visible:['product_line_name','project_code','bill_no','unit_name','material_name'],...(i?{columns:[{colId:'material_name',width:224}]}:{})}}))
    const {context,page,detail}=await open({[key]:preferences,[schemeKey]:plans})
    for(const name of ['仅显示字段','缺省冻结']){
      await selectScheme(page,detail,name)
      await detail.getByRole('button',{name:'查询',exact:true}).click()
      await adjacent(detail)
      await expect(detail.locator('.ag-pinned-right-header [col-id="material_code"]')).toBeVisible()
      await expect(detail.locator('.ag-pinned-right-header [col-id="material_name"]')).toBeVisible()
      const saved=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),key)
      assert.ok(saved.columns.findIndex(c=>c.colId==='bill_no')<saved.columns.findIndex(c=>c.colId==='unit_name'))
    }
    assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)),schemeKey),plans)
    checks.push('incomplete old plans inherit current column order and omitted pin, without altering scheme storage')
    await context.close()
  }
  {
    const {context,page,detail}=await open({[key]:{reportIdentityVersion:1,visible:['product_line_name','bill_no'],columns:[{colId:'material_name',hide:true,pinned:'right',width:224}]}})
    await expect(header(detail,'material_code')).toBeVisible();await expect(header(detail,'material_name')).toHaveCount(0)
    await detail.getByRole('button',{name:'总进度',exact:true}).click()
    const overview=page.locator('.purchase-overview-page')
    await overview.getByRole('button',{name:'查询',exact:true}).click()
    await expect(overview.locator('[role="gridcell"][col-id="project_code"]').first()).toBeVisible()
    assert.equal(await header(overview,'material_code').count(),0)
    const target=await overview.locator('[role="gridcell"][col-id="project_code"]').first().innerText()
    const rowId=await overview.locator('[role="gridcell"][col-id="project_code"]').first().locator('..').getAttribute('row-id')
    await overview.locator(`.ag-pinned-right-cols-container [row-id="${rowId}"]`).getByRole('button',{name:'明细',exact:true}).click()
    await expect(detail).toBeVisible();await expect(header(detail,'material_code')).toBeVisible()
    assert.equal(calls.filter(c=>c.path==='/reports/purchase').at(-1).query.project_code,target)
    await page.setViewportSize({width:1182,height:820})
    await page.screenshot({path:path.join(out,'hidden-name-drill-1182.png'),animations:'disabled'})
    checks.push('hidden material name stays hidden; overview adds no material column; row drill keeps project scope and code')
    await context.close()
  }
  assert.deepEqual(errors,[]);assert.deepEqual(unknown,[])
  await writeFile(path.join(out,'result.json'),JSON.stringify({passed:true,checks,errors,unknown,calls,productionBuild:true,
    endpoint:'127.0.0.1:5192',realBackend:false,businessWrites:false},null,2)+'\n')
  console.log(JSON.stringify({passed:true,checks},null,2))
}catch(error){console.error({errors,unknown,calls:calls.slice(-6)});throw error}
finally{await browser?.close();await new Promise(resolve=>server.close(resolve))}
