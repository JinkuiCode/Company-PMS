import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const base = process.env.PMS_GOVERNANCE_URL || 'http://127.0.0.1:5198'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-test-only'))
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.origin !== base) return route.abort()
    if (!url.pathname.startsWith('/api/')) return route.continue()
    let json = []
    if (url.pathname === '/api/auth/me') json = { id: 1, username: 'fixture', permissions: ['system:operation-log:view'] }
    if (url.pathname === '/api/operation-logs') json = { query_version: 2, total: 2, actions: [{ value: 'maintain', label: '档案维护' }], modules: [{ value: '项目档案', label: '项目档案' }], items: [1, 2].map(id => ({
      id, module: '项目档案', action: 'maintain', operator_name: `维护人员${id}`, entity_name: `项目${id}`,
      created_at: '2026-10-15T10:00:00', status: 'success', summary: `档案修订${id}`, request_path: '/safe/path',
      diff_items: [{ field_key: 'customer', field_label: '客户', before_display: '原客户', after_display: `新客户${id}` }],
    })) }
    return route.fulfill({ json })
  })
  await page.goto(`${base}/system/operation-log`)
  await page.getByRole('button', { name: '详情', exact: true }).first().click()
  const detail = page.getByRole('dialog', { name: '操作详情', exact: true })
  await expect(detail).toContainText('新客户1')
  assert.ok((await detail.boundingBox()).x > 600)
  await expect(detail.getByText('/safe/path', { exact: false })).not.toBeVisible()
  await page.getByRole('row').filter({ hasText: '项目2' }).click()
  await expect(detail).toContainText('新客户2')
  await detail.getByText('技术信息', { exact: true }).click()
  await expect(detail.getByText('/safe/path', { exact: false })).toBeVisible()
  await page.screenshot({ path: '../outputs/development-governance-20261015-audit.png' })
  await detail.press('Escape')
  await expect(detail).toHaveCount(0)
  assert.deepEqual(errors, [])
  console.log('PASS: 审计右侧详情、单据切换、技术信息收起、Esc关闭')
} finally { await browser.close() }
