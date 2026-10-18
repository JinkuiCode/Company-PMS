import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'

const base = process.env.PMS_PROGRESS_TEST_BASE || 'http://127.0.0.1:5174'
assert.equal(new URL(base).hostname, '127.0.0.1')
const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
  page.setDefaultTimeout(8000)
  const errors = [], writes = [], optionRequests = []
  let failOptions = false, failSave = false, staleOptions = false
  const depts = [
    { id: 1, dept_name: '第一部门', parent_id: 0, leader_id: null, sort: 0, status: 1, children: [] },
    { id: 2, dept_name: '第二部门', parent_id: 0, leader_id: null, sort: 1, status: 1, children: [] },
    { id: 3, dept_name: '历史部门', parent_id: 0, leader_id: 3, leader_label: '历史负责人（A003）', sort: 2, status: 1, children: [] },
  ]
  page.on('pageerror', e => errors.push(e.message))
  await page.addInitScript(() => localStorage.setItem('access_token', 'mock-only'))
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (url.origin !== base) return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let body = []
    if (path === '/api/auth/me') body = { id: 1, username: 'mock', permissions: ['system:user:view', 'system:user:add', 'system:user:edit'] }
    else if (path === '/api/users') body = { items: [], total: 0 }
    else if (path === '/api/depts/tree') body = depts
    else if (path === '/api/users/options') {
      optionRequests.push(url.search)
      const stale = staleOptions
      staleOptions = false
      await new Promise(resolve => setTimeout(resolve, stale ? 1200 : 180))
      if (failOptions) return route.fulfill({ status: 500, json: { detail: '人员选项加载失败' } })
      body = stale ? [{ id: 9, username: 'OLD', real_name: '过期用户', dept_id: 1 }] : [
        { id: 1, username: 'A001', real_name: '同名', dept_id: 1 },
        { id: 2, username: 'A002', real_name: '同名', dept_id: 2 },
      ]
    }
    if (['POST', 'PUT'].includes(route.request().method())) {
      const data = route.request().postDataJSON()
      writes.push({ path, data })
      if (failSave) return route.fulfill({ status: 422, json: { detail: '模拟保存失败' } })
      if (path.startsWith('/api/depts/')) Object.assign(depts.find(dept => dept.id === Number(path.split('/').at(-1))), data)
      body = { id: 4 }
    }
    return route.fulfill({ json: body })
  })
  await page.goto(base + '/system/user')
  const drawer = page.locator('.pms-form-drawer:visible')
  const leader = drawer.locator('[aria-label="部门负责人"] .el-select__wrapper')
  async function edit(name) {
    await page.getByRole('tree').getByText(name, { exact: true }).click({ button: 'right' })
    await page.locator('.context-menu').getByText('编辑部门', { exact: true }).click()
    await expect(drawer).toBeVisible()
  }
  async function selectLeader() {
    await leader.click()
    await expect(page.getByRole('option', { name: '同名（A001）', exact: true })).toBeVisible()
    await page.getByRole('option', { name: '同名（A002）', exact: true }).click()
  }
  await page.getByRole('tree').getByText('第一部门', { exact: true }).click()
  await edit('第一部门')
  await expect(leader).toBeVisible()
  await expect(drawer.getByRole('button', { name: '保存', exact: true })).toBeEnabled()
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer.getByText('请选择部门负责人', { exact: true })).toBeVisible()
  assert.equal(writes.length, 0)
  await selectLeader()
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  assert.equal(writes.at(-1).data.leader_id, 2)
  await edit('第二部门')
  await selectLeader()
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  assert.equal(depts[0].leader_id, depts[1].leader_id)
  assert.ok(optionRequests.every(query => !query.includes('dept_id')))
  await edit('第一部门')
  await expect(leader).toContainText('同名（A002）')
  failSave = true
  await drawer.getByRole('textbox', { name: '部门名称', exact: true }).fill('保留草稿')
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('模拟保存失败', { exact: true })).toBeVisible()
  await expect(drawer.getByRole('textbox', { name: '部门名称', exact: true })).toHaveValue('保留草稿')
  await expect(leader).toContainText('同名（A002）')
  failSave = false
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
  await page.getByRole('dialog', { name: '未保存修改', exact: true }).getByRole('button', { name: '确定', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  await edit('历史部门')
  await leader.click()
  await expect(page.getByRole('option', { name: '历史负责人（A003）（不可选）', exact: true })).toHaveAttribute('aria-disabled', 'true')
  await page.keyboard.press('Escape')
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
  failOptions = true
  await edit('第一部门')
  await expect(drawer.getByText('无法加载负责人选项，请重试', { exact: true })).toBeVisible()
  await expect(drawer.getByRole('button', { name: '保存', exact: true })).toBeDisabled()
  failOptions = false
  await drawer.getByRole('button', { name: '重试', exact: true }).click()
  await expect(drawer.getByRole('button', { name: '保存', exact: true })).toBeEnabled()
  await expect(leader).toContainText('同名（A002）')
  await page.screenshot({ path: '/tmp/pms-department-leader-1366.png' })
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
  staleOptions = true
  await edit('第一部门')
  await expect(drawer.getByRole('button', { name: '保存', exact: true })).toBeDisabled()
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
  await edit('第二部门')
  await expect(drawer.getByRole('button', { name: '保存', exact: true })).toBeEnabled()
  await leader.click()
  await expect(page.getByRole('option', { name: '同名（A002）', exact: true })).toBeVisible()
  await expect(page.getByRole('option', { name: '过期用户（OLD）', exact: true })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
  await page.getByRole('button', { name: '说明', exact: true }).click()
  await expect(page.getByText('跨部门兼任', { exact: true })).toBeVisible()
  const popupPromise = page.waitForEvent('popup')
  await page.getByRole('link', { name: '新页签打开', exact: true }).click()
  const popup = await popupPromise
  await expect(popup.getByRole('heading', { name: '用户与部门管理', exact: true })).toBeVisible()
  assert.ok(popup.url().includes('/page-guide/users#'))
  await popup.close()
  assert.deepEqual(errors, [])
  console.log('Department leader browser: required, cross-dept, shared leader, draft/error, guide passed')
} finally { await browser.close() }
