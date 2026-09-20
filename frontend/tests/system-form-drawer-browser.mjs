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
  await page.route('**/*', async route => {
    const { origin, pathname: path } = new URL(route.request().url())
    if (origin !== 'http://127.0.0.1:5174') return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    const method = route.request().method()
    let body = []
    if (path === '/api/auth/me') body = { id: 1, username: 'mock', permissions: ['system:user:view', 'system:user:add', 'system:user:edit', 'system:enum:view', 'system:enum:add', 'system:enum:edit'] }
    else if (path === '/api/users') body = { items: [], total: 0 }
    else if (path === '/api/depts/tree') body = [{ id: 1, dept_name: '测试部门', parent_id: 0, sort: 0, status: 1, children: [] }]
    else if (path === '/api/dicts') body = [
      { id: 1, dict_code: 'product_category', dict_name: '产品类别', mode: 'configurable', allow_add: true, bindings: [], item_count: 1 },
      { id: 2, dict_code: 'equipment_series', dict_name: '设备系列', mode: 'configurable', allow_add: true, bindings: [], item_count: 0 },
    ]
    else if (path === '/api/dicts/1/items') body = [{ id: 5, item_value: '101', item_label: '测试类别', sort: 1, status: 1, reference_count: 0 }]
    else if (path.startsWith('/api/dicts/code/')) body = { options: [], label_map: {} }
    if (method === 'POST' || method === 'PUT') {
      writes.push({ path, method, data: route.request().postDataJSON() })
      if (failSave) return route.fulfill({ status: 422, json: { detail: '模拟保存失败' } })
      body = { id: 5 }
    }
    await route.fulfill({ json: body })
  })
  const drawer = page.locator('.pms-form-drawer:visible')
  async function checkLayout(name) {
    await expect(drawer).toBeVisible()
    await expect(drawer.getByRole('heading', { name, exact: true })).toBeVisible()
    await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().right))).toBe(page.viewportSize().width - 16)
    const geometry = await drawer.evaluate(el => ({ width: el.getBoundingClientRect().width, bottom: el.querySelector('.el-drawer__footer').getBoundingClientRect().bottom, viewport: innerHeight }))
    assert.equal(Math.round(geometry.width), 492)
    assert.ok(geometry.bottom <= geometry.viewport)
  }
  await page.goto('http://127.0.0.1:5174/system/user')
  await page.getByText('测试部门', { exact: true }).click({ button: 'right' })
  await page.getByText('新增子部门', { exact: true }).click()
  await checkLayout('新增部门')
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer.getByText('请输入部门名称', { exact: true })).toBeVisible()
  assert.equal(writes.length, 0)
  await drawer.getByRole('textbox', { name: '部门名称', exact: true }).fill('子部门')
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  assert.equal(writes[0].data.parent_id, 1)
  assert.equal(writes[0].path, '/api/depts')
  await page.getByText('测试部门', { exact: true }).click({ button: 'right' })
  await page.getByText('编辑部门', { exact: true }).click()
  await checkLayout('编辑部门')
  await expect(drawer.getByRole('textbox', { name: '部门名称', exact: true })).toHaveValue('测试部门')
  await expect(drawer.locator('#dept-parent')).not.toHaveValue('0')
  const rowGaps = await drawer.locator('.el-form-item').evaluateAll(rows => rows.slice(1).map((row, i) => row.getBoundingClientRect().top - rows[i].getBoundingClientRect().bottom))
  assert.ok(rowGaps.every(gap => Math.abs(gap) <= 1))
  await page.screenshot({ path: '/tmp/pms-dept-drawer-1366.png' })
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
  await page.goto('http://127.0.0.1:5174/system/enum')
  await page.getByRole('button', { name: '新增值', exact: true }).click()
  await checkLayout('新增枚举值')
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer.getByText('请输入显示名称', { exact: true })).toBeVisible()
  await drawer.getByRole('textbox', { name: '显示名称', exact: true }).fill('新增类别')
  await expect(drawer.getByRole('heading', { name: '产品类别', exact: true })).toBeVisible()
  failSave = true
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('模拟保存失败', { exact: true })).toBeVisible()
  await expect(drawer.getByRole('textbox', { name: '显示名称', exact: true })).toHaveValue('新增类别')
  failSave = false
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  assert.equal(writes.at(-1).path, '/api/dicts/1/items')
  assert.equal('item_value' in writes.at(-1).data, false)
  await page.getByRole('button', { name: /产品类别.*可配置/ }).click()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await checkLayout('编辑枚举值')
  await expect(drawer.getByText('101', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 1600, height: 900 })
  await checkLayout('编辑枚举值')
  await page.screenshot({ path: '/tmp/pms-enum-drawer-1600.png' })
  await drawer.getByRole('textbox', { name: '显示名称', exact: true }).fill('修改类别')
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  assert.equal(writes.at(-1).path, '/api/dicts/items/5')
  assert.deepEqual(errors, [])
  console.log('Department and enum drawer browser checks passed')
} finally { await browser.close() }
