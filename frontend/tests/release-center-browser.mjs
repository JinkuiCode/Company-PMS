import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const base = process.env.PMS_GOVERNANCE_URL || 'http://127.0.0.1:5198'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  let reads = 0, failRead = true
  const errors = []
  const release = { id: 1, version: 'v1.0.0', title: '单据记录与版本通知', summary: '查看修改经过，了解系统更新。',
    published_at: '2026-10-15T09:00:00', changes: [{ kind: '新增', title: '单据内查看操作记录', description: '在档案详情中查看字段变化。', guide: 'archive' }] }
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-test-only'))
  await page.route('**/*', route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (url.origin !== base) return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let json = []
    if (path === '/api/auth/me') json = { id: 1, username: 'fixture', permissions: ['project:archive:view', 'feedback:view'] }
    else if (path === '/api/business-notices') json = { total: 0, unread: 0, items: [] }
    else if (path === '/api/releases/runtime') json = { product: 'PMS 项目管理系统', version: 'v1.0.0', environment: '开发环境', published_at: release.published_at, page_updates: { archive: { version: 'v1.0.0' } } }
    else if (path === '/api/releases') json = { total: 1, items: [release] }
    else if (path === '/api/releases/notices') json = { total: 1, unread: reads ? 0 : 1, items: [{ id: 11, read_at: reads ? '2026-10-15T09:10:00' : null, release }] }
    else if (path === '/api/releases/notices/11/read') {
      if (failRead) return route.fulfill({ status: 500, json: { detail: '隔离模拟：已读保存失败' } })
      reads++; json = { read: true }
    }
    else if (path === '/api/releases/1/mail-preview') json = { subject: 'PMS升级通知 v1.0.0', text: 'v1.0.0 单据内查看操作记录' }
    else if (path === '/api/projects/archives/list') json = { total: 0, items: [] }
    else if (path === '/api/product-lines/options') json = { options: [], label_map: {} }
    else if (path === '/api/projects/archives/fields') json = { items: [] }
    return route.fulfill({ json })
  })
  await page.goto(`${base}/project/archive`)
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '关于 PMS', exact: true }).click()
  const about = page.getByRole('dialog', { name: '关于 PMS', exact: true })
  await expect(about.getByText('v1.0.0', { exact: true }).first()).toBeVisible()
  await expect(about.getByText('技术信息', { exact: true })).toHaveCount(0)
  await expect(about).toContainText('单据内查看操作记录')
  await page.screenshot({ animations: 'disabled', path: '../outputs/development-governance-20261015-about.png' })
  await about.getByRole('button', { name: '关闭此对话框', exact: true }).click()
  await page.getByRole('button', { name: /^通知/ }).click()
  await page.getByRole('tab', { name: '升级通知', exact: true }).click()
  const notices = page.getByRole('dialog', { name: '通知', exact: true })
  await expect(notices.getByRole('button', { name: '标为已读', exact: true })).toBeVisible()
  assert.equal(reads, 0)
  await notices.getByRole('button', { name: '查看邮件预览', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '邮件预览', exact: true })).toContainText('v1.0.0')
  await page.getByRole('dialog', { name: '邮件预览', exact: true }).getByRole('button', { name: '关闭此对话框', exact: true }).click()
  await notices.getByRole('button', { name: '标为已读', exact: true }).click()
  await expect(notices.getByRole('button', { name: '标为已读', exact: true })).toBeEnabled()
  assert.equal(reads, 0)
  failRead = false
  await notices.getByRole('button', { name: '标为已读', exact: true }).click()
  await expect(notices.getByRole('button', { name: '已读', exact: true })).toBeDisabled()
  assert.equal(reads, 1)
  await page.screenshot({ animations: 'disabled', path: '../outputs/development-governance-20261015-notices.png' })
  await notices.getByRole('button', { name: '关闭此对话框', exact: true }).click()
  await page.setViewportSize({ width: 518, height: 760 })
  await expect(page.getByRole('button', { name: '用户菜单', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '关于 PMS', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '关于 PMS', exact: true })).toContainText('v1.0.0')
  assert.deepEqual(errors, [])
  console.log('PASS: 用户菜单关于PMS、真实版本、个人通知、显式已读、邮件预览与普通用户技术信息隔离')
} finally { await browser.close() }
