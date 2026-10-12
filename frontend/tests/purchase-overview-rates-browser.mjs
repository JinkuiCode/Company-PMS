import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { createServer } from 'vite'
import { chromium, expect } from '@playwright/test'

const root = resolve(import.meta.dirname, '../..')
const metadata = JSON.parse(execFileSync('/Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3', ['-c', 'import json; from app.services.purchase_fields import *; from app.services.report_filters import query_fields; print(json.dumps(dict(fields=report_fields(),overview_fields=overview_fields(),query_fields=query_fields("purchase"),overview_query_fields=query_fields("purchase-overview"),overview_column_filter_fields=query_fields("purchase-overview"),progress_labels=PROGRESS_LABELS,document_status_labels=DOCUMENT_STATUSES,organizations=[dict(value=499413,label="12吋Bench")],start_date="2026-01-01")))'], { cwd: resolve(root, 'backend'), env: { ...process.env, PYTHONPATH: resolve(root, 'backend/.venv-deps312') }, encoding: 'utf8' }))
metadata.overview_query_fields = [...new Map([...metadata.query_fields, ...metadata.overview_query_fields].map(field => [field.field, field])).values()]
const server = await createServer({ server: { host: '127.0.0.1', port: 0 } })
let browser
const queries = [], exports = [], errors = []
try {
  await server.listen()
  const base = `http://127.0.0.1:${server.httpServer.address().port}`
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', message => { if (message.type() === 'error') console.error(message.text()) })
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'isolated-rates-test')
    localStorage.setItem('pms:purchase-overview:v1:996', JSON.stringify({ visible: ['project_code', 'completion_rate', 'total_lines'], columns: [{ colId: 'project_code', width: 144, pinned: 'left' }, { colId: 'completion_rate', width: 181 }, { colId: 'total_lines' }, { colId: 'product_line_name', width: 137, hide: true, pinned: 'right' }] }))
    localStorage.setItem('pms:query-workspace:v2:996:report-purchase-overview', JSON.stringify([{ version: 2, name: '旧指标方案', isDefault: false, definitions: [{ field: 'project_code', shown: true, operator: 'equals', value: 'A-202503', valueEnd: null, schemaVersion: 2 }], preferences: { visible: ['project_code', 'completion_rate', 'total_lines'], columns: [{ colId: 'project_code', width: 144, pinned: 'left' }, { colId: 'completion_rate', width: 181 }, { colId: 'total_lines' }, { colId: 'product_line_name', width: 137, hide: true, pinned: 'right' }] } }]))
  })
  await page.route('**/api/**', route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    if (!path.startsWith('/api/')) return route.continue()
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 996, username: 'fixture', real_name: '指标测试', permissions: ['report:purchase:view', 'report:purchase:export'], role_codes: [], data_scope: 4 } })
    if (path.endsWith('/metadata')) return route.fulfill({ json: metadata })
    if (path === '/api/reports/purchase/overview') {
      queries.push(Object.fromEntries(url.searchParams))
      return route.fulfill({ json: { items: [{ id: '499413:A-202503', organization_id: 499413, product_line_name: '12吋Bench', project_code: 'A-202503', project_name: '', total_lines: 216, completion_rate: '90.740740740740', conversion_rate: '96.296296296296', not_ordered_lines: 7, ordering_lines: 1, receiving_lines: 12, complete_lines: 196, review_lines: 0 }], total: 1, total_lines: 216, complete_lines: 196, review_lines: 0, queried_at: '2026-10-12T00:00:00Z' } })
    }
    if (path.endsWith('/column-options')) return route.fulfill({ json: { items: [{ value: '96.296296296296', label: '96.296296296296', count: 1 }], total: 1, has_more: false } })
    if (path.startsWith('/api/report-exports') && request.method() === 'POST') {
      exports.push(request.postDataJSON())
      return route.fulfill({ json: { id: 'b'.repeat(32), status: 'success', report: 'purchase', processed: 1, created_at: '2026-10-12T00:00:00' } })
    }
    return route.fulfill({ json: [] })
  })
  await page.goto(`${base}/reports/purchase-progress`)
  const summary = page.locator('.purchase-overview-page')
  try { await expect(summary.getByRole('button', { name: '查询', exact: true })).toBeEnabled() }
  catch (error) { console.error('UI_DIAGNOSTIC', page.url(), errors, await page.locator('body').innerText()); throw error }
  assert.equal(queries.length, 0)
  await summary.getByRole('button', { name: '查询', exact: true }).click()
  await expect(summary.locator('[col-id="completion_rate"][role="gridcell"]')).toContainText('90.7%')
  await expect(summary.locator('[col-id="conversion_rate"][role="gridcell"]')).toContainText('96.3%')
  await expect(summary.locator('[col-id="completion_rate"][role="columnheader"]')).toContainText('申请行入库率')
  await expect(summary.locator('[col-id="conversion_rate"][role="columnheader"]')).toContainText('申请行转单率')
  assert.equal(await summary.locator('.ag-pinned-left-header .ag-header-cell').first().getAttribute('col-id'), 'product_line_name')
  assert.equal(Math.round(await summary.locator('[col-id="product_line_name"][role="columnheader"]').evaluate(el => el.getBoundingClientRect().width)), 137)
  await summary.locator('.pms-query-scheme-select .el-select__wrapper').click()
  await page.getByRole('option', { name: '旧指标方案', exact: true }).click()
  await summary.getByRole('button', { name: '查询', exact: true }).click()
  await expect.poll(() => queries.length).toBe(2)
  assert.ok(JSON.parse(queries.at(-1).filters).some(c => c.field === 'project_code' && c.value === 'A-202503'))
  await expect(summary.locator('[col-id="conversion_rate"][role="gridcell"]')).toContainText('96.3%')
  assert.equal(await summary.locator('.ag-pinned-left-header .ag-header-cell').first().getAttribute('col-id'), 'product_line_name')
  await summary.getByRole('button', { name: '申请行转单率列筛选', exact: true }).click()
  const panel = page.getByRole('dialog', { name: '申请行转单率列筛选面板', exact: true })
  await panel.getByRole('button', { name: '降序', exact: true }).click()
  await expect.poll(() => queries.at(-1).sort).toBe('conversion_rate')
  assert.equal(queries.at(-1).direction, 'desc')
  await page.keyboard.press('Escape')
  await summary.getByRole('button', { name: '导出数据', exact: true }).click()
  await expect.poll(() => exports.length).toBe(1)
  assert.equal(exports[0].parameters.view, 'overview')
  assert.equal(exports[0].parameters.sort, 'conversion_rate')
  assert.equal(exports[0].columns[0], 'product_line_name')
  assert.ok(exports[0].columns.includes('completion_rate') && exports[0].columns.includes('conversion_rate'))
  await summary.getByRole('button', { name: '导出任务', exact: true }).click()
  await expect(page.getByText('暂无导出任务', { exact: true })).toBeHidden()
  await summary.locator('.pms-query-scheme-select .el-select__wrapper').click()
  await page.getByRole('option', { name: '旧指标方案', exact: true }).click()
  await summary.getByRole('button', { name: '查询', exact: true }).click()
  await expect.poll(() => queries.at(-1).sort).toBe('project_code')
  await page.reload()
  await expect(summary.getByRole('button', { name: '查询', exact: true })).toBeEnabled()
  await summary.getByRole('button', { name: '查询', exact: true }).click()
  await expect.poll(() => queries.at(-1).sort).toBe('project_code')
  const folder = resolve(root, 'outputs/purchase-overview-rates-20261012')
  mkdirSync(folder, { recursive: true })
  for (const width of [1440, 1182, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.evaluate(() => document.fonts.ready)
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
    await page.screenshot({ path: resolve(folder, `overview-${width}.png`) })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
  }
  assert.deepEqual(errors, [])
  console.log('PASS: migrated first product line/width, both rates, server sort, export scope/columns, responsive')
} finally {
  await browser?.close()
  await server.close()
}
