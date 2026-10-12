import assert from 'node:assert/strict'
import { mkdirSync } from 'node:fs'
import { createServer } from 'vite'
import { chromium, expect } from '@playwright/test'

const server = await createServer({ server: { host: '127.0.0.1', port: 0 }, cacheDir: '../.runtime/page-guide-vite-cache' })
let browser, page
const errors = [], businessCalls = []
const field = (key, label, value_type = 'text') => ({ key, label, value_type, type: value_type, width: 140, group: '基本信息' })
const organizations = [{ value: 2, label: '8吋Bench半导体项目产品线' }, { value: 3, label: 'Single单片清洗设备产品线' }]
const identity = [field('product_line_name', '产品线'), field('project_code', '项目编码')]
const purchase = { organizations, fields: [...identity, field('bill_no', '申请单编号'), field('progress', '采购进度')], overview_fields: [...identity, field('completion_rate', '申请行入库率', 'number'), field('conversion_rate', '申请行转单率', 'number'), field('total_lines', '申请行数', 'number')], query_fields: [], column_filter_fields: [], overview_column_filter_fields: [], document_status_labels: { C: '已审核' }, progress_labels: { complete: '已完成' }, start_date: '2026-01-01' }
const inventory = { organizations, fields: [identity[0], field('Stock', '仓库'), field('MaterialName', '物料名称'), field('FBaseQty', '基本单位数量', 'number')], query_fields: [], column_filter_fields: [] }
const stock = { organizations, fields: [identity[0], field('material_code', '物料编码'), field('bill_no', '单据编号'), field('income_qty', '收入', 'number')], query_fields: [], column_filter_fields: [] }
const output = '../outputs/page-guide-20261012'
mkdirSync(output, { recursive: true })

try {
  await server.listen()
  const base = `http://127.0.0.1:${server.httpServer.address().port}`
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') console.error('Browser console:', message.text()) })
  page.on('requestfailed', request => console.error('Request failed:', request.url(), request.failure()?.errorText))
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'isolated-guide-test')
    localStorage.setItem('pms:purchase-overview:v1:991', JSON.stringify({ visible: ['project_name', 'project_code'], columns: [{ colId: 'project_name', width: 199 }, { colId: 'project_code', width: 133 }] }))
    localStorage.setItem('pms:inventory-report:v1:991', JSON.stringify({ visible: ['Organization', 'Stock'], columns: [{ colId: 'Organization', width: 199 }, { colId: 'Stock', width: 133 }] }))
    localStorage.setItem('pms:stock-detail:v1:991', JSON.stringify({ visible: ['material_code'], columns: [{ colId: 'material_code', width: 155 }] }))
  })
  await page.context().route('**/api/**', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (!path.startsWith('/api/')) return route.continue()
    let json = []
    if (path === '/api/auth/me') json = { id: 991, username: 'guide-test', real_name: '说明验收', permissions: ['project:archive:view', 'report:purchase:view', 'report:purchase:list', 'report:inventory:view', 'report:inventory:list', 'report:stock-detail:view', 'report:stock-detail:list'], role_codes: [], data_scope: 4 }
    else if (path.endsWith('/metadata')) json = path.includes('inventory') ? inventory : path.includes('stock-detail') ? stock : purchase
    else if (path === '/api/product-lines/options') json = { options: [{ id: 2, label: '8吋Bench' }, { id: 3, label: 'Single' }], label_map: { 2: '8吋Bench', 3: 'Single' } }
    else if (path.includes('/dicts/code/')) json = { items: [], all_items: [], label_map: {} }
    else if (path === '/api/projects/archives/fields') json = { items: [] }
    else if (path === '/api/users/options') json = []
    else if (path.endsWith('/reference-options')) json = { items: [{ value: 20, code: 'A-202503', label: '测试项目', product_line_name: '8吋Bench' }], total: 1, has_more: false }
    else if (path.endsWith('/options')) json = { items: [{ value: 10, label: '研发仓' }], total: 1, has_more: false }
    else if (path === '/api/projects/archives/list') json = { items: [], total: 0 }
    else if (['/api/reports/inventory', '/api/reports/stock-detail', '/api/reports/purchase', '/api/reports/purchase/overview'].includes(path)) { businessCalls.push(path); json = { items: [], total: 0 } }
    await route.fulfill({ json })
  })
  const dialog = surface => surface.getByRole('dialog', { name: /说明$/ })
  const openGuide = async (surface, label) => {
    const button = surface.getByRole('button', { name: '说明', exact: true })
    await button.click()
    await expect(dialog(surface)).toBeVisible()
    await expect(dialog(surface).getByText(label, { exact: true })).toBeVisible()
    await expect(dialog(surface).getByRole('button', { name: '操作说明' })).toHaveAttribute('aria-pressed', 'true')
    await dialog(surface).getByRole('button', { name: '字段逻辑' }).click()
    await expect(dialog(surface).locator('tbody tr')).not.toHaveCount(0)
    await dialog(surface).getByRole('textbox', { name: '搜索说明' }).fill('不存在的说明')
    await expect(dialog(surface).getByText('没有匹配的说明')).toBeVisible()
    await dialog(surface).getByRole('textbox', { name: '搜索说明' }).fill('')
    await dialog(surface).getByRole('button', { name: '全部', exact: true }).click()
    return button
  }
  for (const [path, title, key] of [['/project/archive', '项目档案', 'archive'], ['/reports/purchase-progress', '采购进度查询', 'purchase'], ['/reports/inventory', '即时库存查询', 'inventory'], ['/reports/stock-detail', '物料收发明细', 'stock']]) {
    await page.goto(`${base}${path}`)
    const button = await openGuide(page, title)
    if (key === 'purchase') {
      await dialog(page).getByRole('textbox', { name: '搜索说明' }).fill('转单率')
      await expect(dialog(page).locator('tbody tr')).toHaveCount(1)
      await expect(dialog(page).locator('tbody')).toContainText('部分下单不计')
      await dialog(page).getByRole('button', { name: '总进度', exact: true }).click()
      const sourceUrl = page.url()
      await expect(dialog(page).getByRole('link', { name: '新页签打开' })).toBeVisible()
      const popupPromise = page.waitForEvent('popup')
      await dialog(page).getByRole('link', { name: '新页签打开' }).click()
      const popup = await popupPromise
      popup.on('pageerror', error => errors.push(error.message))
      await expect(popup.getByRole('heading', { name: '采购进度查询' })).toBeVisible()
      await expect(popup.getByRole('button', { name: '字段逻辑' })).toHaveAttribute('aria-pressed', 'true')
      await expect(popup.getByRole('textbox', { name: '搜索说明' })).toHaveValue('转单率')
      await expect(popup.getByRole('button', { name: '总进度', exact: true })).toHaveAttribute('aria-pressed', 'true')
      await expect(popup.locator('tbody tr')).toHaveCount(1)
      await expect(popup.locator('.ag-root, .el-aside')).toHaveCount(0)
      assert.equal(await popup.evaluate(() => window.opener), null)
      assert.equal(page.url(), sourceUrl)
      await expect(dialog(page).getByRole('textbox', { name: '搜索说明' })).toHaveValue('转单率')
      await popup.reload()
      await expect(popup.getByRole('textbox', { name: '搜索说明' })).toHaveValue('转单率')
      await popup.screenshot({ path: `${output}/purchase-new-tab.png` })
      await popup.close()
      await dialog(page).getByRole('textbox', { name: '搜索说明' }).fill('')
      await dialog(page).getByRole('button', { name: '总进度', exact: true }).click()
      await expect(dialog(page).locator('tbody tr')).toHaveCount(3)
      await dialog(page).getByRole('button', { name: '全部', exact: true }).click()
    }
    if (key === 'inventory') await expect(dialog(page).locator('tbody th').filter({ hasText: /^组织$/ })).toHaveCount(0)
    if (key !== 'purchase') {
      const popupPromise = page.waitForEvent('popup')
      await dialog(page).getByRole('link', { name: '新页签打开' }).click()
      const popup = await popupPromise
      await expect(popup.getByRole('heading', { name: title })).toBeVisible()
      assert.equal(new URL(popup.url()).pathname, `/page-guide/${key}`)
      await expect(popup.locator('tbody tr')).not.toHaveCount(0)
      await expect(popup.locator('.el-aside, .ag-root')).toHaveCount(0)
      await popup.close()
    }
    await page.screenshot({ path: `${output}/${key}-implemented.png` })
    await dialog(page).getByRole('textbox', { name: '搜索说明' }).press('Escape')
    await expect(dialog(page)).not.toBeVisible()
    await expect(button).toBeFocused()
    if (key !== 'archive') {
      const headers = page.locator('.ag-header-cell:visible')
      await expect(headers.first()).toHaveAttribute('col-id', 'product_line_name')
      await expect(page.locator('.ag-header-cell[col-id="project_name"]')).toHaveCount(0)
      await expect(page.locator('.ag-header-cell[col-id="Organization"]')).toHaveCount(0)
    }
    const row = page.locator('.pms-query-workspace-fields>.pms-condition-row').first()
    await expect(row).toBeVisible()
    assert.equal(Math.round(await row.evaluate(e => e.getBoundingClientRect().width)), 326)
    const widths = await row.evaluate(e => getComputedStyle(e).gridTemplateColumns.split(' ').map(parseFloat))
    assert.deepEqual(widths, [96, 68, 132, 18])
    if (key === 'purchase') {
      await page.getByRole('button', { name: '明细进度', exact: true }).click()
      await openGuide(page, title)
      await dialog(page).getByRole('textbox', { name: '搜索说明' }).press('Escape')
    }
  }
  assert.deepEqual(businessCalls, [], '说明或页面加载不能触发报表查询')
  const oldScheme = [{ version:2, name:'旧方案验收', isDefault:true, preferences:{}, definitions:[
    { field:'keyword', shown:true, operator:'contains', value:'测试', valueEnd:null, schemaVersion:2 },
    { field:'organization_ids', shown:true, operator:'reference', value:[2,3], valueEnd:null, schemaVersion:2 },
    { field:'project_name', shown:true, operator:'equals', value:'旧名称', valueEnd:null, schemaVersion:2 },
  ] }]
  await page.goto(`${base}/reports/purchase-progress`)
  await page.evaluate(value=>localStorage.setItem('pms:query-workspace:v2:991:report-purchase-overview',JSON.stringify(value)), oldScheme)
  await page.reload()
  await expect(page.getByRole('alert').filter({hasText:'此方案包含已取消的字段'})).toBeVisible()
  await expect(page.getByRole('button',{name:'查询',exact:true})).toBeDisabled()
  assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('pms:query-workspace:v2:991:report-purchase-overview'))), oldScheme)
  await page.getByRole('button',{name:'方案设置',exact:true}).click()
  const settings=page.getByRole('dialog',{name:'查询方案设置'})
  await expect(settings).toBeVisible()
  await expect(settings.locator('[data-field="project_name"]')).toHaveCount(0)
  assert.equal(Math.round(await settings.getByRole('textbox',{name:'方案名称',exact:true}).evaluate(e=>e.closest('.pms-form-control').getBoundingClientRect().height)),32)
  await settings.getByRole('button',{name:'保存方案',exact:true}).click()
  await expect(settings).not.toBeVisible()
  await expect(page.locator('.pms-query-warning')).toHaveCount(0)
  await expect(page.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
  assert.ok(!(await page.evaluate(()=>JSON.parse(localStorage.getItem('pms:query-workspace:v2:991:report-purchase-overview'))))[0].definitions.some(d=>d.field==='project_name'))
  const reference=page.locator('.pms-query-workspace-fields [data-field="organization_ids"] .pms-condition-reference')
  await expect(reference.locator('small')).toHaveText('2 条')
  assert.equal(Math.round(await reference.evaluate(e=>e.getBoundingClientRect().height)),24)
  const assertReferenceFits=async surface=>{
    const box=surface.locator('.pms-query-workspace-fields [data-field="organization_ids"] .pms-condition-reference')
    await expect(box.locator('small')).toHaveText('2 条')
    assert.ok(await box.evaluate(e=>{const r=e.getBoundingClientRect();return Array.from(e.children).every(c=>c.getBoundingClientRect().right<=r.right+1)}),'引用摘要和计数不得超出值框')
  }
  await assertReferenceFits(page)
  // A real iframe boundary, with the parent reserved for OA navigation.
  await page.route(`${base}/__guide-oa-host`, route => route.fulfill({ contentType: 'text/html; charset=utf-8', body: `<style>body{margin:0;background:#eef2f7;font:13px sans-serif}header{height:54px}aside{position:absolute;top:54px;width:184px;height:calc(100vh - 54px);background:#2460bf}iframe{position:absolute;left:184px;top:54px;width:calc(100vw - 184px);height:calc(100vh - 54px);border:0}</style><header>OA嵌入边界验证（模拟）</header><aside></aside><iframe title="PMS" src="${base}/reports/purchase-progress"></iframe>` }))
  for (const [width, height] of [[1366, 768], [1024, 600], [900, 420], [574, 520]]) {
    await page.setViewportSize({ width, height })
    await page.goto(`${base}/__guide-oa-host`)
    const frame = page.frameLocator('iframe')
    await assertReferenceFits(frame)
    await openGuide(frame, '采购进度查询')
    const bounds = await dialog(frame).evaluate(e => { const r = e.getBoundingClientRect(); return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: innerWidth, height: innerHeight, scroll: document.documentElement.scrollWidth } })
    assert.ok(bounds.left >= -1 && bounds.top >= -1 && bounds.right <= bounds.width + 1 && bounds.bottom <= bounds.height + 1, JSON.stringify(bounds))
    assert.ok(bounds.scroll <= bounds.width, JSON.stringify(bounds))
    const footer = await dialog(frame).locator('.pms-guide-footer').evaluate(e => ({ bottom:e.getBoundingClientRect().bottom, bodyBottom:e.closest('.el-dialog__body').getBoundingClientRect().bottom }))
    assert.ok(footer.bottom <= footer.bodyBottom + 1, JSON.stringify(footer))
    await expect(dialog(frame).getByRole('button', { name: '关闭此对话框' })).toBeVisible()
    const newTabLink = dialog(frame).getByRole('link', { name: '新页签打开' })
    const linkBounds = await newTabLink.evaluate(e => { const r=e.getBoundingClientRect(); return { left:r.left, right:r.right, top:r.top, bottom:r.bottom, width:innerWidth, height:innerHeight, controlHeight:r.height } })
    assert.equal(linkBounds.controlHeight, 24)
    assert.ok(linkBounds.left >= 0 && linkBounds.right <= linkBounds.width && linkBounds.bottom <= linkBounds.height)
    if (width === 1366 || width === 574) {
      const popupPromise = page.waitForEvent('popup')
      await newTabLink.click()
      const popup = await popupPromise
      await expect(popup.getByRole('heading', { name: '采购进度查询' })).toBeVisible()
      assert.equal(new URL(popup.url()).origin, base)
      assert.equal(new URL(popup.url()).pathname, '/page-guide/purchase')
      await expect(popup.locator('iframe, .el-aside, .ag-root')).toHaveCount(0)
      assert.ok(await popup.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
      await popup.close()
    }
    await page.screenshot({ path: `${output}/B-oa-${width}x${height}.png` })
    await dialog(frame).getByRole('textbox', { name: '搜索说明' }).press('Escape')
    await expect(dialog(frame)).not.toBeVisible()
  }
  assert.deepEqual(businessCalls, [], '独立说明页签不能触发报表查询')
  const anonymous = await browser.newContext()
  const anonymousCalls = []
  anonymous.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) anonymousCalls.push(request.url()) })
  const authPage = await anonymous.newPage()
  for (const key of ['archive', 'purchase', 'inventory', 'stock']) {
    await authPage.goto(`${base}/page-guide/${key}`)
    await expect(authPage).toHaveURL(`${base}/page-guide/${key}`)
    await expect(authPage.locator('.pms-guide-content')).toBeVisible()
    await authPage.reload()
    await expect(authPage.locator('.pms-guide-content')).toBeVisible()
  }
  assert.deepEqual(anonymousCalls, [], '静态说明页不访问认证或业务接口')
  await authPage.goto(`${base}/project/archive`)
  await expect(authPage).toHaveURL(`${base}/login`)
  await anonymous.close()
  const denied = await browser.newContext()
  await denied.addInitScript(() => localStorage.setItem('access_token', 'isolated-denied-test'))
  await denied.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    if (!path.startsWith('/api/')) return route.continue()
    return route.fulfill({ json: path === '/api/auth/me' ? { id: 992, username: 'denied', permissions: [], role_codes: [], data_scope: 4 } : [] })
  })
  const deniedPage = await denied.newPage()
  deniedPage.on('pageerror', error => console.error('Denied page error:', error.message))
  deniedPage.on('console', message => { if (message.type() === 'error') console.error('Denied console:', message.text()) })
  for (const key of ['archive', 'purchase', 'inventory', 'stock']) {
    await deniedPage.goto(`${base}/page-guide/${key}`)
    await expect(deniedPage).toHaveURL(`${base}/page-guide/${key}`)
    await expect(deniedPage.locator('.pms-guide-content')).toBeVisible()
  }
  await deniedPage.goto(`${base}/reports/purchase-progress`)
  await expect(deniedPage).toHaveURL(`${base}/403`)
  await denied.close()
  assert.deepEqual(errors, [])
  console.log('PASS page guide B: four page popups, state/reload/no opener, static public guides, protected business pages, no report queries, compact widths, OA iframe 1366/1024/900/574')
} catch (error) {
  console.error('Guide failure:', page?.url(), errors, await page?.locator('body').innerText())
  await page?.screenshot({ path: `${output}/implemented-failure.png` })
  throw error
} finally {
  await browser?.close()
  await server.close()
}
