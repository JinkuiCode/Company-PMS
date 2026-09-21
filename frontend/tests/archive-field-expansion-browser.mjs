import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'

const origin = process.env.PMS_TEST_ORIGIN || 'http://127.0.0.1:5174'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.setDefaultTimeout(10000)
  const errors = [], writes = [], creates = [], queries = []
  let regionRequests = 0, rejectCreate = true
  let releaseCreate
  const row = { id: 1, project_code: 'ARCH-TEST', project_name: '测试档案', is_enabled: 1,
    manager_id: 17, manager_name: '原负责人', product_category: 1, product_line_id: 7,
    address_province: '11', address_city: '1101', address_detail: '测试地址',
    created_at: '2026-09-19T10:00:00', erp_sync_status: 'success' }
  const fields = ['project_code', 'project_name', 'customer', 'product_category', 'manager_id', 'equipment_series', 'serial_no',
    'product_line_id', 'contract_signed_date', 'contract_ship_date', 'actual_ship_date', 'warranty_end_date',
    'address_province', 'address_city', 'address_detail', 'project_contact', 'contact_phone', 'plan_start_date', 'plan_end_date']
  const regions = [{ value: '11', label: '北京市', children: [{ value: '1101', label: '北京市辖区' }] },
    { value: '12', label: '天津市', children: [{ value: '1201', label: '天津市辖区' }] }]
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => localStorage.setItem('access_token', 'mock-only'))
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname
    if (url.origin !== origin) return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let body = []
    if (path === '/api/auth/me') body = { id: 42, username: 'test', real_name: '当前用户', permissions: ['project:archive:view', 'project:archive:add', 'project:archive:edit'] }
    else if (path === '/api/users/options') body = [{ id: 42, real_name: '当前用户' }, { id: 17, real_name: '原负责人' }]
    else if (path === '/api/auth/product-categories') body = { unrestricted: true }
    else if (path === '/api/projects/archives/fields') body = { items: fields.map(field_key => ({ field_key, label: field_key,
      visible: true, editable: true, list_available: true,
      required: ['contract_signed_date', 'contract_ship_date'].includes(field_key), required_effective_at: '2026-09-20T00:00:00' })) }
    else if (path === '/api/projects/archives/regions') { regionRequests++; body = regions }
    else if (path.startsWith('/api/dicts/code/')) body = { items: [{ value: 1, label: '类别一' }, { value: 7, label: 'Bench' }, { value: 8, label: 'Single' }], label_map: { 1: '类别一', 7: 'Bench', 8: 'Single' } }
    else if (path === '/api/projects/archives/list') { queries.push(Object.fromEntries(url.searchParams)); body = { items: [row], total: 1 } }
    else if (path === '/api/projects/archives/1' && req.method() === 'PUT') { const data = req.postDataJSON(); writes.push(data); Object.assign(row, data); body = { sync_queued: false } }
    else if (path === '/api/projects/archives' && req.method() === 'POST') {
      creates.push(req.postDataJSON())
      if (rejectCreate) return route.fulfill({ status: 422, json: { detail: { code: 'ARCHIVE_UNIQUE_CONFLICT', field_key: 'project_code', message: '测试编号已存在' } } })
      await new Promise(resolve => { releaseCreate = resolve })
      body = { id: 2 }
    }
    await route.fulfill({ json: body })
  })
  await page.goto(`${origin}/project/archive`)
  await expect(page.getByRole('button', { name: '编辑', exact: true })).toBeVisible()
  assert.equal(regionRequests, 1)
  await expect(page.locator('.ag-header-cell[col-id="product_line_id"]')).toHaveCount(0)
  await page.getByRole('button', { name: '新增档案', exact: true }).click()
  const create = page.locator('.pms-form-drawer:visible')
  await expect(create).toContainText('当前用户')
  await expect(create).toContainText('合同与交付')
  await expect(create).toContainText('项目联系信息')
  assert.equal(Math.round((await create.boundingBox()).width), 492)
  async function assertCreateControlWidths() {
    const measurements = await create.locator('.pms-form-field').evaluateAll(fields => fields.map(field => {
      const section = field.closest('section').getBoundingClientRect()
      const fieldBox = field.getBoundingClientRect()
      const label = field.querySelector('.pms-form-field__label').getBoundingClientRect()
      const control = field.querySelector('.pms-form-control').getBoundingClientRect()
      return { label: field.querySelector('label').textContent.trim(),
        fullRow: Math.abs(fieldBox.width - section.width) < 2,
        fillsTrack: Math.abs(control.right - fieldBox.right) < 2 && control.width >= fieldBox.width - label.width - 13 }
    }))
    assert.ok(measurements.every(item => item.fullRow && item.fillsTrack), JSON.stringify(measurements))
    const manager = create.locator('.pms-form-field:has(#archive-create-manager_id)')
    const selectedLabel = manager.locator('.el-select__selected-item').filter({ hasText: '当前用户' })
    await expect(selectedLabel).toBeVisible()
    assert.ok((await selectedLabel.boundingBox()).width > 60)
  }
  await assertCreateControlWidths()
  await expect(create.locator('#archive-create-address_province')).toBeVisible()
  await expect(create.locator('#archive-create-address_city')).toHaveCount(0)
  await expect(create.locator('#archive-create-address_detail')).toHaveCount(0)
  await create.locator('.el-select:has(#archive-create-address_province)').click()
  await page.getByRole('option', { name: '天津市', exact: true }).click()
  await expect(create.locator('#archive-create-address_city')).toBeVisible()
  await expect(create.locator('#archive-create-address_detail')).toHaveCount(0)
  await create.locator('.el-select:has(#archive-create-address_city)').click()
  await page.getByRole('option', { name: '天津市辖区', exact: true }).click()
  await expect(create.locator('#archive-create-address_detail')).toBeVisible()
  await create.locator('#archive-create-address_detail').fill('新地址')
  await create.getByRole('button', { name: '创建', exact: true }).click()
  await expect(create.locator('.el-form-item__error')).toHaveCount(2)
  assert.equal(creates.length, 0)
  for (const key of ['contract_signed_date', 'contract_ship_date']) {
    await create.locator(`#archive-create-${key}`).fill('2026-09-20')
    await create.locator(`#archive-create-${key}`).press('Tab')
  }
  await create.locator('#archive-create-project_code').fill('ARCH-CREATE')
  await create.getByRole('button', { name: '创建', exact: true }).click()
  await expect(create).toContainText('测试编号已存在')
  await expect(create.locator('#archive-create-project_code')).toHaveValue('ARCH-CREATE')
  assert.equal(creates[0].manager_id, 42)
  assert.equal(creates[0].contract_signed_date, '2026-09-20')
  await create.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.locator('.el-message-box')).toContainText('未保存')
  await page.locator('.el-message-box').getByRole('button', { name: '取消', exact: true }).click()
  await expect(create).toBeVisible()
  rejectCreate = false
  await create.getByRole('button', { name: '创建', exact: true }).click()
  await expect.poll(() => creates.length).toBe(2)
  await expect(create.locator('#archive-create-project_code')).toBeDisabled()
  await expect(create.locator('#archive-create-contract_ship_date')).toBeDisabled()
  await expect(create.locator('#archive-create-manager_id')).toBeDisabled()
  await expect(create.locator('#archive-create-address_detail')).toBeDisabled()
  releaseCreate()
  await expect(create).toHaveCount(0)

  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const drawer = page.locator('.archive-edit-drawer')
  await expect(drawer.getByRole('button', { name: '编辑负责人', exact: true })).toHaveText('原负责人')
  await expect(drawer.getByRole('button', { name: '编辑产品线', exact: true })).toHaveText('Bench')
  await expect(drawer.getByRole('button', { name: '编辑省份', exact: true })).toHaveText('北京市')
  await drawer.getByRole('button', { name: '编辑省份', exact: true }).click()
  await drawer.locator('#archive-drawer-address_province').click()
  await page.getByRole('option', { name: '天津市', exact: true }).click()
  await expect(drawer.getByRole('button', { name: '编辑详细地址', exact: true })).toHaveCount(0)
  await drawer.locator('#archive-drawer-address_province').press('Escape')
  await expect(drawer.getByRole('button', { name: '编辑省份', exact: true })).toHaveText('北京市')
  await expect(drawer.getByRole('button', { name: '编辑城市', exact: true })).toHaveText('北京市辖区')
  await expect(drawer.getByRole('button', { name: '编辑详细地址', exact: true })).toHaveText('测试地址')
  await expect(drawer.locator('.el-form-item__error')).toHaveCount(0)
  await drawer.getByRole('button', { name: '编辑省份', exact: true }).click()
  await drawer.locator('#archive-drawer-address_province').click()
  await page.getByRole('option', { name: '天津市', exact: true }).click()
  await drawer.getByRole('button', { name: /保存修改/ }).click()
  await expect(drawer).toContainText('请完整填写省份、城市和详细地址')
  assert.equal(writes.length, 0)
  await drawer.getByRole('button', { name: '编辑城市', exact: true }).click()
  await drawer.locator('#archive-drawer-address_city').click()
  await page.getByRole('option', { name: '天津市辖区', exact: true }).click()
  await drawer.getByRole('button', { name: '编辑详细地址', exact: true }).click()
  await drawer.locator('#archive-drawer-address_detail').fill('新地址')
  await drawer.getByRole('button', { name: /保存修改/ }).click()
  await expect.poll(() => writes.length).toBe(1)
  assert.deepEqual(writes[0], { address_province: '12', address_city: '1201', address_detail: '新地址' })
  await expect(page.locator('.el-message--success').filter({ hasText: /^已保存$/ })).toBeVisible()
  assert.equal(regionRequests, 1)
  await expect(drawer.getByRole('button', { name: /保存修改/ })).toBeDisabled()
  await expect(drawer.locator('.el-form-item__error')).toHaveCount(0)
  await expect(page.locator('.el-message')).toHaveCount(0)
  await page.screenshot({ path: '/tmp/pms-archive-expansion-inline.png' })
  await drawer.getByRole('button', { name: '关闭档案编辑', exact: true }).click()
  await page.getByRole('button', { name: '添加筛选', exact: true }).click()
  await page.locator('.pms-list-filter-control--field').click()
  await page.getByRole('option', { name: '省份', exact: true }).click()
  await page.locator('.pms-list-filter-control--select-value').click()
  await page.getByRole('option', { name: '天津市', exact: true }).click()
  await expect.poll(() => JSON.parse(queries.at(-1).filters)[0]?.value).toBe('12')
  assert.equal(JSON.parse(queries.at(-1).filters)[0].field, 'address_province')
  await page.getByRole('button', { name: '清空筛选', exact: true }).click()
  await page.getByRole('button', { name: '打开项目档案列设置', exact: true }).click()
  const picker = page.locator('.column-picker-panel:visible')
  for (const label of ['产品线', '省份', '城市']) {
    await picker.getByRole('textbox', { name: '搜索列字段', exact: true }).fill(label)
    await picker.locator('.hidden-field .el-checkbox').click()
    await expect(picker.getByRole('checkbox', { name: `显示${label}列`, exact: true })).toBeChecked()
  }
  await picker.getByRole('textbox', { name: '搜索列字段', exact: true }).fill('')
  await picker.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.locator('.ag-cell[col-id="product_line_id"]')).toHaveText('Bench')
  await expect(page.locator('.ag-cell[col-id="address_province"]')).toHaveText('天津市')
  await expect(page.locator('.ag-cell[col-id="address_city"]')).toHaveText('天津市辖区')
  await page.reload()
  await expect(page.locator('.ag-cell[col-id="product_line_id"]')).toHaveText('Bench')
  assert.equal(regionRequests, 2)
  await page.getByRole('button', { name: '新增档案', exact: true }).click()
  for (const [width, height] of [[1366, 768], [390, 844]]) {
    await page.setViewportSize({ width, height })
    await expect(create).toBeVisible()
    await expect.poll(async () => {
      const bounds = await create.boundingBox()
      return bounds.x >= 0 && bounds.x + bounds.width <= width && bounds.y + bounds.height <= height
    }).toBe(true)
    await assertCreateControlWidths()
    const footer = await create.getByRole('button', { name: '创建', exact: true }).boundingBox()
    assert.ok(footer.y + footer.height <= height)
    await page.screenshot({ path: `/tmp/pms-archive-expansion-create-${width}.png` })
  }
  assert.deepEqual(errors, [])
  console.log('Archive browser passed: required/new vs old, manager, date payload, failed create/draft, discard guard, province/city Escape and save, one region request, User B width')
} finally { await browser.close() }
