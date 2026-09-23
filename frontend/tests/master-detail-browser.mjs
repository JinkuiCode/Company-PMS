import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'

const browser = await chromium.launch({ headless: true, channel: 'msedge' })
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  const errors = []
  page.on('pageerror', e => { errors.push(e.message); console.error(e.message) })
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-ui-test'))
  const rows = [1, 2, 3].map(id => ({ id, project_code: `TEST-${id}`, project_name: `项目${id}`,
    customer: `客户${id}`, is_enabled: 1, created_at: '2020-01-01', status: 1,
    product_category: 1, product_line_id: 1, contract_signed_date: '2026-01-01', contract_ship_date: '2026-12-01',
    plan_start_date: '2026-01-01', plan_end_date: '2026-12-01',
    data_origin: 'pms', sheet_fields: {}, manager_name: '测试用户' }))
  const fields = [{ key: 'note', label: '备注', value_type: 'text', source_type: 'detail', editable: true }]
  let failSave = false, slowDetail = false, slowSave = false, writes = []
  let releaseSave
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (!path.startsWith('/api/')) return route.continue()
    let body = []
    if (path === '/api/auth/me') body = { id: 1, username: 'test', permissions: ['project:archive:view', 'project:archive:edit', 'project:list:view', 'project:list:edit'] }
    else if (path.includes('/dicts/code/')) body = { items: [{ value: '1', label: '测试' }], label_map: { 1: '测试' } }
    else if (path === '/api/product-lines/options') body = { options: [], label_map: {} }
    else if (path === '/api/projects/archives/fields') body = { items: [] }
    else if (path === '/api/projects/sheet-fields') body = { groups: [{ key: 'basic', label: '基础信息', fields }], policies: [] }
    else if (route.request().method() === 'PUT') {
      writes.push(path)
      if (slowSave) await new Promise(r => { releaseSave = r })
      if (failSave) return route.fulfill({ status: 422, json: { detail: '测试保存失败' } })
      const id = Number(path.match(/\d+/)[0])
      Object.assign(rows.find(r => r.id === id), route.request().postDataJSON())
      body = { id }
    } else if (path === '/api/projects/archives/list') {
      const id = new URL(route.request().url()).searchParams.get('archive_id')
      body = { items: id ? rows.filter(r => r.id === Number(id)) : rows, total: 3 }
    } else if (path === '/api/projects') body = { items: rows, total: 3 }
    else if (/\/sheet-detail$/.test(path)) {
      const id = Number(path.match(/\d+/)[0])
      if (slowDetail && id === 2) await new Promise(r => setTimeout(r, 500))
      body = { groups: [{ key: 'basic', label: '基础信息', fields: [{ ...fields[0], value: `详情${id}` }] }] }
    }
    await route.fulfill({ json: body })
  })
  const cell = id => page.locator(`.ag-cell[col-id="project_code"]`).filter({ hasText: `TEST-${id}` }).first()
  await page.goto('http://127.0.0.1:5174/project/archive')
  await page.locator('.archive-row-actions button').first().click()
  await expect(page.locator('.archive-drawer-title')).toHaveText('项目1')
  await cell(2).click()
  await expect(page.locator('.archive-drawer-title')).toHaveText('项目2')
  await page.getByRole('button', { name: '编辑客户', exact: true }).click()
  await page.locator('#archive-drawer-customer').fill('草稿')
  await cell(3).click()
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.locator('.archive-drawer-title')).toHaveText('项目2')
  failSave = true
  await cell(3).click()
  await page.getByRole('button', { name: '保存后切换', exact: true }).click()
  await expect.poll(() => writes.length).toBe(1)
  await expect(page.locator('.archive-drawer-title')).toHaveText('项目2')
  await expect(page.getByRole('button', { name: '编辑客户', exact: true })).toHaveText('草稿')
  failSave = false
  await cell(3).click()
  await page.getByRole('button', { name: '保存后切换', exact: true }).click()
  await expect(page.locator('.archive-drawer-title')).toHaveText('项目3')
  assert.equal(rows[1].customer, '草稿')
  await page.getByRole('button', { name: '编辑客户', exact: true }).click()
  await page.locator('#archive-drawer-customer').fill('不保存')
  await cell(1).click()
  await page.getByRole('button', { name: '放弃修改并切换', exact: true }).click()
  await expect(page.locator('.archive-drawer-title')).toHaveText('项目1')
  assert.equal(rows[2].customer, '客户3')
  slowSave = true
  await page.getByRole('button', { name: '编辑客户', exact: true }).click()
  await page.locator('#archive-drawer-customer').fill('保存后仍选当前行')
  await cell(2).click()
  await page.getByRole('button', { name: '保存后切换', exact: true }).click()
  await expect(page.locator('.el-message-box')).toBeHidden()
  await expect(page.locator('.archive-drawer-title')).toHaveText('项目1')
  await expect.poll(() => typeof releaseSave).toBe('function')
  await cell(1).click()
  releaseSave()
  await expect(page.locator('.archive-drawer-savebar .is-loading')).toHaveCount(0)
  await expect(page.locator('.archive-drawer-title')).toHaveText('项目1')
  slowSave = false
  await page.goto('http://127.0.0.1:5174/project/list')
  await page.getByRole('button', { name: '编辑项目', exact: true }).first().click()
  await expect(page.locator('.drawer-title')).toHaveText('项目1')
  await expect(page.getByRole('button', { name: '编辑备注', exact: true })).toHaveText('详情1')
  slowDetail = true
  await cell(2).click(); await cell(3).click()
  await expect(page.getByRole('button', { name: '编辑备注', exact: true })).toHaveText('详情3')
  await page.waitForTimeout(600)
  await expect(page.getByRole('button', { name: '编辑备注', exact: true })).toHaveText('详情3')
  await page.getByRole('button', { name: '编辑备注', exact: true }).click()
  await page.locator('.drawer-field-editor input').fill('进度草稿')
  await cell(1).click()
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.locator('.drawer-title')).toHaveText('项目3')
  await cell(1).click()
  await page.getByRole('button', { name: '放弃修改并切换', exact: true }).click()
  await expect(page.locator('.drawer-title')).toHaveText('项目1')
  await expect(page.getByRole('button', { name: '编辑备注', exact: true })).toHaveText('详情1')
  await expect(page.locator('.el-message-box')).toBeHidden()
  await page.getByRole('button', { name: '编辑备注', exact: true }).click()
  await page.locator('.drawer-field-editor input').fill('待保存进度')
  failSave = true
  const beforeWrites = writes.length
  await cell(2).click()
  await page.getByRole('button', { name: '保存后切换', exact: true }).click()
  await expect.poll(() => writes.length).toBe(beforeWrites + 1)
  await expect(page.locator('.drawer-title')).toHaveText('项目1')
  await expect(page.getByRole('button', { name: '编辑备注', exact: true })).toHaveText('待保存进度')
  failSave = false
  await cell(2).click()
  await page.getByRole('button', { name: '保存后切换', exact: true }).click()
  await expect(page.locator('.drawer-title')).toHaveText('项目2')
  await expect(page.getByRole('button', { name: '编辑备注', exact: true })).toHaveText('详情2')
  await expect(cell(2).locator('..')).toHaveClass(/progress-row-active/)
  await expect(cell(1).locator('..')).not.toHaveClass(/progress-row-active/)
  await expect(page.locator('.el-message-box')).toBeHidden()
  await page.screenshot({ path: '../.runtime/master-detail-verified.png' })
  assert.deepEqual(errors, [])
  console.log('archive/progress selection, draft protection, failure and stale response verified')
} finally { await browser.close() }
