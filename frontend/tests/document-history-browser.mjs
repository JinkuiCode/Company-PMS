import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import {choosePageSize} from './page-size-helper.mjs'
const base = process.env.PMS_GOVERNANCE_URL || 'http://127.0.0.1:5198'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 850 } })
  page.setDefaultTimeout(10000)
  let oldStarted, releaseOld
  const started = new Promise(resolve => { oldStarted = resolve })
  const held = new Promise(resolve => { releaseOld = resolve })
  let fail = false, deny = false
  const errors = [], requests = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-test-only'))
  const rows = [1, 2].map(id => ({ id, project_code: `ARCH-${id}`, project_name: `档案${id}`, is_enabled: 1,
    can_edit: false, change_mode: 'readonly', edit_reason: '当前仅查看', change_version: `${id}`.repeat(64), data_origin: 'offline_initial', erp_sync_policy: 'manual' }))
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (url.origin !== base) return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let json = []
    if (path === '/api/auth/me') json = { id: 1, username: 'fixture', permissions: ['project:archive:view'] }
    else if (path === '/api/product-lines/options') json = { options: [], label_map: {} }
    else if (path === '/api/projects/archives/fields') json = { items: ['project_code', 'project_name'].map(field_key => ({ field_key, visible: true, editable: false, list_available: true })) }
    else if (path === '/api/projects/archives/list') json = { total: 2, items: rows }
    else if (path.startsWith('/api/document-history/')) {
      const id = Number(path.split('/').at(-1)); requests.push(url.search)
      if (id === 1) { oldStarted(); await held }
      if (id === 2 && (fail || deny)) return route.fulfill({ status: deny ? 403 : 500, json: { detail: '隔离读取失败' } })
      json = { total: url.searchParams.get('action') ? 30 : 60, actions: [{ value: 'update', label: '编辑' }], items: [{ id: id*100+Number(url.searchParams.get('page') || 1), actor: `操作人${id}`,
        created_at: '2026-10-15T10:00:00', action: 'update', action_label: '编辑', status: 'success', status_label: '成功',
        source: '项目档案', summary: id === 1 ? '旧档案迟到响应' : `第二档案记录 第${url.searchParams.get('page') || 1}页`, diff_items: [] }] }
    }
    return route.fulfill({ json })
  })
  await page.goto(`${base}/project/archive`)
  await page.getByRole('button', { name: '查看', exact: true }).first().click()
  const drawer = page.getByRole('dialog', { name: '查看项目档案', exact: true })
  await expect(drawer.getByRole('tab', { name: '业务信息', exact: true })).toHaveAttribute('aria-selected', 'true')
  await drawer.getByRole('tab', { name: '操作记录', exact: true }).click()
  await started
  await page.getByRole('row').filter({ hasText: 'ARCH-2' }).click()
  await expect(drawer).toContainText('第二档案记录 第1页')
  releaseOld()
  await expect(drawer).not.toContainText('旧档案迟到响应')
  await expect(drawer.locator('.history-tools').getByText('全部操作', { exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '2', exact: true }).click()
  await expect(drawer).toContainText('第二档案记录 第2页')
  assert.ok(requests.some(query => query.includes('page=2')))
  fail = true
  await drawer.getByRole('button', { name: '1', exact: true }).click()
  await expect(drawer).toContainText('操作记录加载失败')
  await expect(drawer).not.toContainText('第二档案记录')
  fail = false
  await drawer.getByRole('button', { name: '重新加载', exact: true }).click()
  await expect(drawer).toContainText('第二档案记录 第1页')
  await choosePageSize(drawer,15)
  await drawer.getByRole('combobox', { name: '筛选操作类型', exact: true }).press('ArrowDown')
  await page.getByRole('option', { name: '编辑', exact: true }).click()
  await expect.poll(() => requests.some(query => query.includes('page_size=15') && query.includes('action=update'))).toBe(true)
  await expect(drawer.getByRole('button', { name: '2', exact: true })).toBeVisible()
  deny = true
  await drawer.getByRole('button', { name: '2', exact: true }).click()
  await expect(drawer).toContainText('当前无权查看这张单据')
  await expect(drawer).not.toContainText('第二档案记录')
  await page.screenshot({ animations: 'disabled', path: '../outputs/development-governance-20261015-history-denied.png' })
  assert.deepEqual(errors, [])
  console.log('PASS: 默认业务信息、跨单据迟到响应隔离、分页、失败清空与重试、撤权清空')
} finally { await browser.close() }
