import assert from 'node:assert/strict'
import { chromium, expect } from '@playwright/test'

const base = process.env.PMS_TEST_URL || 'http://127.0.0.1:5189'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
const fixture = 'synthetic-current-initial-82'
let current = { code: 'user.initial_password', name: '用户初始密码', group: '用户管理', description: '新增用户和重置密码使用的初始密码', sensitive: true, configured: true, version: 7, value: null, reveal_status: 'legacy', reveal_message: '旧初始密码仅保存不可逆哈希，需重新保存后才能回显', value_type: 'text' }
const hidden = { ...current, code: 'test.other_secret', name: '其他敏感参数', value: 'synthetic-should-never-display', reveal_status: 'hidden' }
const calls = [], errors = []
await context.addInitScript(() => localStorage.setItem('access_token', 'synthetic-ui-test-token'))
await context.route(`${base}/api/**`, async route => {
  const request = route.request(), path = new URL(request.url()).pathname
  calls.push([request.method(), path])
  let body = []
  if (path === '/api/auth/me') body = { id: 701, username: 'fixture', real_name: '测试用户', permissions: ['system:parameter:view', 'system:parameter:edit'], role_codes: [], status: 1, data_scope: 1, product_line_ids: [] }
  else if (path === '/api/my-menus') body = [{ id: 1, menu_name: '系统管理', menu_type: 'M', children: [{ id: 2, menu_name: '参数设置', path: '/system/parameter', menu_type: 'C' }] }]
  else if (path === '/api/parameters' && request.method() === 'GET') body = { items: [current, hidden] }
  else if (path === '/api/parameters/user.initial_password' && request.method() === 'PUT') {
    const payload = request.postDataJSON()
    assert.equal(payload.version, current.version)
    current = { ...current, value: payload.value, version: current.version + 1, reveal_status: 'available', reveal_message: null }
    body = { message: '参数已更新', version: current.version }
  } else if (request.method() !== 'GET') throw new Error(`Unexpected write: ${path}`)
  await route.fulfill({ json: body, headers: { 'Cache-Control': 'no-store' } })
})
const page = await context.newPage()
page.on('pageerror', error => errors.push(error.message))
try {
  await page.goto(`${base}/system/parameter`)
  await expect(page.getByText(current.reveal_message, { exact: true })).toBeVisible()
  const initial = page.locator('.el-table__row').filter({ hasText: 'user.initial_password' })
  await initial.getByRole('button', { name: '修改', exact: true }).click()
  const input = page.locator('[id="parameter-user.initial_password"]')
  await expect(input).toHaveValue('')
  await expect(input).toHaveAttribute('type', 'password')
  await input.fill(fixture)
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText(fixture, { exact: true })).toBeVisible()
  const statusGeometry = await page.getByText(fixture, { exact: true }).evaluate(el => ({ height: el.getBoundingClientRect().height, minHeight: getComputedStyle(el).minHeight, transform: getComputedStyle(el).transform, lineHeight: getComputedStyle(el).lineHeight }))
  assert.ok(statusGeometry.height >= 24, `current value keeps shared status minimum height: ${JSON.stringify(statusGeometry)}`)
  await expect(page.getByText('synthetic-should-never-display', { exact: true })).toHaveCount(0)
  await expect(page.getByText('已设置 · 不回显', { exact: true })).toBeVisible()
  await page.screenshot({ path: '/private/tmp/pms-parameter-secret-desktop.png' })
  await initial.getByRole('button', { name: '修改', exact: true }).click()
  await expect(input).toHaveValue('')
  await page.getByRole('button', { name: '取消', exact: true }).click()
  const storage = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))
  assert.equal(storage.includes(fixture), false)
  assert.equal(storage.includes('synthetic-should-never-display'), false)
  current = { ...current, value: '合成测试'.repeat(16) }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  const plaintext = page.getByText(current.value, { exact: true })
  await expect(plaintext).toHaveCount(1)
  await page.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate(el => { el.scrollLeft = 310 })
  await expect(plaintext).toBeInViewport()
  const geometry = await plaintext.evaluate(el => ({ scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, height: el.getBoundingClientRect().height }))
  assert.ok(geometry.scrollWidth <= geometry.clientWidth + 1, 'long plaintext wraps inside current-value cell')
  assert.ok(geometry.height > 30)
  assert.ok(await plaintext.evaluate(el => parseFloat(getComputedStyle(el).lineHeight)) >= 16, 'wrapped text remains legible')
  await page.screenshot({ path: '/private/tmp/pms-parameter-secret-mobile.png' })
  assert.deepEqual(errors, [])
  assert.equal(calls.filter(([method]) => method === 'PUT').length, 1)
  console.log('parameter browser passed: legacy/resave, default plaintext, other secret hidden, empty masked editor, no browser persistence, desktop/mobile wrapping; every API mocked')
} catch (error) {
  console.error({ url: page.url(), calls, errors, body: await page.locator('body').innerText() })
  await page.screenshot({ path: '/private/tmp/pms-parameter-secret-browser-failure.png' })
  throw error
} finally {
  await browser.close()
}
