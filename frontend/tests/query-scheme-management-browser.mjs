import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {readFile,stat,mkdir,writeFile} from 'node:fs/promises'
import path from 'node:path'
import {chromium,expect} from '@playwright/test'
import {fixtureResponse} from './fixtures/theme-application-api.mjs'

const root=path.resolve(import.meta.dirname,'../..'),dist=path.join(root,'frontend/dist')
const out=path.join(root,'.runtime/query-scheme-management-20261021/browser')
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
const schemeKey='pms:query-workspace:v2:997:report-purchase-progress',legacyKey='pms:purchase-report:v1:997'
const marker=schemeKey.replace('v2:','legacy-import:v1:')
const definition=value=>({field:'bill_no',shown:true,operator:'equals',value,valueEnd:null,schemaVersion:2})
const plan=(name,isDefault=false)=>({version:2,name,isDefault,definitions:[definition('REQ-'+name)],preferences:{owner:name,pageSize:100,purchaseMaterialLayoutVersion:1,visible:['material_code','material_name','bill_no'],columns:[{colId:'material_code',width:176},{colId:'material_name',width:224},{colId:'bill_no',width:181}]}})
const errors=[],unknown=[],checks=[],calls=[]
let browser
try{
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(5192,'127.0.0.1',resolve)})
  const base='http://127.0.0.1:5192'
  browser=await chromium.launch({channel:'msedge',headless:true})
  async function open(seed={},url='/reports/purchase-progress',failStorageKey=''){
    const context=await browser.newContext({viewport:{width:1440,height:900}})
    await context.addInitScript(({seed,failStorageKey})=>{
      localStorage.setItem('access_token','isolated-scheme-test')
      for(const [key,value] of Object.entries(seed))if(localStorage.getItem(key)===null)localStorage.setItem(key,typeof value==='string'?value:JSON.stringify(value))
      if(failStorageKey){window.__failSchemeStorage=true;const set=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){if(window.__failSchemeStorage&&key===failStorageKey)throw new DOMException('quota','QuotaExceededError');return set.call(this,key,value)}}
    },{seed,failStorageKey})
    await context.route('**/*',route=>{
      const request=route.request(),url=new URL(request.url())
      if(url.origin!==base){unknown.push('External request '+url.origin);return route.abort()}
      if(!url.pathname.startsWith('/api/'))return route.continue()
      const routePath=url.pathname.slice(4)
      calls.push({path:routePath,method:request.method(),query:Object.fromEntries(url.searchParams)})
      if(request.method()!=='GET'){unknown.push('Business write '+routePath);return route.abort()}
      try{return route.fulfill({json:fixtureResponse(routePath,url.searchParams,request.method())})}
      catch(error){unknown.push(String(error));return route.fulfill({status:501,json:{detail:String(error)}})}
    })
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
    await page.goto(base+url)
    if(url.startsWith('/reports/purchase')){
      await expect(page.locator('.purchase-overview-page').getByRole('button',{name:'查询',exact:true})).toBeEnabled()
      await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
    }
    const workspace=page.locator('.pms-query-workspace:visible')
    await expect(workspace.getByRole('button',{name:'方案设置',exact:true})).toBeEnabled()
    return{context,page,workspace}
  }
  const drawer=page=>page.getByRole('dialog',{name:'查询方案设置',exact:true})
  const stored=page=>page.evaluate(key=>JSON.parse(localStorage.getItem(key)||'[]'),schemeKey)
  const queryCount=()=>calls.filter(c=>c.path==='/reports/purchase').length
  async function settings(page,workspace){await workspace.getByRole('button',{name:'方案设置',exact:true}).click();await expect(drawer(page)).toBeVisible();return drawer(page)}
  async function choose(page,name){await drawer(page).locator('.el-select').filter({has:page.getByRole('combobox',{name:'维护查询方案',exact:true})}).click();await page.getByRole('option',{name,exact:true}).click()}
  async function confirm(page,title,button){const box=page.getByRole('dialog',{name:title,exact:true});await expect(box).toBeVisible();await box.getByRole('button',{name:button,exact:true}).click()}
  {
    const {context,page,workspace}=await open({[schemeKey]:[plan('A',true),plan('B')]})
    assert.equal(queryCount(),0,'report stays pending on entry')
    await workspace.getByRole('button',{name:'查询',exact:true}).click()
    await expect(page.locator('.purchase-page [role="gridcell"][col-id="bill_no"]').first()).toHaveText('REQ-TEST-1')
    const count=queryCount()
    let d=await settings(page,workspace);await choose(page,'B')
    await d.getByRole('textbox',{name:'方案名称',exact:true}).fill('B改名')
    await d.getByRole('button',{name:'保存方案',exact:true}).click();await expect(d).not.toBeVisible()
    assert.equal(queryCount(),count)
    assert.deepEqual((await stored(page)).find(s=>s.name==='B改名').preferences,plan('B').preferences)
    await expect(workspace.getByRole('textbox',{name:'查询1值',exact:true})).toHaveValue('REQ-A')
    d=await settings(page,workspace)
    await d.getByRole('button',{name:'删除方案',exact:true}).click()
    await confirm(page,'删除个人方案','取消');await expect(d).toBeVisible()
    assert.equal((await stored(page)).length,2)
    await d.getByRole('button',{name:'删除方案',exact:true}).click();await confirm(page,'删除个人方案','删除方案')
    await expect(d).not.toBeVisible();await expect(workspace).toContainText('条件已变更，待查询')
    assert.equal(queryCount(),count)
    await expect(page.locator('.purchase-page [role="gridcell"][col-id="bill_no"]').first()).toHaveText('REQ-TEST-1')
    d=await settings(page,workspace)
    await expect(d.getByRole('button',{name:'删除方案',exact:true})).toHaveCount(0)
    await expect(d.getByRole('button',{name:'保存方案',exact:true})).toBeDisabled()
    for(const [id,label] of [['blue','办公蓝'],['teal','青绿'],['graphite','石墨']]){
      await d.getByRole('button',{name:'取消',exact:true}).click();await expect(d).not.toBeVisible()
      await page.getByRole('button',{name:'切换外观',exact:true}).click();await page.getByRole('menuitem',{name:label,exact:true}).click()
      await expect(page.locator('html')).toHaveAttribute('data-pms-theme',id)
      d=await settings(page,workspace);await choose(page,'B改名')
      await page.screenshot({path:path.join(out,`settings-${id}.png`),animations:'disabled'})
    }
    for(const width of [1182,390]){
      await page.setViewportSize({width,height:820})
      const footer=d.locator('.pms-form-drawer__footer')
      await page.screenshot({path:path.join(out,`settings-${width}.png`),animations:'disabled'})
      const rects=await footer.locator('button:visible').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return{x:r.x,right:r.right,y:r.y,bottom:r.bottom}}))
      for(const r of rects)assert.ok(r.x>=0&&r.right<=width+1,JSON.stringify({width,rects}))
      for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){const a=rects[i],b=rects[j];assert.ok(a.right<=b.x+1||b.right<=a.x+1||a.bottom<=b.y+1||b.bottom<=a.y+1,'footer buttons cannot overlap')}
      await page.screenshot({path:path.join(out,`settings-${width}.png`),animations:'disabled'})
    }
    checks.push('real drawer rename preserves other scheme preferences/active results; cancel/delete fallback no query; system readonly; three themes and compact/mobile footer')
    await context.close()
  }
  {
    const {context,page,workspace}=await open({[schemeKey]:[plan('A',true)]})
    const d=await settings(page,workspace)
    await d.getByRole('textbox',{name:'方案名称',exact:true}).fill('未保存')
    await d.getByRole('button',{name:'取消',exact:true}).click();await confirm(page,'未保存修改','取消')
    await expect(d.getByRole('textbox',{name:'方案名称',exact:true})).toHaveValue('未保存')
    await page.evaluate(key=>{const all=JSON.parse(localStorage.getItem(key));all[0].definitions[0].value='OTHER-TAB';localStorage.setItem(key,JSON.stringify(all))},schemeKey)
    await d.getByRole('button',{name:'保存方案',exact:true}).click()
    await expect(d).toContainText('其他页面更新或删除')
    await expect(d.getByRole('textbox',{name:'方案名称',exact:true})).toHaveValue('未保存')
    assert.equal((await stored(page))[0].definitions[0].value,'OTHER-TAB')
    await d.getByRole('button',{name:'取消',exact:true}).click();await confirm(page,'未保存修改','放弃修改')
    await expect(d).not.toBeVisible();await settings(page,workspace)
    await d.getByRole('textbox',{name:'方案名称',exact:true}).fill('保存失败草稿')
    const original=await stored(page)
    await page.evaluate(key=>{const set=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k===key)throw new DOMException('quota','QuotaExceededError');return set.call(this,k,v)}},schemeKey)
    await d.getByRole('button',{name:'保存方案',exact:true}).click()
    await expect(d).toContainText('原记录和草稿保留');await expect(d).toBeVisible()
    assert.deepEqual(await stored(page),original)
    await page.screenshot({path:path.join(out,'write-failure.png'),animations:'disabled'})
    checks.push('unsaved cancel retained; same-target second-tab change rejected; quota failure keeps original record and editor draft')
    await context.close()
  }
  {
    const legacy={plans:[{name:'旧采购',filters:{project_code:'THEME-0001',organization_ids:[],progress:''},dates:[],conditions:[],pageSize:100}]}
    const {context,page,workspace}=await open({[legacyKey]:legacy})
    assert.ok((await stored(page)).some(p=>p.name==='旧采购'))
    let d=await settings(page,workspace);await choose(page,'旧采购')
    await d.getByRole('textbox',{name:'方案名称',exact:true}).fill('旧采购改名')
    await d.getByRole('button',{name:'保存方案',exact:true}).click();await expect(d).not.toBeVisible()
    await page.reload();await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
    assert.deepEqual((await stored(page)).map(s=>s.name),['旧采购改名'])
    d=await settings(page,workspace);await choose(page,'旧采购改名');await d.getByRole('button',{name:'删除方案',exact:true}).click();await confirm(page,'删除个人方案','删除方案');await expect(d).not.toBeVisible()
    await page.reload();await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
    assert.deepEqual(await stored(page),[])
    assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)).plans,legacyKey),legacy.plans)
    assert.equal(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)).version,marker),1)
    checks.push('actual legacy report import is once-only; rename/delete survive reload without source revival or source mutation')
    await context.close()
  }
  {
    const before=calls.filter(c=>c.path==='/projects/archives/list').length
    const {context,page,workspace}=await open({},'/project/archive')
    await expect(page.locator('[role="gridcell"][col-id="project_code"]').first()).toBeVisible()
    assert.equal(calls.filter(c=>c.path==='/projects/archives/list').length,before+1)
    const d=await settings(page,workspace)
    await d.getByRole('button',{name:'新建方案',exact:true}).click()
    await d.getByRole('textbox',{name:'方案名称',exact:true}).fill('档案测试方案')
    await d.getByRole('button',{name:'保存方案',exact:true}).click();await expect(d).not.toBeVisible()
    assert.equal(calls.filter(c=>c.path==='/projects/archives/list').length,before+1,'scheme save never implicitly queries documents')
    checks.push('archive autoqueries once on entry; shared create/save works without a second business query')
    await context.close()
  }
  {
    const legacy={plans:[{name:'导入失败测试',filters:{project_code:'THEME-0001'},dates:[],conditions:[]}]}
    const {context,page,workspace}=await open({[legacyKey]:legacy},'/reports/purchase-progress',marker)
    await expect(workspace).toContainText('旧方案导入尚未完成')
    const d=await settings(page,workspace);await choose(page,'导入失败测试')
    await expect(d.getByRole('button',{name:'删除方案',exact:true})).toBeDisabled()
    await expect(d.getByRole('button',{name:'保存方案',exact:true})).toBeDisabled()
    await d.getByRole('button',{name:'取消',exact:true}).click();await expect(d).not.toBeVisible()
    await page.evaluate(()=>{window.__failSchemeStorage=false})
    await settings(page,workspace);await choose(page,'导入失败测试')
    await expect(d.getByRole('button',{name:'保存方案',exact:true})).toBeEnabled()
    await expect(d.getByRole('button',{name:'删除方案',exact:true})).toBeEnabled()
    assert.deepEqual(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)).plans,legacyKey),legacy.plans)
    checks.push('incomplete legacy marker write disables maintenance; reopen after recovery retries safely with original source intact')
    await context.close()
  }
  for(const [url,listKey,endpoint] of [['/reports/inventory','report-inventory','/reports/inventory'],['/reports/stock-detail','report-stock-detail','/reports/stock-detail']]){
    const ownKey=`pms:query-workspace:v2:997:${listKey}`
    const before=calls.filter(c=>c.path===endpoint).length
    const {context,page,workspace}=await open({[ownKey]:[]},url)
    const d=await settings(page,workspace)
    await expect(d.getByRole('button',{name:'删除方案',exact:true})).toHaveCount(0)
    await d.getByRole('button',{name:'新建方案',exact:true}).click()
    await d.getByRole('textbox',{name:'方案名称',exact:true}).fill('报表设置验证')
    await expect(d.getByRole('button',{name:'保存方案',exact:true})).toBeEnabled()
    assert.equal(calls.filter(c=>c.path===endpoint).length,before,'opening report/settings must not query business data')
    checks.push(`${listKey}: shared readonly system/new-scheme drawer, no entry or settings business query`)
    await context.close()
  }
  assert.deepEqual(errors,[]);assert.deepEqual(unknown,[])
  await writeFile(path.join(out,'result.json'),JSON.stringify({passed:true,checks,errors,unknown,calls,productionBuild:true,endpoint:'127.0.0.1:5192',realBackend:false,businessWrites:false},null,2)+'\n')
  console.log(JSON.stringify({passed:true,checks},null,2))
}catch(error){console.error({errors,unknown,calls:calls.slice(-5)});throw error}
finally{await browser?.close();await new Promise(resolve=>server.close(resolve))}
