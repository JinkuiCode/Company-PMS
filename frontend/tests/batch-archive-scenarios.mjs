/** Combined archive/P28/C1 through real production UI, live RBAC and private SQLite. */
import assert from 'node:assert/strict'
import {expect} from '@playwright/test'
import {writeFile} from 'node:fs/promises'
import path from 'node:path'
import {fixtureResponse} from './fixtures/theme-application-api.mjs'

export async function runBatchArchive({browser,base,backend,tokens,out,errors,unknown,checks,requests}){
  const draftBase='/api/form-drafts/archive-create'
  async function api(endpoint,{method='GET',body,user=997,status=200}={}){
    const r=await fetch(backend+endpoint,{method,headers:{Authorization:'Bearer '+tokens[user],'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})})
    const json=await r.json();assert.equal(r.status,status,endpoint+' '+JSON.stringify(json));return json
  }
  const state=()=>api('/api/test/batch-state')
  const list=async(user=997)=>(await api('/api/projects/archives/list?enabled=all&page_size=500',{user})).items
  const archive=async(code,user=997)=>(await list(user)).find(r=>r.project_code===code)
  const draft=(code,more={})=>({id:crypto.randomUUID(),payload:{project_code:code,project_name:'合成 '+code,archive_category:2,product_line_id:3,manager_id:997,...more}})
  const bad=await api(draftBase,{method:'POST',body:draft('BATCH-BAD',{archive_category:null}),status:422});assert.ok(JSON.stringify(bad).includes('archive_category'))
  for(const value of [-1,0,1.5])await api(draftBase,{method:'POST',body:draft('BATCH-QTY-'+String(value),{quantity:value}),status:422})
  const before=(await state()).archives.length
  const saved=await api(draftBase,{method:'POST',body:draft('BATCH-API',{serial_no:'BATCH-API-SN'})})
  assert.equal((await state()).archives.length,before)
  await api(`${draftBase}/${saved.id}`,{user:998,status:404})
  await api(draftBase,{method:'POST',body:draft('BATCH-COLLISION',{serial_no:' batch-api-sn ' }),user:998,status:409})
  const formal=await api(`${draftBase}/${saved.id}/submit`,{method:'POST',body:{expected_version:saved.version}})
  await api(`${draftBase}/${saved.id}/submit`,{method:'POST',body:{expected_version:saved.version}})
  assert.equal((await list()).filter(r=>r.project_code==='BATCH-API').length,1)
  const created=await archive('BATCH-API');assert.ok(created);assert.equal(created.contract_signed_date,null);assert.equal(created.contract_ship_date,null)
  await api(draftBase,{method:'POST',body:draft('BATCH-AFTER-FORMAL',{serial_no:'BATCH-API-SN'}),status:409})
  await api('/api/projects/archives',{method:'POST',body:{project_code:'BATCH-MAIN-INVALID',project_name:'主机必输合成',archive_category:1,product_line_id:3,manager_id:997},status:422})
  checks.push('real SQLite: draft category/positive integer validation; private ownership; serial claim survives formal conversion and idempotent replay; non-main blank dates accepted; main incomplete rejected')
  // Same identity namespace through real JWT/API and approval lifecycle.
  const submit=async(serial)=>{
    const row=await archive('BATCH-API')
    return api(`/api/projects/archive-changes/${row.id}/submit`,{method:'POST',body:{expected_version:row.change_version,submission_id:crypto.randomUUID(),updates:{serial_no:serial},reason:'合成序列号流转验证'}})
  }
  for(const action of ['withdraw','reject','approve']){
    const serial='BATCH-PENDING-'+action,pending=await submit(serial)
    await api(draftBase,{method:'POST',body:draft('BATCH-PEND-CONFLICT-'+action,{serial_no:serial}),user:998,status:409})
    await api(draftBase,{method:'POST',body:draft('BATCH-OLD-CONFLICT-'+action,{serial_no:(await archive('BATCH-API')).serial_no}),user:998,status:409})
    if(action==='withdraw')await api(`/api/projects/archive-changes/requests/${pending.id}/withdraw`,{method:'POST',body:{expected_version:pending.version}})
    else await api(`/api/projects/archive-changes/requests/${pending.id}/decide`,{method:'POST',user:998,body:{decision:action,expected_version:pending.version,opinion:'合成生命周期'}})
    if(action==='approve'){
      assert.equal((await archive('BATCH-API')).serial_no,serial)
      await api(draftBase,{method:'POST',body:draft('BATCH-OLD-RELEASED',{serial_no:'BATCH-API-SN'})})
      await api(draftBase,{method:'POST',body:draft('BATCH-APPROVED-CONFLICT',{serial_no:serial}),status:409})
    }else{
      const free=await api(draftBase,{method:'POST',body:draft('BATCH-FREE-'+action,{serial_no:serial})})
      await api(`${draftBase}/${free.id}`,{method:'DELETE',body:{expected_version:free.version}})
    }
  }
  checks.push('real combined JWT/SQLite: pending retains old+new serial; withdraw/reject release target; approve atomically replaces claim, no ERP worker')
  const limited=await list(999);assert.equal(limited.length,0)
  await api('/api/test/batch-permission',{method:'POST',body:{user_id:997,permission:'project:archive:add',enabled:false}})
  await api(draftBase,{method:'POST',body:draft('BATCH-REVOKED'),status:403})
  await api('/api/test/batch-permission',{method:'POST',body:{user_id:997,permission:'project:archive:add',enabled:true}})
  checks.push('real live-role revoke applies to existing JWT next request; product-line restriction hides foreign archives')

  const contexts=[]
  async function open({user=997,seed={},theme='blue'}={}){
    const context=await browser.newContext({viewport:{width:1440,height:1000}});contexts.push(context)
    await context.addInitScript(({seed,token,base,theme,user})=>{
      localStorage.setItem('access_token',token)
      if(!sessionStorage.getItem('batch-seeded')){
        for(const [key,value]of Object.entries(seed))localStorage.setItem(key,JSON.stringify(value))
        localStorage.setItem(`pms:theme:v1:${encodeURIComponent(base)}:${user}`,theme)
        sessionStorage.setItem('batch-seeded','1')
      }
    },{seed,token:tokens[user],base,theme,user})
    await context.route('**/*',async route=>{
      const request=route.request(),url=new URL(request.url())
      if(url.origin!==base){unknown.push('archive external '+url.origin);return route.abort()}
      if(!url.pathname.startsWith('/api/'))return route.continue()
      const endpoint=url.pathname.slice(4),record={path:endpoint,method:request.method(),query:Object.fromEntries(url.searchParams)}
      requests.push(record)
      if(/^\/(projects|form-drafts|product-lines|dicts|users\/options|operation-logs|document-history|offline-archives)(\/|$)/.test(endpoint)||endpoint==='/auth/me'){
        const response=await route.fetch({url:backend+url.pathname+url.search});record.status=response.status()
        if(response.status()>=500)unknown.push('archive server '+endpoint+' '+response.status())
        return route.fulfill({response})
      }
      if(request.method()!=='GET'){unknown.push('archive unexpected write '+endpoint);return route.abort()}
      try{return route.fulfill({json:fixtureResponse(endpoint,url.searchParams,request.method())})}
      catch(error){unknown.push(String(error));return route.fulfill({status:501,json:{detail:String(error)}})}
    })
    const page=await context.newPage();page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message))
    await page.goto(base+'/project/archive')
    await expect(page.getByRole('button',{name:'新增档案',exact:true})).toBeVisible()
    await expect(page.locator('[role="gridcell"][col-id="project_code"]').first()).toBeVisible()
    const form=page.getByRole('dialog',{name:'新增项目档案',exact:true})
    const field=(key,scope=form)=>scope.locator(`#${scope===form?'archive-create':'archive-drawer'}-${key}`)
    async function pick(name,label,scope=form){const input=scope.getByRole('combobox',{name,exact:true});await input.locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]').click();await page.getByRole('option',{name:label,exact:true}).click()}
    async function restore(code){
      await page.getByRole('button',{name:'我的草稿',exact:true}).click()
      const box=page.getByRole('dialog',{name:'我的草稿',exact:true})
      await box.locator('tr').filter({hasText:code}).getByRole('button',{name:'继续填写',exact:true}).click();await expect(form).toBeVisible()
    }
    return {page,context,form,field,pick,restore}
  }
  async function columns(page){return page.evaluate(()=>{
    const headers=[...document.querySelectorAll('.project-archive-page .ag-header-cell[col-id]')].map(el=>({colId:el.getAttribute('col-id'),rect:el.getBoundingClientRect()})).filter(x=>x.rect.width>0&&x.rect.height>0).sort((a,b)=>a.rect.x-b.rect.x)
    const preference=JSON.parse(localStorage.getItem('pms_project_archive_list_columns_v2:997')||'{}')
    return {displayed:headers.map(x=>x.colId),state:preference.columnState||[]}
  })}
  const prefKey='pms_project_archive_list_columns_v2:997',schemeKey='pms:query-workspace:v2:997:project-archive'
  const legacy={selected_column_keys:['customer','project_code','project_name'],columnState:[{colId:'customer',width:231,pinned:'left',hide:false},{colId:'project_name',width:291,hide:false},{colId:'project_code',width:161,pinned:null}]}
  const definitions=[{field:'project_code',shown:true,operator:'contains',value:'BATCH',valueEnd:null,schemaVersion:2}]
  const scheme={version:2,name:'组合旧列方案',isDefault:true,definitions,preferences:{pageSize:100,columns:legacy}}
  try{
    let f=await open({seed:{[prefKey]:legacy,[schemeKey]:[scheme]}})
    await expect.poll(async()=>(await columns(f.page)).displayed.slice(0,3)).toEqual(['archive_selection','product_line_id','project_code'])
    let cols=await columns(f.page);assert.equal(cols.state.find(c=>c.colId==='customer').width,231);assert.equal(cols.state.find(c=>c.colId==='project_name').width,291)
    assert.deepEqual(await f.page.evaluate(k=>JSON.parse(localStorage.getItem(k)),schemeKey),[scheme],'old named scheme not rewritten by read')
    const count=()=>requests.filter(r=>r.path==='/projects/archives/list').length
    const beforeQuery=count()
    await f.page.getByRole('button',{name:'方案设置',exact:true}).click()
    const settings=f.page.getByRole('dialog',{name:'查询方案设置',exact:true})
    await settings.getByRole('textbox',{name:'方案名称',exact:true}).fill('组合改名')
    await settings.getByRole('button',{name:'保存方案',exact:true}).click();await expect(settings).not.toBeVisible()
    assert.equal(count(),beforeQuery)
    const written=await f.page.evaluate(k=>JSON.parse(localStorage.getItem(k)),schemeKey)
    assert.equal(written[0].preferences.columns.layout_version,1);assert.equal(written[0].preferences.columns.columnState.find(c=>c.colId==='customer').width,231)
    await f.page.reload();await expect(f.page.getByRole('button',{name:'新增档案',exact:true})).toBeVisible()
    await expect.poll(async()=>(await columns(f.page)).displayed.slice(0,3)).toEqual(['archive_selection','product_line_id','project_code'])
    await expect(f.page.locator('[role="gridcell"][col-id="project_code"]').first()).toBeVisible()
    const rowsBeforeDelete=await f.page.locator('[role="gridcell"][col-id="project_code"]').allTextContents()
    const afterReload=count()
    await f.page.getByRole('button',{name:'方案设置',exact:true}).click()
    await settings.getByRole('button',{name:'删除方案',exact:true}).click()
    const confirm=f.page.getByRole('dialog',{name:'删除个人方案',exact:true});await confirm.getByRole('button',{name:'删除方案',exact:true}).click()
    await expect(settings).not.toBeVisible();assert.equal(count(),afterReload)
    assert.deepEqual(await f.page.locator('[role="gridcell"][col-id="project_code"]').allTextContents(),rowsBeforeDelete)
    assert.deepEqual(await f.page.evaluate(k=>JSON.parse(localStorage.getItem(k)),schemeKey),[])
    checks.push('actual P28+C1: legacy personal/named columns migrate once; rename/save marker preserves widths; reload valid; delete-last falls back without querying or clearing rows')
    await f.page.getByRole('button',{name:'说明',exact:true}).click()
    const guide=f.page.locator('.pms-page-guide-dialog');await expect(guide).toContainText('页面说明');await f.page.screenshot({path:path.join(out,'archive-guide.png'),animations:'disabled'});await guide.locator('.el-dialog__headerbtn').click()
    await f.page.getByRole('button',{name:'新增档案',exact:true}).click()
    await expect(f.field('quantity')).toHaveValue('1');await expect(f.form.getByText('pcs',{exact:true})).toBeVisible();await expect(f.form.getByText('合成操作者',{exact:true})).toBeVisible()
    for(const key of ['customer_full_name','legacy_archive_status','legacy_code_date','legacy_updated_date','delivery_note','remarks'])await expect(f.form.locator(`label[for="archive-create-${key}"]`)).toHaveCount(0)
    await f.pick('产品线','8吋Bench');await f.pick('档案类别','主机');await f.field('serial_no').fill('BATCH-UI-SN');await f.pick('设备系列','DF-2000B');await f.pick('档案类别','辅机')
    await expect(f.field('serial_no')).toHaveCount(0);await expect(f.field('equipment_series')).toHaveCount(0)
    await f.field('project_code').fill('BATCH-UI');await f.field('project_name').fill('合成真实页面草稿')
    let savedResponse=f.page.waitForResponse(r=>r.url()===base+draftBase&&r.request().method()==='POST')
    await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();assert.equal((await savedResponse).status(),200)
    const savedBody=await (await savedResponse).json();assert.equal(savedBody.payload.serial_no,'BATCH-UI-SN');assert.equal(Number(savedBody.payload.quantity),1);assert.equal(savedBody.payload.quantity_unit,7)
    await f.form.getByRole('button',{name:'取消',exact:true}).click();await expect(f.form).not.toBeVisible()
    await f.restore('BATCH-OLD-DRAFT');await expect(f.field('quantity')).toHaveValue('');await expect(f.form.getByText('合成部门负责人',{exact:true})).toBeVisible()
    await f.pick('产品线','12吋Bench');await expect(f.field('equipment_series')).toBeVisible();await expect(f.form.getByText('DF-2000B',{exact:true})).toBeVisible()
    const draftWrites=()=>requests.filter(r=>r.path==='/form-drafts/archive-create'&&r.method==='POST').length,beforeInvalid=draftWrites()
    await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();assert.equal(draftWrites(),beforeInvalid)
    await f.pick('设备系列','DF-3000B')
    savedResponse=f.page.waitForResponse(r=>r.url()===base+draftBase&&r.request().method()==='POST')
    await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();const history=(await (await savedResponse).json());assert.equal((await savedResponse).status(),200)
    assert.equal(history.payload.equipment_series,12);assert.equal(history.payload.serial_no,'BATCH-OLD-SN');assert.equal(history.payload.remarks,'合成历史隐藏备注');assert.ok(history.payload.quantity==null);assert.ok(history.payload.quantity_unit==null)
    await expect(f.field('equipment_series')).toHaveCount(0)
    await f.form.getByRole('button',{name:'取消',exact:true}).click();await f.restore('BATCH-SERIAL-DRAFT')
    savedResponse=f.page.waitForResponse(r=>r.url()===base+draftBase&&r.request().method()==='POST')
    await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();assert.equal((await savedResponse).status(),409)
    await expect(f.field('serial_no')).toHaveValue('BATCH-HIST-SN');await expect(f.form).toContainText('序列号已存在或已被草稿、待审批变更占用')
    await f.field('serial_no').fill('');savedResponse=f.page.waitForResponse(r=>r.url()===base+draftBase&&r.request().method()==='POST')
    await f.form.getByRole('button',{name:'保存草稿',exact:true}).click();assert.equal((await savedResponse).status(),200);assert.equal((await (await savedResponse).json()).payload.serial_no,null)
    await expect(f.field('serial_no')).toHaveCount(0)
    await f.form.getByRole('button',{name:'取消',exact:true}).click()
    checks.push('actual server-backed UI: fresh owner/pcs/defaults; hidden regional values absent; draft save; restore no defaults; hidden incompatible series blocks until explicit correction; real serial409 preserves input and allows explicit clear/re-hide')
    const addressBefore=await archive('BATCH-ADDRESS')
    const maintenance={updates:{manager_id:998},expected_version:addressBefore.change_version,reason:'合成历史负责人维护'}
    await api(`/api/projects/archives/${addressBefore.id}/maintenance/preview`,{method:'POST',body:{updates:{manager_id:998,project_name:addressBefore.project_name},expected_version:addressBefore.change_version},status:422})
    await api(`/api/projects/archives/${addressBefore.id}`,{method:'PUT',user:998,body:{manager_id:998,expected_version:addressBefore.change_version},status:422})
    const addressScheme={version:2,name:'历史地址验收',isDefault:true,definitions:[{field:'project_code',shown:true,operator:'equals',value:'BATCH-ADDRESS',valueEnd:null,schemaVersion:2}],preferences:{}}
    const a=await open({seed:{[schemeKey]:[addressScheme]}})
    await a.page.getByRole('button',{name:'编辑',exact:true}).click()
    let detail=a.page.getByRole('dialog',{name:'编辑项目档案',exact:true});await expect(detail).toBeVisible()
    await detail.getByRole('button',{name:'维护',exact:true}).click();detail=a.page.getByRole('dialog',{name:'维护项目档案',exact:true})
    await a.pick('负责人','合成部门负责人',detail)
    const previewResponse=a.page.waitForResponse(r=>r.url().endsWith(`/archives/${addressBefore.id}/maintenance/preview`))
    await detail.getByRole('button',{name:'确认维护',exact:true}).click();assert.equal((await previewResponse).status(),200)
    const confirmation=a.page.getByRole('dialog',{name:'确认档案维护',exact:true});await expect(confirmation).toBeVisible()
    await confirmation.getByRole('textbox',{name:'维护原因',exact:true}).fill(maintenance.reason)
    const maintained=a.page.waitForResponse(r=>r.url().endsWith(`/archives/${addressBefore.id}/maintenance`)&&r.request().method()==='PUT')
    await confirmation.getByRole('button',{name:'确认生效',exact:true}).click();assert.equal((await maintained).status(),200)
    const addressAfter=await archive('BATCH-ADDRESS');assert.equal(addressAfter.manager_id,998)
    const raw=(await state()).archives.find(r=>r.project_code==='BATCH-ADDRESS');assert.equal(raw.address_detail,'  合成历史原地址  ');assert.equal(raw.address_province,null);assert.equal(raw.address_city,null)
    const historyLog=await api(`/api/document-history/archive/${addressBefore.id}`)
    assert.equal(historyLog.items[0].action,'maintain');assert.match(historyLog.items[0].summary,/合成历史负责人维护/)
    assert.equal(historyLog.items[0].diff_items.length,1);assert.match(historyLog.items[0].diff_items[0].after_display,/合成部门负责人/)
    await a.page.screenshot({path:path.join(out,'historical-owner-maintenance.png'),animations:'disabled'})
    checks.push('actual P29 maintenance UI+API: owner-only preview/reason/save; raw incomplete address unchanged; extra unchanged key/ordinary edit rejected; one Chinese owner diff in document audit')
    // Three established themes, actual core metadata; no new theme/UI baseline.
    for(const [id,label]of [['blue','办公蓝'],['teal','青绿'],['graphite','石墨']]){
      await f.page.getByRole('button',{name:'切换外观',exact:true}).click();await f.page.getByRole('menuitem',{name:label,exact:true}).click()
      await expect(f.page.locator('html')).toHaveAttribute('data-pms-theme',id)
      await f.page.getByRole('button',{name:'新增档案',exact:true}).click();await f.pick('档案类别','辅机');await expect(f.field('serial_no')).toHaveCount(0)
      await f.page.screenshot({path:path.join(out,'archive-nonmain-'+id+'.png'),animations:'disabled'})
      await f.pick('档案类别','主机');await expect(f.field('serial_no')).toBeVisible();await f.page.screenshot({path:path.join(out,'archive-main-'+id+'.png'),animations:'disabled'})
      await f.form.getByRole('button',{name:'取消',exact:true}).click()
      const unsaved=f.page.getByRole('dialog',{name:'未保存修改',exact:true});if(await unsaved.isVisible())await unsaved.getByRole('button',{name:'放弃本次修改',exact:true}).click()
    }
    checks.push('actual archive main/non-main form, shared fields/layout/required markers in all three established themes')
    await writeFile(path.join(out,'archive-combined-state.json'),JSON.stringify(await state(),null,2))
  }catch(error){
    for(const [i,context]of contexts.entries())for(const page of context.pages())await page.screenshot({path:path.join(out,'archive-failure-'+i+'.png'),animations:'disabled'}).catch(()=>{})
    throw error
  }finally{for(const context of contexts){await context.unrouteAll({behavior:'wait'});await context.close()}}
}
