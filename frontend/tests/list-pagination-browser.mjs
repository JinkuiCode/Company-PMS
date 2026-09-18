import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import { verifyColumnLayout } from './grid-layout-browser-helper.mjs'

const browser = await chromium.launch({ headless: true, channel: 'msedge' })
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  const failures = []
  page.on('pageerror', error => { failures.push(error.message); console.error('PAGE ERROR', error.message) })
  await page.addInitScript(() => localStorage.setItem('access_token', 'local-test-only'))
  const requests = []
  const rows = Array.from({ length: 940 }, (_, i) => ({
    id: 940 - i, project_code: `CODE-${String(940 - i).padStart(4, '0')}`,
    project_name: '项目名称很长需要完整限制在列内且不能覆盖客户'.repeat(5),
    customer: i % 2 ? '乙客户' : '甲客户', is_enabled: 1, product_category: 1,
    plan_start_date: '2026-09-01', plan_end_date: '2026-09-30',
    manager_name: '测试用户', created_by_name: '测试用户', data_origin: 'kingdee_initial',
    can_delete: false, erp_sync_status: 'historical',
  }))
  let failNext = false
  let progressEdit = true
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    if (!url.pathname.startsWith('/api/')) return route.continue()
    let body = []
    if (route.request().method() === 'PUT' && /\/projects\/archives\/\d+$/.test(url.pathname)) {
      const row = rows.find(item => item.id === Number(url.pathname.split('/').at(-1)))
      Object.assign(row, route.request().postDataJSON())
      return route.fulfill({ json: row })
    }
    if (url.pathname === '/api/auth/me') body = { id: 1, username: 'test', real_name: '测试', permissions: ['project:archive:view', 'project:archive:edit', 'project:archive:sync', 'project:archive:delete', 'project:list:view', ...(progressEdit ? ['project:list:edit', 'project:list:delete'] : []), ...['user', 'role', 'dict', 'enum', 'field-policy', 'operation-log'].map(key => `system:${key}:view`)] }
    else if (url.pathname === '/api/auth/product-categories') body = { unrestricted: true }
    else if (url.pathname.includes('/dicts/code/')) body = { items: [{ value: '1', label: '测试类别' }], label_map: { 1: '测试类别' } }
    else if (url.pathname === '/api/projects/archives/fields') body = { items: [] }
    else if (url.pathname === '/api/projects/sheet-fields') body = { groups: [], policies: [] }
    else if (['/api/users', '/api/field-catalog', '/api/field-policies', '/api/operation-logs'].includes(url.pathname)) body = { items: [], total: 0, groups: [] }
    else if (url.pathname === '/api/dicts') body = [{ id: 1, dict_name: '测试枚举', dict_code: 'test', item_count: 1 }]
    else if (url.pathname === '/api/dicts/1/items') body = [{ id: 1, item_value: 1, item_label: '测试名称'.repeat(60), status: 1 }]
    else if (url.pathname === '/api/projects') {
      const all = Array.from({ length: 2040 }, (_, i) => ({ id: 2040 - i,
        project_code: `PROGRESS-${String(2040 - i).padStart(4, '0')}`, project_name: '项目',
        status: 1, product_category: 1, design_progress: 50, sheet_fields: {},
      }))
      const start = (Number(url.searchParams.get('page')) - 1) * Number(url.searchParams.get('page_size'))
      body = { total: all.length, items: url.searchParams.get('all_rows') === 'true' ? all : all.slice(start, start + Number(url.searchParams.get('page_size'))) }
    }
    else if (url.pathname === '/api/projects/archives/list') {
      const params = Object.fromEntries(url.searchParams)
      requests.push(params)
      if (failNext) { failNext = false; return route.fulfill({ status: 500, json: { detail: '测试错误' } }) }
      let selected = rows.filter(row => !params.keyword || `${row.project_code}${row.customer}`.includes(params.keyword))
      if (params.archive_id) selected = selected.filter(row => row.id === Number(params.archive_id))
      for (const filter of JSON.parse(params.filters || '[]')) {
        if (filter.value) selected = selected.filter(row => String(row[filter.field] || '').includes(filter.value))
      }
      const sort = JSON.parse(params.sort || '[]')[0]
      if (sort) selected.sort((a, b) => String(a[sort.colId]).localeCompare(String(b[sort.colId])) * (sort.sort === 'asc' ? 1 : -1))
      const start = (Number(params.page) - 1) * Number(params.page_size)
      body = { total: selected.length, items: selected.slice(start, start + Number(params.page_size)) }
      await new Promise(resolve => setTimeout(resolve, params.keyword === 'CODE-0001' ? 700 : 100))
    }
    return route.fulfill({ json: body })
  })
  await page.goto('http://127.0.0.1:5174/project/archive')
  await expect(page.getByText('共 940 条')).toBeVisible()
  assert.equal(requests.at(-1).page_size, '50')
  assert.ok(await page.locator('.ag-pinned-left-cols-container [col-id="project_code"]').count() <= 50)
  await expect(page.locator('.archive-row-actions').first()).toHaveText('编辑同步')
  async function actionGeometry() {
    return page.locator('.ag-cell.pms-actions-cell').first().evaluate(cell => {
      const buttons = [...cell.querySelectorAll('button')]
      const rect = cell.getBoundingClientRect()
      return { width: rect.width, padding: getComputedStyle(cell).paddingLeft,
        buttons: buttons.map(button => { const r = button.getBoundingClientRect(); return { width: r.width, height: r.height, left: r.left - rect.left } }) }
    })
  }
  const archiveActions = await actionGeometry()
  await verifyColumnLayout(page, 'customer', '客户')
  assert.equal(archiveActions.width, 112)
  assert.equal(archiveActions.padding, '8px')
  assert.deepEqual(archiveActions.buttons.map(b => [b.width, b.height]), [[40, 24], [40, 24]])
  assert.equal(archiveActions.buttons[1].left - archiveActions.buttons[0].left, 48)
  const nameCell = page.locator('.ag-center-cols-container [col-id="project_name"]').first()
  await nameCell.hover()
  await expect(page.locator('.ag-tooltip').first()).toBeVisible({ timeout: 1000 })
  await page.mouse.move(0, 0)
  await page.locator('.pagination-center .page-btn').filter({ hasText: /^2$/ }).click()
  await expect.poll(() => requests.at(-1).page).toBe('2')
  await expect(page.locator('.ag-center-cols-container [col-id="project_name"]').first()).toBeVisible()
  const geometry = await page.locator('.ag-center-cols-container [col-id="project_name"]').first().evaluate(cell => {
    const value = cell.querySelector('.ag-cell-value')
    const wrapper = cell.querySelector('.ag-cell-wrapper')
    return { cell: cell.getBoundingClientRect().width, value: value?.getBoundingClientRect().width,
      wrapperOverflow: wrapper && getComputedStyle(wrapper).overflow, textOverflow: value && getComputedStyle(value).textOverflow }
  })
  assert.ok(geometry.value <= geometry.cell, JSON.stringify(geometry))
  assert.equal(geometry.textOverflow, 'ellipsis')
  await page.getByRole('textbox', { name: '搜索项目档案' }).fill('甲客户')
  await expect(page.getByText('共 470 条')).toBeVisible()
  assert.equal(requests.at(-1).page, '1')
  await page.locator('.page-size-select').selectOption('20')
  await expect.poll(() => requests.at(-1).page_size).toBe('20')
  assert.equal(requests.at(-1).keyword, '甲客户')
  await page.getByRole('textbox', { name: '搜索项目档案' }).fill('CODE-0001')
  await expect.poll(() => requests.at(-1).keyword).toBe('CODE-0001')
  await page.getByRole('textbox', { name: '搜索项目档案' }).fill('CODE-0002')
  await expect(page.getByText('共 1 条')).toBeVisible()
  await page.waitForTimeout(800)
  await expect(page.locator('.ag-pinned-left-cols-container [col-id="project_code"]').first()).toHaveText('CODE-0002')
  failNext = true
  await page.getByRole('textbox', { name: '搜索项目档案' }).fill('失败')
  await expect(page.getByRole('alert').filter({ hasText: '加载失败' })).toBeVisible()
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: '加载失败' })).toHaveCount(0)
  await page.getByRole('textbox', { name: '搜索项目档案' }).fill('')
  await expect(page.getByText('共 940 条')).toBeVisible()
  await page.locator('.ag-header-cell[col-id="project_code"] .ag-header-cell-label').click()
  await expect.poll(() => JSON.parse(requests.at(-1).sort)[0]?.sort).toBe('asc')
  await expect(page.locator('.ag-pinned-left-cols-container [col-id="project_code"]').first()).toHaveText('CODE-0001')
  await page.reload()
  await expect(page.getByText('共 940 条')).toBeVisible()
  assert.equal(JSON.parse(requests.at(-1).sort)[0].sort, 'asc')
  await page.getByRole('button', { name: '添加筛选', exact: true }).click()
  await page.getByRole('textbox', { name: '筛选值', exact: true }).fill('CODE-000')
  await expect(page.getByText('共 9 条')).toBeVisible()
  assert.equal(requests.at(-1).page, '1')
  await page.getByRole('button', { name: '清空筛选', exact: true }).click()
  await expect(page.getByText('共 940 条')).toBeVisible()
  await page.getByRole('textbox', { name: '搜索项目档案' }).fill('乙客户')
  await expect(page.getByText('共 470 条')).toBeVisible()
  await page.getByRole('button', { name: '编辑', exact: true }).first().click()
  await page.getByRole('button', { name: '编辑客户', exact: true }).click()
  await page.getByRole('textbox', { name: '客户', exact: true }).fill('新客户')
  await page.getByRole('button', { name: /保存修改/ }).click()
  await expect(page.getByText('共 469 条')).toBeVisible()
  await expect(page.getByRole('button', { name: '编辑客户', exact: true })).toHaveText('新客户')
  await expect(page.getByRole('button', { name: /保存修改/ })).toBeDisabled()
  assert.equal(requests.filter(item => !item.archive_id).at(-1).keyword, '乙客户')
  await page.getByRole('button', { name: '关闭档案编辑', exact: true }).click()
  await page.getByRole('textbox', { name: '搜索项目档案' }).fill('')
  await expect(page.getByText('共 940 条')).toBeVisible()
  for (const width of [1366, 1600]) {
    await page.setViewportSize({ width, height: width === 1366 ? 768 : 900 })
    const pagination = await page.locator('.custom-pagination').boundingBox()
    assert.ok(pagination.y + pagination.height <= page.viewportSize().height)
    assert.ok(page.viewportSize().height - pagination.y - pagination.height < 60)
    await page.screenshot({ path: `/tmp/pms-pagination-${width}.png` })
  }
  rows.splice(0, 50)
  await page.locator('.pagination-center .page-btn').filter({ hasText: /^19$/ }).click()
  await expect(page.getByText('共 890 条')).toBeVisible()
  await expect(page.locator('.pagination-center .page-btn.active')).toHaveText('18')
  await expect.poll(() => requests.at(-1).page).toBe('18')
  await page.goto('http://127.0.0.1:5174/project/list')
  await expect(page.getByText('共 2040 条')).toBeVisible()
  await verifyColumnLayout(page, 'design_progress', '设计进度')
  await expect(page.locator('.progress-row-actions .detail-btn').first()).toHaveText('编辑')
  assert.deepEqual(await actionGeometry(), archiveActions)
  progressEdit = false
  await page.reload()
  await expect(page.locator('.progress-row-actions .detail-btn').first()).toHaveText('查看')
  const readOnlyActions = await actionGeometry()
  assert.equal(readOnlyActions.width, 112)
  assert.deepEqual(readOnlyActions.buttons, archiveActions.buttons.slice(0, 1))
  assert.ok(await page.locator('.ag-pinned-left-cols-container [col-id="project_code"]').count() <= 50)
  await page.locator('.pagination-center .page-btn').filter({ hasText: /^2$/ }).click()
  await expect(page.locator('.ag-pinned-left-cols-container [col-id="project_code"]').first()).toHaveText('PROGRESS-1990')
  await page.locator('.ag-header-cell[col-id="project_code"] .ag-header-cell-label').click()
  await expect(page.locator('.ag-pinned-left-cols-container [col-id="project_code"]').first()).toHaveText('PROGRESS-0051')
  await page.getByRole('textbox', { name: '搜索项目进度' }).fill('PROGRESS-0001')
  await expect(page.getByText('共 1 条')).toBeVisible()
  await expect(page.locator('.ag-pinned-left-cols-container [col-id="project_code"]').first()).toHaveText('PROGRESS-0001')
  for (const route of ['user', 'role', 'dict', 'enum', 'field-policy', 'operation-log']) {
    await page.goto('http://127.0.0.1:5174/system/' + route)
    const table = page.locator('.el-table, .ag-root-wrapper').first()
    await expect(table).toBeVisible()
    await page.waitForTimeout(250)
    const box = await table.boundingBox()
    assert.ok(box.height > 450, `${route} height ${box.height}`)
    assert.ok(box.y + box.height <= 885, `${route} bottom ${box.y + box.height}`)
    if (route === 'enum') {
      await page.locator('.el-table__body .el-table__row td').nth(1).hover()
      await expect(page.getByRole('tooltip')).toBeVisible({ timeout: 1000 })
      await page.mouse.move(0, 0)
    }
    await page.screenshot({ path: `/tmp/pms-density-${route}.png` })
  }
  assert.deepEqual(failures, [])
  console.log('Browser passed: paging, query retention, sizing, stale responses, errors, widths', geometry)
} finally {
  await browser.close()
}
