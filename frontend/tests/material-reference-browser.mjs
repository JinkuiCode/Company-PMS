import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {readFile,stat,mkdir,writeFile} from 'node:fs/promises'
import {createWriteStream} from 'node:fs'
import {spawn,execFileSync} from 'node:child_process'
import path from 'node:path'
import {chromium,expect} from '@playwright/test'
import {fixtureResponse} from './fixtures/theme-application-api.mjs'

const root=path.resolve(import.meta.dirname,'../..'),dist=path.join(root,'frontend/dist'),out=path.join(root,'.runtime/material-reference-implementation-20261021/browser')
await mkdir(out,{recursive:true})
const backend='http://127.0.0.1:8192',base='http://127.0.0.1:5192',errors=[],unknown=[],checks=[],requests=[]
const log=createWriteStream(path.join(out,'backend.log'))
let browser,child
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.svg':'image/svg+xml'}
const server=createServer(async(req,res)=>{
  try{
    let file=path.resolve(dist,'.'+decodeURIComponent(new URL(req.url,base).pathname))
    if(!file.startsWith(dist+path.sep)){res.writeHead(403);res.end();return}
    try{if(!(await stat(file)).isFile())file=path.join(dist,'index.html')}catch{file=path.join(dist,'index.html')}
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});res.end(await readFile(file))
  }catch{res.writeHead(500);res.end()}
})
const definition=(field,operator,value=null,valueEnd=null)=>({field,operator,value,valueEnd,shown:true,schemaVersion:2})
try{
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(5192,'127.0.0.1',resolve)})
  child=spawn('/Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',['-m','uvicorn','material_reference_app:app','--host','127.0.0.1','--port','8192'],{cwd:path.join(root,'backend'),env:{...process.env,PMS_CONFIG_FILE:'/dev/null',SQLITE_DB_PATH:path.join(out,'unused-engine.sqlite'),PMS_C2_TEST_OUTPUT:out,PYTHONPATH:['/Users/jin/Code/PMS/backend/.venv-deps312',path.join(root,'backend/tests/fixtures'),path.join(root,'backend/tests'),path.join(root,'backend')].join(':')},stdio:['ignore','pipe','pipe']})
  child.stdout.pipe(log);child.stderr.pipe(log)
  for(let attempt=0;;attempt++){
    if(child.exitCode!==null)throw Error('Synthetic backend exited '+child.exitCode)
    try{if((await fetch(backend+'/api/test/state')).ok)break}catch{}
    if(attempt>=100)throw Error('Synthetic backend not ready')
    await new Promise(resolve=>setTimeout(resolve,100))
  }
  browser=await chromium.launch({channel:'msedge',headless:true})
  async function open(kind,initialCodes){
    const config={overview:['/reports/purchase-progress','report-purchase-overview','material_code'],purchase:['/reports/purchase-progress','report-purchase-progress','material_code'],inventory:['/reports/inventory','report-inventory','MaterialCode'],stock:['/reports/stock-detail','report-stock-detail','material_code']}[kind]
    const [url,key,field]=config
    const context=await browser.newContext({viewport:{width:1440,height:900},acceptDownloads:true})
    const definitions=[definition(field,'contains'),definition(kind==='inventory'?'organization_id':'organization_ids','reference',[11])]
    if(initialCodes)definitions[0]=definition(field,'reference',initialCodes)
    if(kind==='stock')definitions.push(definition('bill_date','between','2026-10-01','2026-10-20'))
    await context.addInitScript(({key,definitions})=>{
      localStorage.setItem('access_token','synthetic-c2-only')
      const storage=`pms:query-workspace:v2:997:${key}`
      if(!localStorage.getItem(storage))localStorage.setItem(storage,JSON.stringify([{version:2,name:'引用验收',isDefault:true,definitions,preferences:{}}]))
    },{key,definitions})
    await context.route('**/*',async route=>{
      const request=route.request(),url=new URL(request.url())
      if(url.origin!==base){unknown.push(url.origin);return route.abort()}
      if(!url.pathname.startsWith('/api/'))return route.continue()
      const endpoint=url.pathname.slice(4)
      const record={path:endpoint,method:request.method(),query:Object.fromEntries(url.searchParams),body:request.postDataJSON?.()};requests.push(record)
      if(endpoint.startsWith('/reports/')||endpoint.startsWith('/report-exports')){
        if(request.method()!=='GET'&&!(request.method()==='POST'&&endpoint==='/report-exports')){unknown.push('unexpected write '+endpoint);return route.abort()}
        const response=await route.fetch({url:backend+url.pathname+url.search})
        record.status=response.status()
        if(response.status()>=500)unknown.push('Synthetic server failure '+endpoint+' '+response.status())
        return route.fulfill({response})
      }
      if(request.method()!=='GET'){unknown.push('unconfigured write '+endpoint);return route.abort()}
      try{return route.fulfill({json:fixtureResponse(endpoint,url.searchParams,request.method())})}
      catch(error){unknown.push(String(error));return route.fulfill({status:501,json:{detail:String(error)}})}
    })
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
    await page.goto(base+url)
    if(kind==='purchase')await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
    const workspace=page.locator('.pms-query-workspace:visible')
    await expect(workspace.locator(`[data-field="${field}"]`)).toBeVisible()
    return{page,context,workspace,field,key}
  }
  async function reference(page,workspace,field){
    const row=workspace.locator(`[data-field="${field}"]`)
    if(await row.locator('.pms-condition-reference').count())await row.locator('.pms-condition-reference').click()
    else{await row.locator('.el-select').nth(1).click();await page.getByRole('option',{name:'引用',exact:true}).click()}
    const dialog=page.getByRole('dialog',{name:'引用物料',exact:true});await expect(dialog).toBeVisible()
    return dialog
  }
  async function choose(dialog,code){
    await dialog.getByRole('textbox',{name:'搜索引用记录',exact:true}).fill(code)
    await dialog.getByRole('button',{name:'查询',exact:true}).click()
    const checkbox=dialog.getByRole('checkbox',{name:new RegExp('^选择'+code+' ')})
    await expect(checkbox).toBeEnabled();await checkbox.locator('..').locator('.el-checkbox__inner').click()
  }
  for(const kind of ['overview','purchase','inventory','stock']){
    const {page,context,workspace,field,key}=await open(kind)
    const before=(await (await fetch(backend+'/api/test/state')).json()).calls.length
    let dialog=await reference(page,workspace,field)
    if(kind==='inventory'){
      await dialog.getByRole('button',{name:'2',exact:true}).click()
      const first=dialog.getByRole('table',{name:'引用记录列表'}).locator('tbody tr').first()
      await expect(first).toBeVisible()
      await first.locator('.el-checkbox__inner').click()
      await dialog.getByRole('button',{name:'1',exact:true}).click()
      await expect(dialog.getByRole('table',{name:'已选记录列表'}).locator('tbody tr')).toHaveCount(1)
      await dialog.getByRole('button',{name:'清空选择',exact:true}).click()
      checks.push('real reference pagination retains a selection from another page')
    }
    await choose(dialog,'0007-A');await choose(dialog,'0008-B')
    await expect(dialog.getByRole('table',{name:'已选记录列表'}).locator('tbody tr')).toHaveCount(2)
    await dialog.getByRole('button',{name:'取消',exact:true}).click()
    await expect(workspace.locator(`[data-field="${field}"] .pms-condition-reference`)).toHaveCount(0)
    dialog=await reference(page,workspace,field);await choose(dialog,'0007-A');await choose(dialog,'0008-B')
    for(const [id,label] of kind==='inventory'?[['blue','办公蓝'],['teal','青绿'],['graphite','石墨']]:[]){
      await dialog.getByRole('button',{name:'确认引用',exact:true}).click()
      await page.getByRole('button',{name:'切换外观',exact:true}).click();await page.getByRole('menuitem',{name:label,exact:true}).click()
      await expect(page.locator('html')).toHaveAttribute('data-pms-theme',id)
      dialog=await reference(page,workspace,field);await page.screenshot({path:path.join(out,`reference-${id}.png`),animations:'disabled'})
    }
    await dialog.getByRole('button',{name:'确认引用',exact:true}).click()
    assert.equal((await (await fetch(backend+'/api/test/state')).json()).calls.length,before,'reference changes do not implicitly load reports')
    await workspace.getByRole('button',{name:'查询',exact:true}).click()
    await expect.poll(async()=>(await (await fetch(backend+'/api/test/state')).json()).calls.length).toBeGreaterThan(before)
    const received=(await (await fetch(backend+'/api/test/state')).json()).calls.at(-1)
    if(kind==='stock')assert.deepEqual(received.parameters.material_codes,['0007-a','0008-b'])
    else assert.deepEqual(JSON.parse(received.parameters.filters).find(c=>c.operator==='reference').value,['0007-a','0008-b'])
    if(kind==='overview'){
      await expect(page.locator('.purchase-overview-page [role="gridcell"][col-id="total_lines"]').first()).toHaveText('2')
      const rowId=await page.locator('.purchase-overview-page [role="gridcell"][col-id="project_code"]').first().locator('..').getAttribute('row-id')
      await page.locator(`.purchase-overview-page .ag-pinned-right-cols-container [row-id="${rowId}"]`).getByRole('button',{name:'明细',exact:true}).click()
      await expect(page.locator('.purchase-page [col-id="material_code"][role="gridcell"]').first()).toBeVisible()
      const drill=(await (await fetch(backend+'/api/test/state')).json()).calls.at(-1)
      assert.equal(drill.kind,'purchase');assert.deepEqual(JSON.parse(drill.parameters.filters).find(c=>c.field==='material_code').value,['0007-a','0008-b'])
      checks.push('overview row drill preserves the full material collection')
      await page.getByRole('button',{name:'总进度',exact:true}).filter({visible:true}).click()
    }
    if(kind==='inventory'){
      const count=(await (await fetch(backend+'/api/test/state')).json()).calls.length
      await workspace.getByRole('button',{name:'方案设置',exact:true}).click()
      const drawer=page.getByRole('dialog',{name:'查询方案设置',exact:true})
      await drawer.getByRole('textbox',{name:'方案名称',exact:true}).fill('多物料保存')
      await drawer.getByRole('button',{name:'保存方案',exact:true}).click();await expect(drawer).not.toBeVisible()
      const saved=await page.evaluate(key=>JSON.parse(localStorage.getItem(`pms:query-workspace:v2:997:${key}`)),key)
      assert.deepEqual(saved.find(p=>p.name==='多物料保存').definitions.find(d=>d.field==='MaterialCode').value,['0007-a','0008-b'])
      await page.reload()
      await expect(workspace.locator(`[data-field="${field}"] .pms-condition-reference`)).toContainText('2')
      assert.equal((await (await fetch(backend+'/api/test/state')).json()).calls.length,count)
      await workspace.getByRole('button',{name:'查询',exact:true}).click()
      await expect(page.locator('[role="gridcell"][col-id="MaterialCode"]').first()).toHaveText('0007-A')
      async function line(name){
        await workspace.locator('[data-field="organization_id"] .pms-condition-reference').click()
        const dialog=page.getByRole('dialog',{name:'引用产品线',exact:true})
        await dialog.getByRole('button',{name:'清空选择',exact:true}).click()
        await dialog.getByRole('checkbox',{name:'选择'+name,exact:true}).locator('..').locator('.el-checkbox__inner').click()
        await dialog.getByRole('button',{name:'确认引用',exact:true}).click()
      }
      await line('合成产品线乙')
      const beforeRejected=(await (await fetch(backend+'/api/test/state')).json()).calls.length
      await workspace.getByRole('button',{name:'查询',exact:true}).click()
      await expect(workspace).toContainText('引用校验失败')
      assert.equal((await (await fetch(backend+'/api/test/state')).json()).calls.length,beforeRejected)
      await expect(workspace.locator(`[data-field="${field}"] .pms-condition-reference`)).toContainText('2')
      await expect(page.locator('[role="gridcell"][col-id="MaterialCode"]').first()).toHaveText('0007-A')
      await line('合成产品线甲');await workspace.getByRole('button',{name:'查询',exact:true}).click()
      await expect(workspace.locator('.pms-query-error')).toHaveCount(0)
      checks.push('C1 save/reload retains full keys without autoquery; product-line change retains keys and rejects inaccessible references without widening or erasing old rows')
    }
    const creating=page.waitForResponse(r=>r.url()===base+'/api/report-exports'&&r.request().method()==='POST')
    await page.locator('.report-export-control:visible').getByRole('button',{name:'导出数据',exact:true}).click()
    const created=await (await creating).json()
    await expect(page.locator('.report-export-jobs:visible')).toContainText('排队中')
    await fetch(backend+'/api/test/run-exports',{method:'POST'})
    await page.getByRole('button',{name:'刷新导出任务',exact:true}).filter({visible:true}).click()
    const report=kind==='stock'?'stock-detail':kind==='overview'?'purchase':kind
    const jobs=await (await fetch(backend+'/api/report-exports?report='+report)).json()
    const position=jobs.findIndex(job=>job.id===created.id)
    assert.ok(position>=0,'new synthetic export remains in its owner history')
    const job=page.locator('.report-export-jobs:visible .report-export-job').nth(position)
    await expect(job).toContainText('已完成')
    const downloading=page.waitForEvent('download')
    await job.getByRole('button',{name:'下载',exact:true}).click()
    const download=await downloading,file=path.join(out,`${kind}.xlsx`);await download.saveAs(file)
    assert.ok(download.suggestedFilename().includes(created.id.slice(0,8)))
    const xml=execFileSync('unzip',['-p',file,'xl/worksheets/sheet1.xml'],{encoding:'utf8'})
    if(kind!=='overview'){assert.match(xml,/0007-A/);assert.match(xml,/0008-B/)}
    await page.screenshot({path:path.join(out,`${kind}-queried.png`),animations:'disabled'})
    checks.push(`${kind}: cancel unchanged, cross-search multi-select, full collection received by real FastAPI wrapper, synthetic export/download`)
    await context.close()
  }
  {
    const codes=Array.from({length:180},(_,i)=>`long-${String(i).padStart(4,'0')}-${'x'.repeat(12)}`)
    const {context,page,workspace,field}=await open('stock',codes)
    await expect(workspace.locator(`[data-field="${field}"] .pms-condition-reference`)).toContainText('180')
    const before=(await (await fetch(backend+'/api/test/state')).json()).calls.length
    await workspace.getByRole('button',{name:'查询',exact:true}).click()
    await expect(page.locator('.el-message__content').filter({hasText:'6000字节'})).toBeVisible()
    assert.equal((await (await fetch(backend+'/api/test/state')).json()).calls.length,before)
    await expect(workspace.locator(`[data-field="${field}"] .pms-condition-reference`)).toContainText('180')
    await page.screenshot({path:path.join(out,'long-url-error.png'),animations:'disabled'})
    checks.push('identity validation fits but full stock URL exceeds limit: explicit reason shown, no report request,180 selected keys retained')
    await context.close()
  }
  assert.deepEqual(errors,[]);assert.deepEqual(unknown,[])
  const state=await (await fetch(backend+'/api/test/state')).json();assert.deepEqual(state.errors,[])
  await writeFile(path.join(out,'result.json'),JSON.stringify({passed:true,checks,errors,unknown,requests,received:state.calls,backendErrors:state.errors,productionBuild:true,front:base,backend,syntheticOnly:true,existingDatabase:false},null,2)+'\n')
  console.log(JSON.stringify({passed:true,checks},null,2))
}catch(error){console.error({errors,unknown,requests:requests.slice(-6)});throw error}
finally{
  await browser?.close()
  if(child&&child.exitCode===null){const stopped=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await stopped}
  await new Promise(resolve=>server.close(resolve));log.end()
}
