import assert from 'node:assert/strict'
import {choosePageSize} from './page-size-helper.mjs'
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { chromium, expect as baseExpect } from '@playwright/test'
import { createServer } from 'vite'

const root = resolve(import.meta.dirname, '../..')
const expect = baseExpect.configure({timeout:30000})
const server = await createServer({server:{host:'127.0.0.1',port:0}})
await server.listen()
const base = `http://127.0.0.1:${server.httpServer.address().port}`
const metadata = JSON.parse(execFileSync(resolve(root, 'backend/.venv/bin/python'), ['-c', 'import json; from app.services.purchase_fields import *; from app.services.report_filters import query_fields; print(json.dumps(dict(fields=report_fields(),overview_fields=overview_fields(),query_fields=query_fields("purchase"),overview_query_fields=query_fields("purchase-overview"),overview_column_filter_fields=query_fields("purchase-overview"),progress_labels=PROGRESS_LABELS,document_status_labels=DOCUMENT_STATUSES,organizations=[dict(value=499413,label="8吋Bench")],start_date="2026-01-01")))'], {cwd:resolve(root,'backend'),encoding:'utf8'}))
metadata.overview_query_fields = [...new Map([...metadata.query_fields,...metadata.overview_query_fields].map(f=>[f.field,f])).values()]
const all=Array.from({length:279},(_,i)=>({id:`499413:A-${String(i).padStart(6,'0')}`,project_code:`A-${String(i).padStart(6,'0')}`,product_line_name:'8吋Bench',organization_id:499413,total_lines:10,complete_lines:5,review_lines:0,not_ordered_lines:3,ordering_lines:1,receiving_lines:1,completion_rate:50,conversion_rate:60}))
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1440,height:900}}), calls=[],exports=[],errors=[]
await page.addInitScript(()=>localStorage.setItem('access_token','isolated-page-filter'))
await page.route('**/api/**',async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname
  if(!path.startsWith('/api/')) return route.continue()
  if(path==='/api/auth/me') return route.fulfill({json:{id:997,username:'fixture',real_name:'当前页测试',permissions:['report:purchase:view','report:purchase:export'],role_codes:[],data_scope:4}})
  if(path.endsWith('/metadata')) return route.fulfill({json:metadata})
  if(path.endsWith('/column-options')) throw Error('当前页漏斗不得请求后台候选')
  if(path==='/api/reports/purchase/overview') {
    const params=Object.fromEntries(url.searchParams);calls.push(params)
    assert.equal(params.column_filters,'[]')
    const start=(Number(params.page)-1)*Number(params.page_size)
    return route.fulfill({json:{items:all.slice(start,start+Number(params.page_size)),total:279,total_lines:2790,complete_lines:1395,review_lines:0,queried_at:'2026-10-12T00:00:00Z'}})
  }
  if(path.startsWith('/api/report-exports')&&request.method()==='POST') {
    exports.push(request.postDataJSON())
    return route.fulfill({json:{id:'b'.repeat(32),status:'success',report:'purchase',processed:279,created_at:'2026-10-12T00:00:00'}})
  }
  assert.equal(request.method(),'GET',`Unexpected write: ${path}`)
  return route.fulfill({json:[]})
})
page.on('pageerror',e=>errors.push(e.message))
page.on('console',message=>{if(message.type()==='error') console.error('browser console',message.text())})
page.on('requestfailed',request=>console.error('request failed',request.url(),request.failure()?.errorText))
try {
  await page.goto(`${base}/reports/purchase-progress`)
  const list=page.locator('.purchase-overview-page')
  await expect(list.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
  assert.equal(calls.length,0)
  await list.getByRole('button',{name:'查询',exact:true}).click()
  await expect.poll(()=>calls.length).toBe(1)
  await expect(list.locator('[col-id="project_code"][role="gridcell"]').first()).toContainText('A-000000')
  await list.getByRole('button',{name:'项目编码列筛选',exact:true}).click()
  let panel=page.getByRole('dialog',{name:'项目编码列筛选面板',exact:true})
  await expect(panel.getByText('仅筛选当前页',{exact:true})).toBeVisible()
  await expect(panel.locator('.pms-column-filter-values .el-checkbox')).toHaveCount(50)
  await expect(panel.getByText('A-000050',{exact:true})).toHaveCount(0)
  const folder=resolve(root,'outputs/page-column-filter-20261012');mkdirSync(folder,{recursive:true})
  await expect.poll(() => panel.evaluate(el => {
    for (let node = el; node; node = node.parentElement) {
      if (getComputedStyle(node).opacity !== '1') return false
    }
    return true
  })).toBe(true)
  await page.screenshot({path:resolve(folder,'current-page-popup.png')})
  const sizes=await panel.locator('.el-button').evaluateAll(els=>els.filter(el=>el.offsetHeight).map(el=>Math.round(el.getBoundingClientRect().height)))
  assert.ok(sizes.every(height=>height===24),`popup buttons: ${sizes}`)
  await panel.getByText('全选已加载值',{exact:true}).click()
  await panel.getByText('A-000001',{exact:true}).click()
  await panel.getByRole('button',{name:'应用',exact:true}).click()
  await expect(list.locator('[col-id="project_code"][role="gridcell"]')).toHaveCount(1)
  assert.equal(calls.length,1,'本页筛选不重新查询')
  await expect(list.getByText('共 279 条',{exact:true})).toBeVisible()
  await list.getByRole('button',{name:'导出数据',exact:true}).click()
  await expect.poll(()=>exports.length).toBe(1)
  assert.equal(exports[0].parameters.column_filters,'[]')
  await list.locator('.custom-pagination button').filter({hasText:/^2$/}).click()
  await expect.poll(()=>calls.length).toBe(2)
  assert.equal(calls.at(-1).page,'2')
  await expect(list.locator('[col-id="project_code"][role="gridcell"]').first()).toContainText('A-000050')
  await expect(list.locator('.pms-column-filter-trigger.is-filtered')).toHaveCount(0)
  await choosePageSize(list,500)
  await expect.poll(()=>calls.at(-1).page_size).toBe('500')
  assert.equal(calls.at(-1).page,'1')
  await list.getByRole('button',{name:'项目编码列筛选',exact:true}).click()
  panel=page.getByRole('dialog',{name:'项目编码列筛选面板',exact:true})
  await expect(panel.locator('.pms-column-filter-values .el-checkbox')).toHaveCount(100)
  await panel.getByRole('button',{name:'加载更多',exact:true}).click()
  await expect(panel.locator('.pms-column-filter-values .el-checkbox')).toHaveCount(200)
  await panel.getByRole('button',{name:'加载更多',exact:true}).click()
  await expect(panel.locator('.pms-column-filter-values .el-checkbox')).toHaveCount(279)
  assert.equal(calls.length,3)
  await list.locator('[col-id="total_lines"][role="columnheader"]').click()
  await expect(panel).toHaveCount(0)
  assert.deepEqual(errors,[])
  console.log('PASS: 279/50 current-page candidates, local checkbox filtering/no network, full export scope, page reset, 500 accepted, local load-more, 24px palette, outside close')
} catch(error) {
  console.error({calls,errors,body:await page.locator('body').innerText()})
  throw error
} finally {await browser.close();await server.close()}
