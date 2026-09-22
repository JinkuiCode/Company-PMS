import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 768 } })
await context.addInitScript(() => localStorage.setItem('access_token', 'isolated-product-line-fixture'))
const page = await context.newPage()
page.setDefaultTimeout(10000)
const errors = [], writes = []
let conflict = false
let rejectRoleOptions = false
let rejectOrganizations = false, releaseOldOrganization, oldOrganizationDelivered = false
const row = { id: 1, organization_id: 100, organization_code: '001', organization_name: '金蝶组织原名', display_name: 'Bench', is_enabled: 1, sort: 0, updated_at: '2026-09-21T12:00:00' }
page.on('pageerror', error => errors.push(error.stack || error.message))
await page.route('**/api/**', async route => {
  const path = new URL(route.request().url()).pathname
  if (!path.startsWith('/api/')) return route.continue()
  if (path === '/api/auth/me') return route.fulfill({ json: { id: 999, username: 'test', real_name: '测试用户', permissions: ['system:role:view', 'system:role:edit', 'system:product-line:view', 'system:product-line:add', 'system:product-line:edit', 'system:product-line:delete'], role_codes: [], product_line_ids: [] } })
  if (path === '/api/roles' && route.request().method() === 'GET') return route.fulfill({ json: [{ id: 1, role_name: '产品线角色', role_code: 'line-role', data_scope: 4, status: 1, product_line_ids: [1] }] })
  if (path === '/api/menus/tree') return route.fulfill({ json: [] })
  if (path === '/api/roles/1/menus') return route.fulfill({ json: { menu_ids: [] } })
  if (path === '/api/product-lines/role-options') return rejectRoleOptions
    ? route.fulfill({ status: 503, json: { detail: '角色产品线读取失败，请重试' } })
    : route.fulfill({ json: { items: [{ value: 1, label: '停用产品线', disabled: true }, { value: 2, label: '可用产品线', disabled: false }] } })
  if (path === '/api/my-menus') return route.fulfill({ json: [{ id: 1, menu_name: '系统管理', menu_type: 'M', icon: 'Setting', children: [{ id: 2, menu_name: '产品线管理', path: '/system/product-line', icon: 'OfficeBuilding' }] }] })
  if (path === '/api/product-lines/organizations') {
    if (rejectOrganizations) return route.fulfill({ status: 503, json: { detail: '测试组织来源失败' } })
    const keyword = new URL(route.request().url()).searchParams.get('keyword')
    if (keyword === '旧') {
      await new Promise(resolve => { releaseOldOrganization = resolve })
      await route.fulfill({ json: { items: [{ organization_id: 201, code: 'OLD', name: '旧组织' }], total: 1 } })
      oldOrganizationDelivered = true
      return
    }
    return route.fulfill({ json: { items: [{ organization_id: 200, code: '002', name: keyword === '新' ? '新组织' : 'Single组织' }], total: 1 } })
  }
  if (path === '/api/product-lines' && route.request().method() === 'GET') return route.fulfill({ json: { items: [row], total: 1 } })
  if (path === '/api/product-lines/1' && route.request().method() === 'DELETE') return route.fulfill({ status: 409, json: { detail: '产品线已被引用，只能禁用' } })
  if (['POST', 'PUT'].includes(route.request().method())) {
    writes.push(route.request().postDataJSON())
    return route.fulfill({ status: conflict ? 409 : 200, json: conflict ? { detail: '并发冲突' } : row })
  }
  throw Error(`Unexpected request: ${path}`)
})
try {
  await page.goto('http://127.0.0.1:5174/system/product-line')
  await expect(page.getByText('Bench', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '编辑产品线' })
  await expect(drawer.getByRole('textbox', { name: '金蝶组织', exact: true })).toHaveAttribute('readonly', '')
  await drawer.getByRole('textbox', { name: '产品线名称', exact: true }).fill('Bench业务线')
  conflict = true
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer.getByText('名称、组织冲突或记录已被修改，请关闭并刷新后重试')).toBeVisible()
  await expect(drawer.getByRole('textbox', { name: '产品线名称', exact: true })).toHaveValue('Bench业务线')
  assert.equal(writes[0].expected_updated_at, row.updated_at)
  assert.ok(!('organization_id' in writes[0]))
  for (const size of [{ width: 1366, height: 768 }, { width: 1600, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size)
    await page.evaluate(() => document.fonts.ready)
    await expect.poll(async () => {
      const box = await drawer.boundingBox()
      return box && box.x >= 0 && box.x + box.width <= size.width
    }).toBeTruthy()
    await page.screenshot({ path: resolve('../.runtime', `product-line-${size.width}.png`) })
  }
  conflict = false
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer).not.toBeVisible()
  await page.setViewportSize({ width: 1366, height: 768 })
  await page.getByRole('button', { name: '新增产品线', exact: true }).click()
  const create = page.getByRole('dialog', { name: '新增产品线' })
  await create.locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: '002 · Single组织', exact: true }).click()
  await expect(create.getByRole('textbox', { name: '产品线名称', exact: true })).toHaveValue('Single组织')
  await create.getByRole('button', { name: '保存', exact: true }).click()
  await expect(create).not.toBeVisible()
  assert.equal(writes.at(-1).organization_id, 200)
  await page.getByRole('button', { name: '删除', exact: true }).click()
  await page.locator('.el-message-box').getByRole('button', { name: '确定', exact: true }).click()
  await expect(page.getByText('产品线已被引用，只能禁用', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '删除', exact: true })).toBeEnabled()
  assert.deepEqual(errors, [])
  rejectOrganizations = true
  await page.getByRole('button', { name: '新增产品线', exact: true }).click()
  await expect(create.getByText('金蝶组织读取失败', { exact: false })).toBeVisible()
  rejectOrganizations = false
  await create.getByRole('button', { name: '重试', exact: true }).click()
  await expect(create.getByText('金蝶组织读取失败', { exact: false })).not.toBeVisible()
  const search = create.getByRole('textbox', { name: '查找金蝶组织', exact: true })
  await search.fill('旧')
  await search.press('Enter')
  await expect.poll(() => !!releaseOldOrganization).toBe(true)
  await search.fill('新')
  await search.press('Enter')
  await expect(create.locator('.el-select__wrapper')).not.toHaveClass(/is-disabled/)
  await create.locator('.el-select__wrapper').click()
  await expect(page.getByRole('option', { name: '002 · 新组织', exact: true })).toBeVisible()
  releaseOldOrganization()
  await expect.poll(() => oldOrganizationDelivered).toBe(true)
  await expect(page.getByRole('option', { name: '002 · 新组织', exact: true })).toBeVisible()
  await expect(page.getByRole('option', { name: 'OLD · 旧组织', exact: true })).toHaveCount(0)
  await create.getByRole('button', { name: '取消', exact: true }).click()
  await expect(create).not.toBeVisible()
  rejectRoleOptions = true
  await page.goto('http://127.0.0.1:5174/system/role')
  await expect(page.getByText('角色产品线读取失败，请重试', { exact: true })).toBeVisible()
  const writeCount = writes.length
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '编辑角色' })).not.toBeVisible()
  assert.equal(writes.length, writeCount)
  assert.deepEqual(errors, [], 'role option failure must be handled without an unhandled rejection')
  rejectRoleOptions = false
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const role = page.getByRole('dialog', { name: '编辑角色' })
  const historical = role.getByRole('checkbox', { name: '停用产品线', exact: true })
  await expect(historical).toBeChecked()
  await expect(historical).toBeEnabled()
  await role.getByText('停用产品线', { exact: true }).click()
  await expect(historical).not.toBeVisible()
  await role.getByRole('button', { name: '保存', exact: true }).click()
  await expect(role).not.toBeVisible()
  assert.deepEqual(writes.at(-1).product_line_ids, [])
  assert.deepEqual(errors, [])
  console.log('product line browser checks passed')
} finally { await browser.close() }
