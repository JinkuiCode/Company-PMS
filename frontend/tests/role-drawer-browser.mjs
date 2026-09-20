import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
  page.setDefaultTimeout(10000)
  const errors = [], writes = []
  let failSave = false
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript(() => localStorage.setItem('access_token', 'mock-only'))
  const menu = { id: 10, menu_type: 'C', menu_name: '项目档案', path: '/project/archive', status: 1, visible: 1, children: [
    { id: 11, parent_id: 10, menu_type: 'B', menu_name: '查看', permission_code: 'project:archive:view', status: 1, visible: 1 },
    { id: 12, parent_id: 10, menu_type: 'B', menu_name: '编辑', permission_code: 'project:archive:edit', status: 1, visible: 1 },
  ] }
  await page.route('**/*', async route => {
    const { origin, pathname: path } = new URL(route.request().url())
    if (origin !== 'http://127.0.0.1:5174') return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let body = []
    if (path === '/api/auth/me') body = { id: 1, username: 'mock', permissions: ['system:role:view', 'system:role:add', 'system:role:edit'] }
    else if (path === '/api/roles') body = [{ id: 1, role_name: '测试角色', role_code: 'test', data_scope: 4, status: 1, home_menu_id: 10, home_priority: 20, product_category_ids: '101', remark: '保留备注' }]
    else if (path === '/api/menus/tree') body = [menu]
    else if (path === '/api/roles/1/menus') body = { menu_ids: [10, 11, 12] }
    else if (path.startsWith('/api/dicts/code/')) body = { items: [{ value: '101', label: '测试类别', status: 1 }], all_items: [{ value: '101', label: '测试类别', status: 1 }], label_map: { 101: '测试类别' } }
    if (['POST', 'PUT'].includes(route.request().method())) {
      writes.push({ path, data: route.request().postDataJSON() })
      if (failSave) return route.fulfill({ status: 422, json: { detail: '模拟保存失败' } })
      body = { id: 2 }
    }
    await route.fulfill({ json: body })
  })
  await page.goto('http://127.0.0.1:5174/system/role')
  await page.getByRole('button', { name: '新增角色', exact: true }).click()
  const drawer = page.locator('.pms-form-drawer:visible')
  await expect(drawer).toBeVisible()
  await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().right))).toBe(1350)
  assert.equal(Math.round((await drawer.boundingBox()).width), 492)
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer.getByText('请输入角色名称', { exact: true })).toBeVisible()
  assert.equal(writes.length, 0)
  await drawer.getByRole('textbox', { name: '角色名称', exact: true }).fill('新增角色测试')
  await drawer.getByRole('textbox', { name: '角色编码', exact: true }).fill('new_test')
  await drawer.locator('.permission-check-all').click()
  await drawer.locator('.el-select__wrapper').filter({ has: page.locator('#role-home') }).click()
  await page.getByRole('option', { name: '项目档案', exact: true }).click()
  await drawer.getByRole('spinbutton', { name: '首页优先级', exact: true }).fill('30')
  failSave = true
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('模拟保存失败', { exact: true })).toBeVisible()
  await expect(drawer.getByRole('textbox', { name: '角色名称', exact: true })).toHaveValue('新增角色测试')
  failSave = false
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  assert.equal(writes.at(-1).path, '/api/roles')
  assert.equal(writes.at(-1).data.home_menu_id, 10)
  assert.deepEqual([...writes.at(-1).data.menu_ids].sort((a,b) => a-b), [10,11,12])
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(drawer.getByRole('textbox', { name: '角色编码', exact: true })).toBeDisabled()
  await expect(drawer.getByRole('spinbutton', { name: '首页优先级', exact: true })).toHaveValue('20')
  await expect(drawer.getByRole('checkbox', { name: '全选权限', exact: true })).toBeChecked()
  await drawer.locator('.permission-check-all').click()
  await expect(drawer.locator('.el-select').filter({ has: page.locator('#role-home') })).toContainText('自动选择可访问页面')
  for (const [width, height] of [[1366, 768], [1600, 900]]) {
    await page.setViewportSize({ width, height })
    await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().right))).toBe(width - 16)
    await drawer.locator('.permission-check-all').scrollIntoViewIfNeeded()
    const box = await drawer.getByRole('button', { name: '保存', exact: true }).boundingBox()
    assert.ok(box.y + box.height <= height)
    await page.screenshot({ path: `/tmp/pms-role-drawer-${width}.png` })
    await drawer.locator('.el-drawer__body').evaluate(el => { el.scrollTop = 0 })
    await page.screenshot({ path: `/tmp/pms-role-drawer-top-${width}.png` })
  }
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  const result = writes.at(-1)
  assert.equal(result.path, '/api/roles/1')
  assert.equal(result.data.home_menu_id, null)
  assert.equal(result.data.product_category_ids, '101')
  assert.equal(result.data.remark, '保留备注')
  assert.deepEqual(errors, [])
  console.log('Role drawer checks passed: layout, required, create/edit, retry, permissions/home linkage, payload preservation')
} finally { await browser.close() }
