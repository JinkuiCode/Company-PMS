// Isolated real-component acceptance; API fixtures never access ERP.
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'

const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><div id="app"></div><script type="module" src="/tests/fixtures/stock-detail-entry.ts"></script><style>html,body,#app{margin:0;height:100%;box-sizing:border-box}#app{padding:16px;display:flex;flex-direction:column}</style></html>`
const server = await createServer({
  server: { host: '127.0.0.1', port: 5190, strictPort: true },
  plugins: [{ name: 'stock-detail-test-entry', configureServer(vite) {
    vite.middlewares.use((req, res, next) => {
      if (req.url !== '/stock-detail-test') return next()
      res.setHeader('Content-Type', 'text/html'); res.end(html)
    })
  } }],
})
let browser
try {
  await server.listen()
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  const errors = []
  page.on('pageerror', error => { if (errors.length < 20) errors.push(error.message) })
  page.on('console', message => { if (message.type() === 'error') console.error(message.text()) })
  const fields = [
    ['material_code', '物料编码', 140], ['material_name', '物料名称', 100], ['bill_date', '日期', 110],
    ['bill_name', '单据名称', 130], ['bill_no', '单据编号', 155], ['bill_seq', '行号', 65],
    ['stock_name', '仓库名称', 115], ['stock_status_name', '库存状态', 95], ['owner_type_name', '货主类型', 100],
    ['owner_name', '货主', 210], ['unit_name', '库存单位', 80], ['opening_qty', '期初', 95],
    ['income_qty', '收入', 95], ['issue_qty', '发出', 95], ['balance_qty', '结存', 95],
  ].map(([key, label, width]) => ({ key, label, width, type: key.endsWith('_qty') ? 'decimal' : 'text' }))
  let calls = 0
  const requests = []
  const exports = []
  await page.route('**/api/report-exports**', async route => {
    if (route.request().method() === 'POST') {
      exports.push(route.request().postDataJSON())
      await route.fulfill({ json: { id: 'a'.repeat(32), report: 'stock-detail', status: 'queued', processed: 0, created_at: '2026-09-23T10:00:00' } })
    } else await route.fulfill({ json: [] })
  })
  await page.route('**/api/reports/stock-detail**', async route => {
    const url = new URL(route.request().url())
    let data
    if (url.pathname.endsWith('/metadata')) data = { fields, organizations: [{ value: 1, label: '8吋半导体' }, { value: 2, label: 'Single' }] }
    else if (url.pathname.endsWith('/options')) data = { items: url.searchParams.get('field') === 'material'
      ? [{ value: '180102020045', code: '180102020045', label: 'PFA管' }]
      : [{ value: 4397043, code: 'CK01', label: '亚电-研发仓' }], has_more: false }
    else {
      calls++; requests.push({ ...Object.fromEntries(url.searchParams), organization_ids: url.searchParams.getAll('organization_ids') })
      const current = Number(url.searchParams.get('page')), size = Number(url.searchParams.get('page_size'))
      const items = Array.from({ length: Math.max(0, Math.min(size, 70 - (current - 1) * size)) }, (_, offset) => {
        const id = (current - 1) * size + offset + 1
        return { row_id: `m:${id}`, row_kind: 'movement', material_code: '180102020045', material_name: 'PFA管',
          bill_no: `DOC${id}`, bill_seq: id, bill_name: '直接调拨单', bill_date: '2026-09-03',
          stock_name: '亚电-研发仓', stock_status_name: '可用', owner_type_name: '业务组织', owner_name: '江苏亚电科技股份有限公司',
          unit_name: '米', opening_qty: null, income_qty: '6', issue_qty: '0', balance_qty: String(id * 6) }
      })
      data = { items, openings: [{ row_id: 'opening:0', row_kind: 'opening', material_code: '180102020045', material_name: 'PFA管', bill_name: '期初', opening_qty: '0', balance_qty: '0' }], total: 70, queried_at: '2026-09-23T10:00:00Z',
        summary: { material_code: '180102020045', material_name: 'PFA管', unit_name: '米', opening_qty: '0', income_qty: '420', issue_qty: '0', balance_qty: '420' } }
    }
    await route.fulfill({ json: data })
  })
  await page.goto('http://127.0.0.1:5190/stock-detail-test')
  const query = page.getByRole('button', { name: '查询', exact: true })
  await query.waitFor({ timeout: 15000 }).catch(error => { console.error(errors); throw error })
  assert.equal(await query.isDisabled(), true, 'empty material must disable query')
  await page.getByRole('textbox', { name: '物料（必填）', exact: true }).fill('　 ')
  assert.equal(await query.isDisabled(), true, 'whitespace material must disable query')
  await page.getByRole('textbox', { name: '物料（必填）', exact: true }).press('Enter')
  assert.equal(calls, 0)
  await page.getByRole('textbox', { name: '物料（必填）', exact: true }).fill('180102020045')
  assert.equal(await query.isEnabled(), true)
  await page.locator('.pms-form-control[aria-label="库存组织"]').click()
  await page.getByRole('option', { name: '8吋半导体', exact: true }).click()
  await page.getByRole('option', { name: 'Single', exact: true }).click()
  await page.keyboard.press('Escape')
  await page.locator('.pms-form-control[aria-label="仓库"]').click()
  await page.getByRole('option', { name: '亚电-研发仓', exact: true }).click()
  await query.click()
  await page.getByRole('button', { name: '查看单据 DOC1', exact: true }).waitFor()
  assert.ok((await page.getByLabel('完整查询数量汇总').innerText()).includes('420'))
  await page.getByRole('button', { name: '导出当前筛选', exact: true }).click()
  await page.waitForFunction(() => !!document.querySelector('.report-export-heading'))
  assert.equal(exports.length, 1)
  assert.equal(exports[0].report, 'stock-detail')
  assert.equal(exports[0].parameters.material, '180102020045')
  assert.deepEqual(exports[0].parameters.organization_ids, [1, 2])
  assert.deepEqual(requests.at(-1).organization_ids, ['1', '2'])
  assert.equal(exports[0].columns.length, 15)
  await page.getByRole('button', { name: '保存查询方案', exact: true }).hover()
  await page.keyboard.press('Escape')
  assert.equal(requests.at(-1).page_size, '50')
  assert.equal(requests.at(-1).stock_id, '4397043')
  assert.equal(await page.getByRole('dialog').count(), 0)
  await page.getByRole('button', { name: '查看单据 DOC1', exact: true }).click()
  await page.getByRole('dialog').getByText('DOC1', { exact: true }).waitFor()
  await page.locator('.ag-center-cols-container [row-id="m:2"] [col-id="material_name"]').click()
  await page.getByRole('dialog').getByText('DOC2', { exact: true }).waitFor()
  await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click()
  await page.getByRole('button', { name: '保存查询方案', exact: true }).click()
  await page.getByRole('textbox', { name: '方案名称', exact: true }).fill('研发仓查询')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('pms:stock-detail:v1:1')).plans[0].filters.stock_id), 4397043)
  await page.locator('.pagination-center').getByRole('button', { name: '2', exact: true }).click()
  await page.getByRole('button', { name: '查看单据 DOC51', exact: true }).waitFor()
  assert.equal(requests.at(-1).page, '2')
  await page.getByRole('textbox', { name: '物料（必填）', exact: true }).fill('different')
  await page.locator('.pms-form-control[aria-label="查询方案"]').click()
  await page.getByRole('option', { name: '当前查询', exact: true }).click()
  await page.locator('.pms-form-control[aria-label="查询方案"]').click()
  await page.getByRole('option', { name: '研发仓查询', exact: true }).click()
  await page.getByRole('button', { name: '查看单据 DOC1', exact: true }).waitFor()
  assert.equal(requests.at(-1).material, '180102020045')
  assert.equal(requests.at(-1).stock_id, '4397043')
  assert.equal(requests.at(-1).page, '1')
  assert.deepEqual(requests.at(-1).organization_ids, ['1', '2'])
  await page.getByRole('button', { name: '打开物料收发明细列设置', exact: true }).click()
  await page.getByRole('spinbutton', { name: '物料名称列宽', exact: true }).fill('180')
  await page.getByRole('spinbutton', { name: '物料名称列宽', exact: true }).press('Tab')
  await page.locator('.column-picker-panel').getByRole('button', { name: '保存', exact: true }).click()
  await page.waitForFunction(() => JSON.parse(localStorage.getItem('pms:stock-detail:v1:1')).columns.find(c => c.colId === 'material_name')?.width === 180)
  await mkdir('../.runtime/stock-detail-browser', { recursive: true })
  for (const width of [1600, 1366, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.waitForTimeout(250)
    await page.screenshot({ path: `../.runtime/stock-detail-browser/${width}.png` })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `page overflow at ${width}`)
  }
  assert.deepEqual(errors, [])
  const callsBeforeReset = calls
  await page.getByRole('button', { name: '重置', exact: true }).click({ timeout: 3000 })
  assert.equal(await page.getByRole('textbox', { name: '物料（必填）', exact: true }).inputValue(), '')
  assert.equal(await page.getByRole('button', { name: '查看单据 DOC1', exact: true }).count(), 0)
  assert.equal(calls, callsBeforeReset, 'reset must not query without a material')
  assert.equal(await query.isDisabled(), true)
  console.log('Stock detail browser: required material, warehouse selection, 50-row paging, detail switching, plan restore, column width persistence and responsive widths passed (mock API only).')
} finally {
  await browser?.close()
  await server.close()
}
