import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'

const base = process.env.PMS_GOVERNANCE_URL || 'http://127.0.0.1:5198'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
  page.setDefaultTimeout(10000)
  const errors = [], writes = []
  let allowed = true, failSave = false, holdRefresh = false
  let releaseRefresh
  const refreshGate = new Promise(resolve => { releaseRefresh = resolve })
  const row = { id: 1, project_code: 'MAINT-001', project_name: '原名称', customer: '客户',
    archive_category: 1, product_line_id: 7, quantity: 1, quantity_unit: 7, manager_id: 42,
    manager_name: '负责人', machine_model: 1, equipment_series: 1, serial_no: 'SN-001',
    is_enabled: 1, data_origin: 'offline_initial', erp_sync_policy: 'manual',
    created_at: '2020-01-01', can_edit: false, can_maintain: true, change_mode: 'readonly',
    change_version: 'a'.repeat(64), edit_reason: '只有项目负责人或其部门负责人可以修改',
    contract_signed_date: '2020-01-01', contract_ship_date: '2020-02-01' }
  const fields = ['archive_category', 'project_code', 'project_name', 'customer', 'product_line_id',
    'quantity', 'quantity_unit', 'manager_id', 'machine_model', 'equipment_series', 'serial_no',
    'contract_signed_date', 'contract_ship_date', 'remarks']
  await page.addInitScript(() => localStorage.setItem('access_token', 'isolated-test-only'))
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method()
    if (url.origin !== base) return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let body = []
    if (path === '/api/auth/me') body = { id: 99, username: 'maintenance-fixture', real_name: '维护测试',
      permissions: ['project:archive:view', 'project:archive:edit', ...(allowed ? ['project:archive:maintain'] : [])] }
    else if (path === '/api/users/options') body = [{ id: 42, username: 'owner', real_name: '负责人' }]
    else if (path === '/api/product-lines/options') body = { options: [{ value: 7, label: '产品线甲' }], label_map: { 7: '产品线甲' } }
    else if (path === '/api/projects/archives/fields') body = { items: fields.map(field_key => ({ field_key,
      label: field_key, visible: true, editable: true, list_available: true, required: false })) }
    else if (path.startsWith('/api/dicts/code/')) body = { items: [{ value: 1, label: '主机' }, { value: 7, label: '台' }], label_map: { 1: '主机', 7: '台' } }
    else if (path === '/api/projects/archives/list') {
      if (holdRefresh) await refreshGate
      body = { total: 1, items: [{ ...row, can_maintain: allowed }] }
    }
    else if (path === '/api/projects/archives/1/maintenance/preview') body = { mode: 'maintenance', expected_version: row.change_version,
      differences: [{ field_key: 'project_name', field_label: '项目名称', before_display: row.project_name,
        after_display: route.request().postDataJSON().updates.project_name }] }
    else if (path === '/api/document-history/archive/1') body = { total: 1, actions: [{ value: 'maintain', label: '维护' }], items: [{
      id: 81, actor: '资料维护人员', created_at: '2026-10-15T10:20:00', action: 'maintain', action_label: '维护',
      status: 'success', status_label: '成功', source: '项目档案', summary: '档案维护：纠正历史资料',
      diff_items: [{ field_key: 'project_name', field_label: '项目名称', before_display: '原名称', after_display: '维护后的名称' }],
    }] }
    else if (path === '/api/projects/archives/1/maintenance' && method === 'PUT') {
      writes.push(route.request().postDataJSON())
      if (failSave) return route.fulfill({ status: 403, json: { detail: '维护授权已撤销' } })
      Object.assign(row, route.request().postDataJSON().updates, { change_version: 'b'.repeat(64) })
      holdRefresh = true
      body = { mode: 'maintenance', sync_queued: false }
    }
    await route.fulfill({ json: body })
  })
  await page.goto(`${base}/project/archive`)
  await page.getByRole('button', { name: '查看', exact: true }).click()
  let drawer = page.getByRole('dialog', { name: '查看项目档案', exact: true })
  await expect(drawer.getByRole('button', { name: '维护', exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '维护', exact: true }).click()
  drawer = page.getByRole('dialog', { name: '维护项目档案', exact: true })
  await drawer.getByRole('textbox', { name: '项目名称', exact: true }).fill('维护后的名称')
  await drawer.getByRole('button', { name: '确认维护', exact: true }).click()
  const confirmation = page.getByRole('dialog', { name: '确认档案维护', exact: true })
  await expect(confirmation).toContainText('原名称')
  await expect(confirmation).toContainText('维护后的名称')
  await confirmation.getByRole('button', { name: '确认生效', exact: true }).click()
  await expect(confirmation).toContainText('请填写维护原因')
  assert.equal(writes.length, 0)
  await confirmation.getByRole('textbox', { name: '维护原因', exact: true }).fill('纠正历史资料')
  failSave = true
  await confirmation.getByRole('button', { name: '确认生效', exact: true }).click()
  await expect(confirmation.getByRole('textbox', { name: '维护原因', exact: true })).toHaveValue('纠正历史资料')
  assert.equal(row.project_name, '原名称')
  failSave = false
  await confirmation.getByRole('button', { name: '确认生效', exact: true }).click()
  await expect(confirmation).toBeHidden()
  await expect(drawer.getByRole('textbox', { name: '项目名称', exact: true })).not.toBeEditable()
  holdRefresh = false
  releaseRefresh()
  assert.equal(row.project_name, '维护后的名称')
  assert.equal(writes.at(-1).reason, '纠正历史资料')
  assert.equal(writes.at(-1).expected_version, 'a'.repeat(64))
  await page.setViewportSize({ width: 1100, height: 650 })
  drawer = page.getByRole('dialog', { name: '查看项目档案', exact: true })
  await expect(drawer).toBeVisible()
  await drawer.getByRole('tab', { name: '操作记录', exact: true }).click()
  await expect(drawer.getByText('资料维护人员', { exact: true })).toBeVisible()
  await drawer.getByRole('button', { name: '查看 1 项字段变化', exact: true }).click()
  await expect(drawer.getByRole('table')).toContainText('维护后的名称')
  await expect(drawer.getByText('request_path', { exact: false })).toHaveCount(0)
  await drawer.getByRole('tab', { name: '业务信息', exact: true }).click()
  const box = await drawer.boundingBox()
  assert.ok(box.x >= 0 && box.x + box.width <= 1100)
  await page.screenshot({ path: '../outputs/development-governance-20261015-maintenance.png' })
  allowed = false
  await page.reload()
  await page.getByRole('button', { name: '查看', exact: true }).click()
  await expect(page.getByRole('button', { name: '维护', exact: true })).toHaveCount(0)
  assert.deepEqual(errors, [])
  console.log('PASS: 显式维护、原因必填、服务端差异、失败保留草稿、权限入口与窄窗')
} finally {
  await browser.close()
}
