import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
const root = resolve(import.meta.dirname, '../..')
const metadata = JSON.parse(execFileSync('/Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3', ['-c', 'import json; from app.services.purchase_fields import *; from app.services.report_filters import filter_fields; print(json.dumps(dict(fields=report_fields(),overview_fields=overview_fields(),filter_fields=filter_fields("purchase"),progress_labels=PROGRESS_LABELS,document_status_labels=DOCUMENT_STATUSES,organizations=[dict(value=100,label="8吋Bench"),dict(value=200,label="Single")],start_date="2026-01-01")))'], {cwd:resolve(root,'backend'),env:{...process.env,PYTHONPATH:resolve(root,'backend/.venv-deps312')},encoding:'utf8'}))
const browser = await chromium.launch({channel:'msedge',headless:true})
const page = await browser.newPage({viewport:{width:1440,height:900}})
const overviewRequests=[], detailRequests=[], errors=[]
let fail=false, failDetail=false
page.on('pageerror',error=>errors.push(error.message))
await page.addInitScript(()=>localStorage.setItem('access_token','mock-token'))
await page.addInitScript(()=>localStorage.setItem('pms:purchase-overview:v1:990',JSON.stringify({columns:[{colId:'completion_rate',sort:'desc'}]})))
await page.addInitScript(()=>localStorage.setItem('pms:purchase-overview:v1:990:plans',JSON.stringify([{version:1,name:'待提交排序方案',state:{keyword:'',project_code:'',supplier:'',progress:'',organization_ids:[],dates:[],conditions:[],overviewStatus:'',pageSize:50,visible:['product_line_name','project_code','project_name','completion_rate','total_lines','not_ordered_lines','ordering_lines','receiving_lines','complete_lines','review_lines'],columns:[{colId:'completion_rate',sort:'asc'}],sort:{sort:'completion_rate',direction:'asc'}}}])))
await page.route('**/api/**',route=>{
  const url=new URL(route.request().url()), path=url.pathname
  if (!path.startsWith('/api/')) return route.continue()
  if(path==='/api/auth/me') return route.fulfill({json:{id:990,username:'test',real_name:'测试',permissions:['report:purchase:view'],role_codes:[],data_scope:1}})
  if(path==='/api/my-menus') return route.fulfill({json:[{id:4,menu_name:'报表中心',menu_type:'M',icon:'DataAnalysis',children:[{id:41,menu_name:'采购进度查询',path:'/reports/purchase-progress',icon:'Document'}]}]})
  if(path.endsWith('/metadata')) return route.fulfill({json:metadata})
  if(path.endsWith('/options')) return route.fulfill({json:{items:url.searchParams.get('project_code')?[{value:url.searchParams.get('project_code'),label:url.searchParams.get('project_code')}]:[],has_more:false}})
  if(path==='/api/reports/purchase/overview') {
    overviewRequests.push(Object.fromEntries(url.searchParams))
    if(fail) return route.fulfill({status:503,json:{detail:'测试查询失败'}})
    const second=url.searchParams.get('page')==='2'
    const items=Array.from({length:second?2:50},(_,index)=>({id:JSON.stringify([second?200:100,`P-${second?2:1}-${index}`]),organization_id:second?200:100,product_line_name:second?'Single':'8吋Bench',project_code:second?'P-2':index?`P-1-${index}`:'P-1',project_name:'PMS项目名称',organization_name:second?'Single组织':'8吋半导体',total_lines:10,completion_rate:40,not_ordered_lines:1,ordering_lines:2,receiving_lines:2,complete_lines:4,review_lines:1}))
    return route.fulfill({json:{items,total:52,total_lines:520,complete_lines:208,review_lines:52,queried_at:'2026-10-09T06:00:00Z'}})
  }
  if(path==='/api/reports/purchase') {
    detailRequests.push({...Object.fromEntries(url.searchParams),organization_ids:url.searchParams.getAll('organization_ids')})
    if(failDetail) return route.fulfill({status:503,json:{detail:'测试明细失败'}})
    return route.fulfill({json:{items:[{id:1,product_line_name:'Single',project_code:'P-2',project_name:'PMS项目名称',bill_no:'CGSQ-1',line_no:1,material_name:'测试物料',unit_name:'只',progress:'complete',progress_label:'已完成',document_status:'C'}],total:1,queried_at:'2026-10-09T06:01:00Z'}})
  }
  return route.fulfill({json:[]})
})
try {
  await page.goto('http://127.0.0.1:5174/reports/purchase-progress')
  await expect(page.getByRole('button',{name:'总进度',exact:true})).toHaveAttribute('aria-pressed','true')
  assert.equal(overviewRequests.length+detailRequests.length,0,'进入页面不查ERP业务数据')
  const summary=page.locator('.purchase-overview-page')
  await summary.getByRole('button',{name:'查询',exact:true}).click()
  await expect(summary.locator('[col-id="completion_rate"][role="gridcell"]').first()).toContainText('40.0%')
  assert.equal(overviewRequests[0].sort,'completion_rate','列设置恢复后的箭头与请求排序一致')
  assert.equal(overviewRequests[0].direction,'desc')
  assert.deepEqual(await summary.locator('.ag-pinned-left-header .ag-header-cell').evaluateAll(els=>els.map(el=>el.getAttribute('col-id'))),['product_line_name','project_code','project_name'])
  await summary.locator('.pms-report-plans .el-select__wrapper').click()
  await page.getByRole('option',{name:'待提交排序方案',exact:true}).click()
  await summary.locator('.custom-pagination').getByRole('button',{name:'2',exact:true}).click()
  await expect.poll(()=>overviewRequests.at(-1).page).toBe('2')
  assert.equal(overviewRequests.at(-1).direction,'desc','加载方案未查询时，翻页保留已生效排序')
  await expect(summary.locator('[col-id="project_code"][role="gridcell"]').first()).toContainText('P-2')
  await summary.getByRole('textbox',{name:'搜索采购明细'}).fill('未提交草稿')
  await summary.locator('[col-id="review_lines"][role="gridcell"] button').first().click()
  const detail=page.locator('.purchase-detail-view')
  await expect.poll(()=>detailRequests.length).toBe(1)
  assert.equal(detailRequests[0].project_code,'P-2')
  assert.deepEqual(detailRequests[0].organization_ids,['200'])
  assert.equal(detailRequests[0].keyword,'','下钻不用未提交草稿')
  assert.ok(JSON.parse(detailRequests[0].filters).some(c=>c.field==='progress'&&c.value==='review'))
  await expect(detail.getByText('当前项目限定',{exact:false})).toBeVisible()
  assert.deepEqual(await detail.locator('.ag-pinned-left-header .ag-header-cell').evaluateAll(els=>els.map(el=>el.getAttribute('col-id'))),['product_line_name','project_code','project_name'])
  await detail.getByRole('button',{name:'保存查询方案',exact:true}).click()
  await page.getByRole('textbox',{name:'方案名称',exact:true}).fill('项目限定方案')
  await page.getByRole('button',{name:'保存',exact:true}).filter({visible:true}).click()
  await detail.getByRole('button',{name:'重置',exact:true}).click()
  await detail.locator('.pms-report-query-plan-select').click()
  await page.getByRole('option',{name:'项目限定方案',exact:true}).click()
  const beforePlan=detailRequests.length
  await detail.getByRole('button',{name:'查询',exact:true}).click()
  await expect.poll(()=>detailRequests.length).toBe(beforePlan+1)
  assert.equal(detailRequests.at(-1).project_code,'P-2','恢复查询方案必须保留项目限定')
  assert.deepEqual(detailRequests.at(-1).organization_ids,['200'])
  await page.getByRole('button',{name:'总进度',exact:true}).filter({visible:true}).click()
  await expect(summary.getByRole('textbox',{name:'搜索采购明细'})).toHaveValue('未提交草稿')
  assert.equal(overviewRequests.length,2,'返回复用总表缓存与页码')
  await expect(summary.locator('.custom-pagination').getByRole('button',{name:'2',exact:true})).toHaveClass(/active/)
  const beforeAll=detailRequests.length
  await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
  await expect.poll(()=>detailRequests.length).toBe(beforeAll+1)
  assert.equal(detailRequests.at(-1).project_code,'')
  assert.deepEqual(detailRequests.at(-1).organization_ids,[],'表头明细不保留项目限定')
  assert.equal(JSON.parse(detailRequests.at(-1).filters).length,0)
  await page.getByRole('button',{name:'总进度',exact:true}).filter({visible:true}).click()
  fail=true
  await summary.getByRole('button',{name:'查询',exact:true}).click()
  await expect(summary.getByRole('alert').filter({hasText:'查询失败'})).toBeVisible()
  await expect(summary.locator('[col-id="project_code"][role="gridcell"]').first()).toContainText('P-2')
  fail=false
  await summary.getByRole('button',{name:'重试',exact:true}).click()
  await expect(summary.locator('.pms-list-load-error')).toHaveCount(0)
  await summary.getByRole('textbox',{name:'搜索采购明细'}).fill('')
  await summary.getByRole('button',{name:'查询',exact:true}).click()
  await expect(summary.locator('[col-id="project_code"][role="gridcell"]').first()).toContainText('P-1')
  failDetail=true
  await summary.getByRole('button',{name:'明细',exact:true}).first().click()
  await expect(detail.getByRole('alert').filter({hasText:'采购数据加载失败'})).toBeVisible()
  await expect(detail.locator('.pms-report-query-status')).toContainText('条件已修改，待查询')
  await expect(detail.getByText('上次结果范围：当前查询范围全部项目',{exact:false})).toBeVisible()
  failDetail=false
  await detail.getByRole('button',{name:'重试',exact:true}).click()
  await expect(detail.locator('.pms-list-load-error')).toHaveCount(0)
  await page.getByRole('button',{name:'总进度',exact:true}).filter({visible:true}).click()
  const viewport=summary.locator('.ag-body-viewport')
  await viewport.evaluate(el=>{el.scrollTop=480})
  await expect.poll(()=>viewport.evaluate(el=>el.scrollTop)).toBeGreaterThan(400)
  const scrollBeforeReturn=await viewport.evaluate(el=>el.scrollTop)
  await summary.locator('.ag-pinned-right-cols-container [row-index="18"] button').click()
  const beforeReturn=overviewRequests.length
  await page.getByRole('button',{name:'总进度',exact:true}).filter({visible:true}).click()
  await expect.poll(()=>viewport.evaluate(el=>el.scrollTop)).toBe(scrollBeforeReturn)
  assert.equal(overviewRequests.length,beforeReturn,'返回滚动位置不重新查询')
  await viewport.evaluate(el=>{el.scrollTop=0})
  await expect(page.locator('.el-message')).toHaveCount(0,{timeout:10000})
  for(const viewport of [{width:1920,height:1080},{width:1182,height:760},{width:390,height:844}]) {
    await page.setViewportSize(viewport)
    await page.evaluate(()=>document.fonts.ready)
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))
    if(viewport.width===1920) {
      const unused=await summary.evaluate(el=>{
        const last=el.querySelector('.ag-header-viewport [col-id="review_lines"]')
        const action=el.querySelector('.ag-pinned-right-header')
        return action.getBoundingClientRect().left-last.getBoundingClientRect().right
      })
      assert.ok(unused<8,`默认总表列应铺满宽屏，实际空白 ${unused}px`)
    }
    await page.screenshot({path:resolve(root,`.runtime/purchase-overview-formal-${viewport.width}.png`)})
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'页面不得横向溢出')
  }
  assert.deepEqual(errors,[])
  console.log('PASS overview: manual query, shared labels/order, org-isolated drill, status drill, cached return, draft snapshot, failure/retry, responsive')
} finally {await browser.close()}
