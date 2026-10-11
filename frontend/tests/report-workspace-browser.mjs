// Real Vue/AG Grid integration, with isolated API fixtures and browser storage.
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { chromium, expect } from '@playwright/test'

const server = await createServer({ server: { host: '127.0.0.1', port: 0 } })
let browser, page
const organizations = [{ value: 2, label: '研发' }, { value: 3, label: '生产' }]
const field = (key, label, value_type = 'text') => ({ key, label, value_type, type: value_type, width: 140, group: '基本信息' })
const query = (field, label, type = 'text') => ({ field, label, type })
const purchase = {
  organizations, fields: [field('project_code', '项目编码'), field('project_name', '项目名称'), field('product_line_name', '产品线'), field('bill_no', '单据编号'), field('progress', '采购进度')],
  overview_fields: [field('product_line_name', '产品线'), field('project_code', '项目编码'), field('project_name', '项目名称'), field('completion_rate', '完成率', 'number'), field('total_lines', '申请行数', 'number'), field('review_lines', '待核对行数', 'number')],
  query_fields: [query('application_date', '申请日期', 'date'), { ...query('progress', '采购进度', 'enum'), options: [{ value: 'review', label: '待核对' }, { value: 'complete', label: '已完成' }] }],
  column_filter_fields: [query('bill_no', '单据编号')], overview_column_filter_fields: [query('completion_rate', '完成率', 'number')],
  document_status_labels: { C: '已审核' }, progress_labels: { review: '待核对', complete: '已完成' }, start_date: '2026-01-01',
}
const inventory = { organizations, fields: [field('MaterialName', '物料名称'), field('Stock', '仓库'), field('Qty', '数量', 'number')], query_fields: [query('MaterialName', '物料名称')], column_filter_fields: [query('MaterialName', '物料名称'), query('Stock', '仓库')] }
const stock = { organizations, fields: [field('material_code', '物料编码'), field('bill_no', '单据编号'), field('stock_name', '仓库名称'), field('income_qty', '收入', 'number')], query_fields: [query('bill_no', '单据编号')], column_filter_fields: [query('bill_no', '单据编号')] }
const calls = { inventory: [], overview: [], purchase: [], stock: [], candidates: [], exports: [] }, errors = []
try {
  await server.listen()
  const base = `http://127.0.0.1:${server.httpServer.address().port}`
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'isolated-report-fixture')
    localStorage.setItem('pms:purchase-overview:v1:991:plans', JSON.stringify([{ version: 1, name: '旧总表', state: { keyword: 'BASE', organization_ids: [2], dates: [], conditions: [], overviewStatus: 'review', pageSize: 100, sort: { sort: 'completion_rate', direction: 'desc' } } }]))
    localStorage.setItem('pms:purchase-report:v1:991', JSON.stringify({ plans: [{ name: '旧明细', filters: { keyword: 'DETAIL', organization_ids: [2], progress: 'review' }, dates: [], conditions: [], pageSize: 100, scope: { project_code: 'P1', organization_id: 2, product_line_name: '研发' } }] }))
    localStorage.setItem('pms:inventory-report:v1:991:plans:v1', JSON.stringify([{ version: 1, name: '旧库存', state: { draft: { keyword: 'BASE', organization_id: 2, stock: '', conditions: [] }, pageSize: 100 } }, { version: 1, name: '同名优先', state: { draft: { keyword: 'OLD', conditions: [] } } }]))
    localStorage.setItem('pms:query-workspace:v2:991:report-inventory', JSON.stringify([{ version: 2, name: '同名优先', isDefault: false, definitions: [{ field: 'keyword', shown: true, operator: 'contains', value: 'V2', valueEnd: null, schemaVersion: 2 }], preferences: {} }]))
    localStorage.setItem('pms:stock-detail:v1:991', JSON.stringify({ plans: [{ name: '旧收发', filters: { material: 'MAT', organization_ids: [2], stock_id: 10, dates: ['2026-10-01', '2026-10-11'], conditions: [] }, size: 15 }] }))
  })
  await page.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    const params = { ...Object.fromEntries(url.searchParams), organization_ids: url.searchParams.getAll('organization_ids') }
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 991, username: 'report-fixture', real_name: '报表测试', permissions: ['report:purchase:view', 'report:purchase:list', 'report:purchase:export', 'report:inventory:view', 'report:inventory:list', 'report:inventory:export', 'report:stock-detail:view', 'report:stock-detail:list', 'report:stock-detail:export'], role_codes: [], data_scope: 4 } })
    if (path === '/api/my-menus') return route.fulfill({ json: [] })
    if (path.endsWith('/metadata')) return route.fulfill({ json: path.includes('inventory') ? inventory : path.includes('stock-detail') ? stock : purchase })
    if (path.endsWith('/column-options')) { calls.candidates.push(params); return route.fulfill({ json: { items: [{ value: 'PAGE', label: 'PAGE', count: 50 }, { value: 'OFF-PAGE', label: 'OFF-PAGE', count: 1 }], total: 2, has_more: false } }) }
    if (path.endsWith('/reference-options')) return route.fulfill({ json: { items: [{ value: 20, code: 'P1', label: '测试项目', product_line_name: '研发' }], total: 1, has_more: false } })
    if (path.endsWith('/options')) return route.fulfill({ json: { items: [{ value: 10, code: 'W1', label: '研发仓' }], total: 1, has_more: false } })
    if (path === '/api/reports/inventory') {
      calls.inventory.push(params)
      const filtered = JSON.parse(params.column_filters || '[]').length > 0
      return route.fulfill({ json: { items: [{ FID: '1', MaterialName: filtered ? 'OFF-PAGE' : 'PAGE', Stock: '研发仓', Qty: 10 }], total: filtered ? 1 : 1500, queried_at: '2026-10-11T00:00:00Z' } })
    }
    if (path === '/api/reports/purchase/overview') { calls.overview.push(params); return route.fulfill({ json: { items: [{ id: '2:P1', organization_id: 2, project_code: 'P1', project_name: '测试项目', product_line_name: '研发', completion_rate: 40, total_lines: 10, review_lines: 1 }], total: 1, total_lines: 10, complete_lines: 4, review_lines: 1, queried_at: '2026-10-11T00:00:00Z' } }) }
    if (path === '/api/reports/purchase') { calls.purchase.push(params); return route.fulfill({ json: { items: [{ id: 1, project_code: 'P1', project_name: '测试项目', product_line_name: '研发', bill_no: 'DOC1', progress: 'review', progress_label: '待核对', document_status: 'C' }], total: 1, queried_at: '2026-10-11T00:00:00Z' } }) }
    if (path === '/api/reports/stock-detail') { calls.stock.push(params); return route.fulfill({ json: { items: [{ row_id: 'm:1', row_kind: 'movement', material_code: 'MAT', bill_no: 'DOC1', stock_name: '研发仓', income_qty: '2' }], openings: [{ row_id: 'o:1', row_kind: 'opening', material_code: 'MAT', bill_no: '', income_qty: '' }], total: 1, summary: null, queried_at: '2026-10-11T00:00:00Z' } }) }
    if (path.startsWith('/api/report-exports') && request.method() === 'POST') { calls.exports.push(request.postDataJSON()); return route.fulfill({ json: { id: 'a'.repeat(32), status: 'queued', report: 'inventory', processed: 0 } }) }
    return route.fulfill({ json: [] })
  })
  const selectScheme = async (surface, name) => {
    await surface.locator('.pms-query-scheme-select .el-select__wrapper').click()
    await page.getByRole('option', { name, exact: true }).click()
  }
  const keywordInput = surface => surface.locator('.pms-query-workspace [data-field="keyword"] input').first()
  await page.goto(`${base}/reports/inventory`)
  let surface = page.locator('.pms-report-query-surface')
  await expect(surface.locator('.pms-query-workspace [data-field="keyword"]')).toBeVisible()
  assert.equal(calls.inventory.length, 0)
  await selectScheme(surface, '同名优先')
  await expect(keywordInput(surface)).toHaveValue('V2')
  await selectScheme(surface, '旧库存')
  await expect(keywordInput(surface)).toHaveValue('BASE')
  assert.equal(calls.inventory.length, 0, 'loading a legacy scheme must not query')
  await surface.getByRole('button', { name: '查询', exact: true }).click()
  await expect.poll(() => calls.inventory.length).toBe(1)
  assert.equal(calls.inventory[0].organization_id, '2')
  assert.equal(calls.inventory[0].page_size, '100')
  await keywordInput(surface).fill('UNSUBMITTED')
  await surface.getByRole('button', { name: '物料名称列筛选', exact: true }).click()
  const panel = page.getByRole('dialog', { name: '物料名称列筛选面板', exact: true })
  await expect(panel.getByText('OFF-PAGE', { exact: true })).toBeVisible()
  assert.equal(JSON.parse(calls.candidates.at(-1).parameters).keyword, 'BASE')
  await panel.getByRole('checkbox', { name: 'PAGE 50', exact: true }).uncheck()
  await panel.getByRole('button', { name: '应用', exact: true }).click()
  await expect.poll(() => calls.inventory.length).toBe(2)
  assert.equal(calls.inventory.at(-1).keyword, 'BASE')
  assert.deepEqual(JSON.parse(calls.inventory.at(-1).column_filters)[0].values, ['OFF-PAGE'])
  await expect(surface.locator('[col-id="MaterialName"][role="gridcell"]')).toContainText('OFF-PAGE')
  await expect(surface.locator('[col-id="MaterialName"][role="gridcell"]')).toHaveClass(/pms-query-filtered-column/)
  await surface.getByRole('button', { name: '重置', exact: true }).click()
  await expect(surface.locator('[col-id="MaterialName"][role="gridcell"]')).not.toHaveClass(/pms-query-filtered-column/)
  assert.equal(calls.inventory.length, 2, 'reset only changes drafts')
  assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('pms:inventory-report:v1:991:plans:v1')).length), 2)

  await page.goto(`${base}/reports/purchase-progress`)
  surface = page.locator('.purchase-overview-page')
  await expect(keywordInput(surface)).toBeVisible()
  await selectScheme(surface, '旧总表')
  await surface.getByRole('button', { name: '查询', exact: true }).click()
  await expect.poll(() => calls.overview.length).toBe(1)
  assert.equal(calls.overview[0].overview_status, 'review')
  assert.equal(calls.overview[0].sort, 'completion_rate')
  assert.equal(calls.overview[0].page_size, '100')
  await keywordInput(surface).fill('UNSUBMITTED')
  await surface.getByRole('button', { name: '明细', exact: true }).click()
  await expect.poll(() => calls.purchase.length).toBe(1)
  assert.equal(calls.purchase[0].keyword, 'BASE')
  assert.equal(calls.purchase[0].project_code, 'P1')
  assert.deepEqual(calls.purchase[0].organization_ids, ['2'])
  const detail = page.locator('.purchase-detail-view')
  await selectScheme(detail, '旧明细')
  await detail.getByRole('button', { name: '查询', exact: true }).click()
  await expect.poll(() => calls.purchase.length).toBe(2)
  assert.equal(calls.purchase.at(-1).keyword, 'DETAIL')
  assert.equal(calls.purchase.at(-1).project_code, 'P1')
  assert.equal(calls.purchase.at(-1).page_size, '100')
  assert.ok(JSON.parse(calls.purchase.at(-1).filters).some(c => c.field === 'progress' && c.value === 'review'))
  await detail.getByRole('button', { name: '总进度', exact: true }).click()
  await expect(keywordInput(surface)).toHaveValue('UNSUBMITTED')
  assert.equal(calls.overview.length, 1)
  assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('pms:purchase-report:v1:991')).plans[0].name), '旧明细')

  await page.goto(`${base}/reports/stock-detail`)
  surface = page.locator('.pms-report-query-surface')
  await expect(surface.locator('[data-field="material"]')).toBeVisible()
  await expect(surface.getByRole('button', { name: '查询', exact: true })).toBeDisabled()
  await surface.locator('[data-field="material"] input').fill('MAT')
  await expect(surface.getByRole('button', { name: '查询', exact: true })).toBeDisabled()
  await selectScheme(surface, '旧收发')
  assert.equal(calls.stock.length, 0)
  assert.equal(await surface.locator('[data-field="stock_id"] input:not([readonly])').count(), 0, 'warehouse reference is selection only')
  await surface.getByRole('button', { name: '查询', exact: true }).click()
  await expect.poll(() => calls.stock.length).toBe(1)
  assert.equal(calls.stock[0].material, 'MAT')
  assert.equal(calls.stock[0].stock_id, '10')
  assert.equal(calls.stock[0].page_size, '15')
  assert.deepEqual(calls.stock[0].organization_ids, ['2'])
  await expect(surface.locator('.ag-floating-top [row-id="o:1"]').first()).toBeVisible()
  assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('pms:stock-detail:v1:991')).plans[0].name), '旧收发')
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `/private/tmp/pms-report-workspace-${width}.png` })
  }
  assert.deepEqual(errors, [])
  console.log('PASS shared report workspace: legacy read-only/v2 priority, server-wide funnel, submitted snapshots, total/detail, mandatory stock scope, responsive')
} catch (error) {
  console.error('Report fixture failure:', errors, await page?.locator('body').innerText())
  throw error
} finally {
  await browser?.close()
  await server.close()
}
