import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createServer } from 'vite'
import { chromium, expect } from '@playwright/test'

const root = resolve(import.meta.dirname, '../..')
const metadata = JSON.parse(execFileSync(resolve(root, 'backend/.venv-security312/bin/python'), ['-c',
  'import json; from app.services.purchase_fields import *; from app.services.report_filters import query_fields,filter_fields; print(json.dumps(dict(fields=report_fields(),overview_fields=overview_fields(),query_fields=query_fields("purchase"),filter_fields=filter_fields("purchase"),overview_query_fields=query_fields("purchase-overview"),progress_labels=PROGRESS_LABELS,document_status_labels=DOCUMENT_STATUSES,organizations=[dict(value=100,label="8吋Bench")],start_date="2026-01-01")))'],
  { cwd: resolve(root, 'backend'), env: { ...process.env, PYTHONPATH: '.' }, encoding: 'utf8' }))
metadata.overview_query_fields = [...new Map([...metadata.query_fields, ...metadata.overview_query_fields].map(f => [f.field, f])).values()]
const folder = resolve(root, 'outputs/purchase-population-20261019')
mkdirSync(folder, { recursive: true })
const server = await createServer({ server: { host: '127.0.0.1', port: 0 } })
let browser
const requests = [], errors = []
const schemeKey = 'pms:query-workspace:v2:997:report-purchase-overview'
try {
  await server.listen()
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') console.error('CONSOLE', message.text()) })
  page.on('requestfailed', request => console.error('REQUEST_FAILED', request.url(), request.failure()))
  await page.addInitScript(({ schemeKey }) => {
    localStorage.setItem('access_token', 'isolated-population-fixture')
    localStorage.setItem(schemeKey, JSON.stringify([{ version: 2, name: '旧状态方案', isDefault: true,
      definitions: [{ field: 'document_status', shown: true, operator: 'equals', value: 'C', valueEnd: null, schemaVersion: 2 }], preferences: {} }]))
  }, { schemeKey })
  await page.route('**/api/**', route => {
    const { pathname: path } = new URL(route.request().url())
    if (!path.startsWith('/api/')) return route.continue()
    if (path === '/api/auth/me') return route.fulfill({ json: { id: 997, username: 'fixture', real_name: '隔离验证', permissions: ['report:purchase:view', 'report:purchase:export'], role_codes: [], data_scope: 4 } })
    if (path.endsWith('/metadata')) return route.fulfill({ json: metadata })
    if (path === '/api/reports/purchase/overview' || path === '/api/reports/purchase') {
      requests.push(path)
      return route.fulfill({ json: { items: [], total: 0, queried_at: '2026-10-19T02:00:00Z' } })
    }
    return route.fulfill({ json: [] })
  })
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/reports/purchase-progress`)
  const summary = page.locator('.purchase-overview-page')
  try { await expect(summary.getByRole('alert')).toContainText('此方案包含已取消的字段') }
  catch (error) { console.error('UI_DIAGNOSTIC', page.url(), errors, await page.locator('body').innerText()); throw error }
  await expect(summary.getByRole('button', { name: '查询', exact: true })).toBeDisabled()
  assert.equal(requests.length, 0)
  assert.equal(JSON.parse(await page.evaluate(key => localStorage.getItem(key), schemeKey))[0].definitions[0].field, 'document_status')
  await page.screenshot({ path: resolve(folder, 'old-scheme-blocked.png') })
  await summary.getByRole('button', { name: '方案设置', exact: true }).click()
  const settings = page.getByRole('dialog', { name: '查询方案设置', exact: true })
  await expect(settings).toBeVisible()
  await expect(settings.locator('[data-field="document_status"]')).toHaveCount(0)
  await expect(settings.getByText('数据状态', { exact: true })).toHaveCount(0)
  await settings.getByRole('button', { name: '保存方案', exact: true }).click()
  await expect(summary.getByRole('button', { name: '查询', exact: true })).toBeEnabled()
  await summary.getByRole('button', { name: '查询', exact: true }).click()
  await expect.poll(() => requests.length).toBe(1)
  await summary.getByRole('button', { name: '说明', exact: true }).click()
  const guide = page.getByRole('dialog', { name: '采购进度查询说明', exact: true })
  await expect(guide.getByText(/仅统计已审核且业务终止为正常的采购申请明细/)).toBeVisible()
  await expect(guide.getByText(/数据状态已固定为已审核/)).toBeVisible()
  await expect(guide).toHaveCSS('opacity', '1')
  await page.screenshot({ path: resolve(folder, 'report-guide.png'), animations: 'disabled' })
  assert.ok(metadata.fields.some(f => f.key === 'document_status'), 'display column remains available')
  for (const fields of [metadata.query_fields, metadata.filter_fields, metadata.overview_query_fields])
    assert.ok(fields.every(f => f.field !== 'document_status'), 'status cannot be added as query condition')
  assert.deepEqual(errors, [])
  writeFileSync(resolve(folder, 'browser-verification.json'), JSON.stringify({ passed: true,
    isolated: true, assertions: ['status absent from query and scheme fields', 'old scheme blocked without mutation',
      'explicit resave enables query', 'display field retained', 'guide updated'], requests: requests.length, errors }, null, 2))
  console.log('PASS: fixed population metadata, cancelled condition guard/resave, display field and guide; isolated browser only')
} finally {
  await browser?.close()
  await server.close()
}
