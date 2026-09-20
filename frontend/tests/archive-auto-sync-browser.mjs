import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
  page.setDefaultTimeout(10000)
  const errors = [], queries = [], writes = [], inspections = []
  let canRetry = true, failRetry = false
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => localStorage.setItem('access_token', 'mock-only'))
  const task = { id: 1, archive_id: 1, project_code: 'TEST-001', project_name: '后台同步测试项目',
    status: 'failed', status_label: '同步失败', operator_name: '测试保存人', attempts: 1,
    created_at: '2026-09-20T10:00:00', message: '金蝶审核权限不足',
    history: [{ time: '2026-09-20T10:01:00', message: '金蝶审核权限不足' }] }
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (url.origin !== 'http://127.0.0.1:5174') return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let body = []
    if (path === '/api/auth/me') body = { id: 1, username: 'mock', permissions: ['system:sync:view', ...(canRetry ? ['system:sync:retry'] : [])] }
    else if (path === '/api/sync-tasks') {
      queries.push(Object.fromEntries(url.searchParams))
      body = { items: [task], total: 101, worker_enabled: true }
    } else if (path === '/api/sync-tasks/archive/1') body = { items: [task], total: 1 }
    else if (path === '/api/sync-tasks/1/inspect') {
      inspections.push(Object.fromEntries(url.searchParams))
      body = { status: 'failed', message: '已核查，可以重试' }
    }
    else if (path === '/api/sync-tasks/retry') {
      writes.push(route.request().postDataJSON())
      if (failRetry) return route.fulfill({ status: 409, json: { detail: '已有更新版本，请刷新' } })
      body = { items: [{ id: 1, success: true, task_id: 2 }] }
    }
    await route.fulfill({ json: body })
  })
  await page.goto('http://127.0.0.1:5174/system/sync')
  await expect(page.getByRole('button', { name: '重试', exact: true })).toBeVisible()
  assert.equal(queries.at(-1).page_size, '50')
  await page.getByRole('button', { name: '日志', exact: true }).click()
  const drawer = page.locator('.pms-form-drawer:visible')
  await expect(drawer).toContainText('金蝶审核权限不足')
  await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().right))).toBe(1350)
  await expect(drawer.getByRole('button', { name: '重试', exact: true })).toHaveCount(0)
  for (const [width, height] of [[1366, 768], [1600, 900]]) {
    await page.setViewportSize({ width, height })
    await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().right))).toBe(width - 16)
    await page.screenshot({ path: `/tmp/pms-sync-log-${width}.png` })
    const footer = await drawer.getByRole('button', { name: '刷新', exact: true }).boundingBox()
    assert.ok(footer.y + footer.height <= height)
  }
  await page.keyboard.press('Escape')
  await expect(drawer).toHaveCount(0)
  await page.getByRole('button', { name: '2', exact: true }).click()
  await expect.poll(() => queries.at(-1).page).toBe('2')
  await page.getByRole('textbox', { name: '同步项目搜索', exact: true }).fill('TEST')
  await expect.poll(() => queries.at(-1).keyword).toBe('TEST')
  assert.equal(queries.at(-1).page, '1')
  await page.getByRole('textbox', { name: '保存人筛选', exact: true }).fill('测试')
  await expect.poll(() => queries.at(-1).operator).toBe('测试')
  failRetry = true
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await page.locator('.el-message-box').getByRole('button', { name: /确定|确认/ }).click()
  await expect(page.getByText('已有更新版本，请刷新', { exact: true })).toBeVisible()
  failRetry = false
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await page.locator('.el-message-box').getByRole('button', { name: /确定|确认/ }).click()
  await expect(page.getByText('已安排后台重试', { exact: true })).toBeVisible()
  await expect(page.locator('.el-message-box:visible')).toHaveCount(0)
  assert.deepEqual(writes.at(-1), { task_ids: [1] })
  await expect(page.locator('.el-message')).toHaveCount(0)
  await page.locator('.el-table .el-scrollbar__wrap').evaluateAll(elements => elements.forEach(el => { el.scrollLeft = 0 }))
  await page.screenshot({ path: '/tmp/pms-sync-management.png' })
  task.status = 'review'; task.status_label = '待核查'
  await page.reload()
  await page.getByRole('button', { name: '核查', exact: true }).click()
  await expect(page.locator('.el-message-box')).toContainText('金蝶端确认原请求已处理完毕')
  await page.locator('.el-message-box').getByRole('button', { name: '已确认，开始核查', exact: true }).click()
  await expect.poll(() => inspections.length).toBe(1)
  assert.equal(inspections[0].external_request_finished, 'true')
  canRetry = false
  await page.reload()
  await expect(page.getByRole('button', { name: '日志', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '重试', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '批量重试', exact: true })).toHaveCount(0)
  assert.deepEqual(errors, [])
  console.log('Sync UI passed: filters, default pagination, logs, retry success/failure, permission gates, drawer viewport')
} finally { await browser.close() }
