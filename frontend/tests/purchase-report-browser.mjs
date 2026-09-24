import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
const root = resolve(import.meta.dirname, '../..')
const metadata = JSON.parse(execFileSync(resolve(root, 'backend/.venv-security312/bin/python'), ['-c', 'import json; from app.services.purchase_fields import report_fields,PROGRESS_LABELS,DOCUMENT_STATUSES; print(json.dumps(dict(fields=report_fields(),progress_labels=PROGRESS_LABELS,document_status_labels=DOCUMENT_STATUSES,export_limit=500)))'], { cwd: resolve(root, 'backend'), encoding: 'utf8' }))
metadata.filter_fields=[{field:'material_name',label:'物料名称',type:'text'},{field:'requested',label:'申请数量',type:'number'},{field:'progress',label:'采购进度',type:'enum',operators:['equals','notEquals'],options:[{value:'ordering',label:'部分下单'}]}]
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1600, height: 900 } })
await context.addInitScript(() => localStorage.setItem('access_token', 'isolated-report-ui-fixture'))
const page = await context.newPage()
const errors = [], requests = []
let detailFailure = false, listFailure = false, canExport = true, exportBody
const rows = Array.from({ length: 50 }, (_, index) => ({ id: index + 1, bill_no: `CGSQ-${index + 1}`, line_no: 1,
  project_code: 'A-202629', material_name: `阀门 ${index + 1}`, material_code: 'M001', unit_name: '只', application_date: '2026-09-01',
  document_status: 'C', requested: 18, approved: 18, ordered: index ? 0 : 18, net_received: index ? 0 : 8,
  pending_order: index ? 18 : 0, pending_receipt: index ? 0 : 10, progress: index ? 'not_ordered' : 'receiving', progress_label: index ? '未下单' : '待入库' }))
const order = (id, quantity) => ({ id, bill_no: `ORDER-${id}`, line_no: 1, order_date: '2026-09-02', supplier_name: '供应商测试', unit_name: '只', quantity, document_status: 'C', effective: true })
page.on('pageerror', error => errors.push(error.message))
await page.route('**/api/**', async route => {
  const url = new URL(route.request().url()), path = url.pathname
  if (!path.startsWith('/api/')) return route.continue()
  if (path === '/api/report-exports') {
    if(route.request().method()==='POST') {exportBody=route.request().postDataJSON();return route.fulfill({json:{id:'fixture',status:'pending',processed:0,created_at:'2026-09-24T00:00:00'}})}
    return route.fulfill({json:[]})
  }
  if (path === '/api/auth/me') return route.fulfill({ json: { id: 990, username: 'report-test', real_name: '报表测试', permissions: ['report:purchase:view', ...(canExport ? ['report:purchase:export'] : [])], role_codes: [], data_scope: 4 } })
  if (path === '/api/my-menus') return route.fulfill({ json: [{ id: 4, menu_name: '报表中心', menu_type: 'M', icon: 'DataAnalysis', children: [{ id: 41, menu_name: '采购进度查询', path: '/reports/purchase-progress', icon: 'Document' }] }] })
  if (path === '/api/reports/purchase/metadata') return route.fulfill({ json: metadata })
  if (path === '/api/reports/purchase/options') return route.fulfill({ json: { items: [{ value: 'A-202629', label: 'A-202629' }], has_more: false } })
  if (path === '/api/reports/purchase') {
    requests.push(Object.fromEntries(url.searchParams))
    if (listFailure) return route.fulfill({ status: 503, json: { detail: '测试：数据源暂不可用' } })
    const filtered = url.searchParams.get('keyword') ? rows.filter(row => row.bill_no === url.searchParams.get('keyword')) : rows
    return route.fulfill({ json: { total: filtered.length === 1 ? 1 : 1050, items: url.searchParams.get('page') === '2' ? rows.map(row => ({ ...row, id: row.id + 50 })) : filtered, queried_at: '2026-09-21T06:00:00Z' } })
  }
  if (/\/purchase\/\d+$/.test(path)) {
    const id = Number(path.split('/').at(-1))
    if (id === 3) await new Promise(resolve => setTimeout(resolve, 800))
    if (detailFailure) return route.fulfill({ status: 503, json: { detail: '测试：明细不可用' } })
    return route.fulfill({ json: { request: rows[id - 1], orders: id === 1 ? [order(11, 10), order(12, 8)] : [],
      receipts: id === 1 ? [3, 5].map((qty, index) => ({ id: 21 + index, order_id: 12, bill_no: `STOCK-${index + 1}`, line_no: 1, quantity: qty, unit_name: '只', stock_date: '2026-09-03', document_status: 'C', effective: true })) : [],
      returns: [], summary: { issues: [], net_received: id === 1 ? 8 : 0 }, queried_at: '2026-09-21T06:00:00Z' } })
  }
  throw new Error(`Unexpected API call: ${path}`)
})
try {
  await page.goto('http://127.0.0.1:5191/reports/purchase-progress')
  await expect(page.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
  assert.equal(requests.length,0,'进入页面不得查询业务数据')
  await page.getByRole('button',{name:'查询',exact:true}).click()
  await expect(page.getByRole('button', { name: '明细', exact: true }).first()).toBeVisible()
  assert.equal(requests[0].page_size, '50')
  const search=page.getByRole('textbox',{name:'搜索采购明细'})
  await search.fill('尚未查询的草稿')
  await page.getByRole('button',{name:'2',exact:true}).click()
  await expect.poll(()=>requests.at(-1).page).toBe('2')
  assert.equal(requests.at(-1).keyword,'')
  await page.getByRole('button',{name:'导出当前筛选',exact:true}).click()
  await page.getByRole('button',{name:'继续导出',exact:true}).click()
  await expect.poll(()=>!!exportBody).toBe(true)
  assert.equal(exportBody.parameters.keyword,'')
  listFailure=true
  await page.getByRole('button',{name:'1',exact:true}).click()
  await expect(page.getByRole('alert').filter({hasText:'采购数据加载失败'})).toBeVisible()
  listFailure=false
  await page.getByRole('button',{name:'重试',exact:true}).click()
  await expect.poll(()=>requests.at(-1).page).toBe('1')
  assert.equal(requests.at(-1).keyword,'')
  await search.fill('')
  await expect(page.locator('.pms-list-load-error')).toHaveCount(0)
  await page.locator('.pms-data-list-toolbar').click({position:{x:450,y:10}})
  await expect(page.locator('.el-message')).toHaveCount(0,{timeout:10000})
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: resolve(root, '.runtime/purchase-formal-1600.png') })
  await page.getByRole('button', { name: '明细', exact: true }).first().click()
  const drawer = page.getByRole('dialog', { name: '采购关联明细' })
  await expect(drawer.getByRole('button', { name: 'ORDER-12', exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: 'ORDER-11', exact: true }).click()
  await expect(drawer.getByText('此订单暂无入库记录')).toBeVisible()
  await drawer.getByRole('button', { name: '查看全部' }).click()
  await expect(drawer.getByText('STOCK-2', { exact: true })).toBeVisible()
  await page.screenshot({ path: resolve(root, '.runtime/purchase-formal-detail-1600.png') })
  await page.locator('.ag-pinned-left-cols-container [row-id="2"] [col-id="material_name"]').click()
  await expect(drawer.getByRole('heading', { name: '阀门 2', exact: true })).toBeVisible()
  await expect(drawer.getByText('尚未形成采购订单')).toBeVisible()
  await page.keyboard.press('ArrowDown')
  await expect(drawer.getByRole('heading', { name: '阀门 3', exact: true })).toBeVisible()
  await page.locator('.ag-pinned-left-cols-container [row-id="3"] [col-id="material_name"]').click()
  await page.locator('.ag-pinned-left-cols-container [row-id="4"] [col-id="material_name"]').click()
  await expect(drawer.getByRole('heading', { name: '阀门 4', exact: true })).toBeVisible()
  await page.waitForTimeout(900)
  await expect(drawer.getByRole('heading', { name: '阀门 4', exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '关闭采购明细' }).click()
  detailFailure = true
  await page.getByRole('button', { name: '明细', exact: true }).first().click()
  await expect(drawer.getByRole('alert')).toBeVisible()
  detailFailure = false
  await drawer.getByRole('button', { name: '重试' }).click()
  await expect(drawer.getByRole('button', { name: 'ORDER-12', exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '关闭采购明细' }).click()
  await page.getByRole('textbox', { name: '搜索采购明细' }).fill('CGSQ-1')
  await page.getByRole('button',{name:'添加条件',exact:true}).click()
  await page.locator('.pms-report-conditions').getByRole('button',{name:'添加条件',exact:true}).click()
  await page.getByRole('textbox',{name:'条件1值',exact:true}).fill('阀门')
  await page.getByRole('button',{name:'应用条件',exact:true}).click()
  const beforeSubmit=requests.length
  await page.waitForTimeout(400)
  assert.equal(requests.length,beforeSubmit,'修改条件不得自动查询')
  await page.getByRole('button',{name:'查询',exact:true}).click()
  await expect.poll(() => requests.at(-1).keyword).toBe('CGSQ-1')
  assert.deepEqual(JSON.parse(requests.at(-1).filters),[{field:'material_name',operator:'contains',value:'阀门',valueEnd:null}])
  await expect(page.locator('.ag-center-cols-container [role="row"]')).toHaveCount(1)
  await page.getByRole('button', { name: '保存查询方案', exact: true }).click()
  await page.getByRole('textbox', { name: '方案名称' }).fill('申请跟踪')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await page.evaluate(() => {
    const key = Object.keys(localStorage).find(key => key.startsWith('pms:purchase-report:v1:'))
    const saved = JSON.parse(localStorage.getItem(key))
    saved.plans[0].filters.progress = 'ordering'
    localStorage.setItem(key, JSON.stringify(saved))
  })
  await page.reload()
  const beforeRestore=requests.length
  await page.locator('.pms-report-query-plan-select').click()
  await page.getByRole('option', { name: '申请跟踪', exact: true }).click()
  await expect(page.getByRole('textbox', { name: '搜索采购明细' })).toHaveValue('CGSQ-1')
  assert.equal(requests.length,beforeRestore,'恢复方案不得查询')
  await page.getByRole('button',{name:'查询',exact:true}).click()
  await expect.poll(() => requests.at(-1).page).toBe('1')
  await expect.poll(() => JSON.parse(requests.at(-1).filters).some(c => c.field === 'progress' && c.value === 'ordering')).toBe(true)
  await expect(page.locator('.ag-center-cols-container [role="row"]')).toHaveCount(1)
  await page.getByRole('button', { name: '打开采购进度列设置' }).click()
  await expect(page.getByRole('button', { name: '保存', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByRole('button', { name: '保存', exact: true })).toBeHidden()
  for (const viewport of [{ width: 1366, height: 768 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    if (viewport.width === 390) {
      const gridWidth = await page.locator('.purchase-page .pms-ag-grid').evaluate(el => el.getBoundingClientRect().width)
      assert.ok(gridWidth >= 700, 'Narrow report must scroll a readable grid, not overlap fixed columns')
    }
    await page.screenshot({ path: resolve(root, `.runtime/purchase-formal-${viewport.width}.png`) })
    await page.getByRole('button', { name: '明细', exact: true }).first().click()
    await expect(drawer).toBeVisible()
    const box = await drawer.boundingBox()
    assert.ok(box.x >= 0 && box.x + box.width <= viewport.width)
    await page.screenshot({ path: resolve(root, `.runtime/purchase-formal-detail-${viewport.width}.png`) })
    await drawer.getByRole('button', { name: '关闭采购明细' }).click()
  }
  canExport = false
  await page.reload()
  await expect(page.getByRole('button', { name: '导出', exact: true })).toHaveCount(0)
  listFailure = true
  await page.getByRole('button', { name: '查询', exact:true }).click()
  await expect(page.getByRole('alert').filter({ hasText: '采购数据加载失败' })).toBeVisible()
  assert.deepEqual(errors, [])
  console.log('PASS: formal report layout, selection linkage, races, error/retry, saved query, columns, responsive, export permission')
} finally { await browser.close() }
