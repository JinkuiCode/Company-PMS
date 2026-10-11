import assert from 'node:assert/strict'
import { chromium, expect } from '@playwright/test'

const base = process.env.PMS_TEST_URL || 'http://127.0.0.1:5174'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true })
await context.addInitScript(() => localStorage.setItem('access_token', 'isolated-business-export-test'))
let canExport = true
const exports = [], writes = [], errors = []
const rows = Array.from({ length: 55 }, (_, i) => ({
  id: i + 1, project_code: `P-${String(i).padStart(3, '0')}`, project_name: `设备${i}`, task_name: `设备${i}`,
  status: i % 2 + 1, dept_id: 1, dept_name: '测试部门', pm_id: 1, pm_name: '测试人员', assignee_name: '测试人员',
  total_progress: 0, progress: 0, sort: i + 1, sheet_fields: {},
}))
await context.route(`${base}/api/**`, async route => {
  const request = route.request(), path = new URL(request.url()).pathname.slice(4)
  if (request.method() === 'POST' && ['/projects/export', '/projects/7/tasks/export'].includes(path)) {
    exports.push({ path, body: request.postDataJSON() })
    return route.fulfill({ body: Buffer.from('isolated-xlsx-file'), contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  }
  if (request.method() !== 'GET') { writes.push(path); return route.abort() }
  let result = []
  if (path === '/auth/me') result = { id: 780, username: 'export-test', real_name: '导出测试', permissions: ['project:list:view', ...(canExport ? ['project:list:export'] : [])] }
  else if (path === '/projects') result = { items: rows, total: rows.length }
  else if (path === '/projects/7/tasks') result = rows
  else if (path === '/projects/sheet-fields') result = { fields: [], groups: [], policies: [] }
  else if (path === '/users/options') result = [{ id: 1, real_name: '测试人员' }]
  else if (path === '/depts/tree' || path === '/depts/options') result = [{ id: 1, dept_name: '测试部门', children: [] }]
  else if (path.startsWith('/dicts/code/')) result = {
    dict_code: path.split('/').at(-1), items: [{ value: '1', label: '准备' }, { value: '2', label: '交付' }],
    all_items: [{ value: '1', label: '准备' }, { value: '2', label: '交付' }], label_map: { 1: '准备', 2: '交付' },
  }
  await route.fulfill({ json: result })
})
const page = await context.newPage()
page.on('pageerror', error => errors.push(error.message))
try {
  for (const [path, queryInput, statusLabel, name, endpoint] of [
    ['/project/list', '查询2值', '节点', '项目列表.xlsx', '/projects/export'],
    ['/project/7/progress', '查询1值', '状态', '项目进度.xlsx', '/projects/7/tasks/export'],
  ]) {
    await page.goto(base + path)
    const button = page.getByRole('button', { name: '导出数据', exact: true })
    await expect(page.locator('.ag-row').first()).toBeVisible()
    await expect(button).toBeDisabled()
    const input = page.getByRole('textbox', { name: queryInput, exact: true })
    await input.fill('设备')
    await page.locator('.pms-query-workspace').getByRole('button', { name: '查询', exact: true }).click()
    await expect(button).toBeEnabled()
    await page.locator(`button[aria-label="${statusLabel}列筛选"]:visible`).click()
    const panel = page.getByRole('dialog', { name: `${statusLabel}列筛选面板` })
    await panel.getByText('准备', { exact: true }).waitFor()
    await panel.getByText('准备', { exact: true }).click()
    await panel.getByRole('button', { name: '降序', exact: true }).click()
    await panel.getByRole('button', { name: '应用', exact: true }).click()
    await input.fill('未提交草稿')
    if (path === '/project/list') {
      await page.locator('.custom-pagination .page-size-select').selectOption('20')
      await page.locator('.custom-pagination').getByRole('button', { name: '2', exact: true }).click()
      await page.getByRole('button', { name: '打开项目进度列设置', exact: true }).click()
      const picker = page.locator('.column-picker-panel:visible')
      await picker.locator('[data-column="budget"] .el-checkbox').click()
      await picker.getByRole('button', { name: '保存', exact: true }).click()
    }
    const download = page.waitForEvent('download')
    await button.click()
    assert.equal((await download).suggestedFilename(), name)
    const sent = exports.at(-1)
    assert.equal(sent.path, endpoint)
    assert.equal(sent.body.filters.find(c => c.field === (path === '/project/list' ? 'project_name' : 'task_name')).value, '设备')
    assert.deepEqual(sent.body.column_filters, [{ field: 'status', mode: 'values', values: [2] }])
    assert.deepEqual(sent.body.sort, [{ colId: 'status', sort: 'desc' }])
    assert.deepEqual(sent.body.parameters, {})
    assert.ok(sent.body.columns.includes(path === '/project/list' ? 'project_name' : 'task_name'))
    assert.ok(!sent.body.columns.some(key => key.includes('actions') || /^\d+$/.test(key)))
    assert.ok(!('page' in sent.body) && !('page_size' in sent.body) && !('row_ids' in sent.body))
    const headers = await page.locator('.ag-header-cell[col-id]').evaluateAll(cells => cells.filter(cell => cell.getBoundingClientRect().width > 0)
      .map(cell => cell.getAttribute('col-id')).filter(key => !key.includes('actions') && !/^\d+$/.test(key)))
    // Offscreen displayed columns are virtualized out of the DOM, but still belong in the export.
    assert.deepEqual(sent.body.columns.filter(key => headers.includes(key)), headers, 'Rendered headers keep their displayed order')
    if (path === '/project/list') {
      assert.ok(!sent.body.columns.includes('budget'), 'User-hidden columns must not be exported')
      assert.ok(sent.body.columns.includes('dept_name'), 'Displayed columns outside the viewport must still be exported')
    }
    const height = await button.evaluate(element => element.getBoundingClientRect().height)
    assert.equal(height, 24, 'Approved compact export button')
    for (const width of [1366, 390]) {
      await page.setViewportSize({ width, height: 900 })
      const box = await button.boundingBox()
      assert.ok(box.x >= 0 && box.x + box.width <= width, 'Export control fits the viewport')
      await page.screenshot({ path: `/private/tmp/business-export-${path === '/project/list' ? 'projects' : 'tasks'}-${width}.png` })
    }
    await page.setViewportSize({ width: 1366, height: 900 })
  }
  canExport = false
  for (const path of ['/project/list', '/project/7/progress']) {
    await page.goto(base + path)
    await expect(page.locator('.ag-row').first()).toBeVisible()
    await expect(page.getByRole('button', { name: '导出数据', exact: true })).toHaveCount(0)
  }
  assert.deepEqual(errors, [])
  assert.deepEqual(writes, [], 'No business modifications')
  assert.equal(exports.length, 2)
  console.log('business export browser passed: applied query, full-result payload, column filter/sort/order, XLSX, independent permission, 24px and desktop/mobile')
} catch (error) {
  console.error({ url: page.url(), errors, exports, body: (await page.locator('body').innerText()).slice(0, 2000) })
  throw error
} finally { await browser.close() }
