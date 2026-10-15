import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const base = process.env.PMS_GOVERNANCE_URL || 'http://127.0.0.1:5198'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 850 } })
  let rows = [1, 2].map(id => ({ id, project_id: 1, task_name: `任务${id}`, progress: 0, status: 1, sort: id }))
  const historyRequests = [], errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-test-only'))
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (url.origin !== base) return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let json = []
    if (path === '/api/auth/me') json = { id: 1, username: 'fixture', permissions: ['project:list:view', 'project:list:delete'] }
    else if (path === '/api/projects/1/tasks') json = rows
    else if (path.startsWith('/api/projects/1/tasks/') && route.request().method() === 'DELETE') {
      rows = rows.filter(row => row.id !== Number(path.split('/').at(-1))); json = { msg: '已删除' }
    } else if (path.startsWith('/api/dicts/code/')) json = { items: [{ value: 1, label: '未开始' }], label_map: { 1: '未开始' } }
    else if (path.startsWith('/api/document-history/task/')) {
      const id = Number(path.split('/').at(-1)); historyRequests.push(id)
      json = { total: 1, actions: [], items: [{ id, actor: '用户', created_at: '2026-10-15T10:00:00', action: 'update', action_label: '编辑', status: 'success', status_label: '成功', source: '任务', summary: `任务${id}的操作记录`, diff_items: [] }] }
    }
    return route.fulfill({ json })
  })
  await page.goto(`${base}/project/1/progress`)
  await page.getByRole('row').filter({ hasText: '任务2' }).locator('[col-id="task_name"]').click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: '记录', exact: true }).first().click()
  await expect(page.getByRole('dialog', { name: '任务1 · 操作记录', exact: true })).toContainText('任务1的操作记录')
  await page.getByRole('row').filter({ hasText: '任务2' }).locator('[col-id="task_name"]').click()
  await expect(page.getByRole('dialog', { name: '任务2 · 操作记录', exact: true })).toContainText('任务2的操作记录')
  assert.ok(historyRequests.includes(2))
  await page.screenshot({ animations: 'disabled', path: '../outputs/development-governance-20261015-task-history.png' })
  await page.locator('.ag-pinned-right-cols-container [row-index="1"] .del-btn').click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByText('任务2的操作记录', { exact: true })).toHaveCount(0)
  assert.equal(rows.length, 1)
  assert.deepEqual(errors, [])
  console.log('PASS: 任务记录显式打开、点击其他行联动、操作不被遮挡、删除后关闭记录')
} finally { await browser.close() }
