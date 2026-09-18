import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const browser = await chromium.launch({ headless: true, channel: 'msedge' })
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let home = '/project/archive'
  let permissions = ['project:archive:view', 'project:list:view', 'system:role:view', 'system:role:edit']
  let saved
  const menu = (id, path, permission, name) => ({ id, parent_id: 0, menu_name: name, menu_type: 'C', status: 1, visible: 1, path, permission_code: permission, children: [] })
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (!path.startsWith('/api/')) return route.continue()
    let body = []
    if (path === '/api/auth/me') body = { id: 1, username: 'test', real_name: '测试', home_path: home, permissions }
    else if (['/api/auth/login', '/api/auth/sso-login', '/api/auth/auto-login', '/api/sso/oa-password-login', '/api/sso/oa-login', '/api/sso/callback'].includes(path)) body = { access_token: 'test-token' }
    else if (path === '/api/roles' ) body = [{ id: 1, role_name: '测试角色', role_code: 'test', status: 1, data_scope: 4, home_menu_id: 1, home_priority: 10, ...saved }]
    else if (path === '/api/roles/1/menus') body = { menu_ids: [1, 2] }
    else if (path === '/api/roles/1' && route.request().method() === 'PUT') { saved = route.request().postDataJSON(); body = { msg: 'ok' } }
    else if (path === '/api/menus/tree') body = [menu(1, '/project/archive', 'project:archive:view', '项目档案'), menu(2, '/project/list', 'project:list:view', '项目进度')]
    else if (path.includes('/dicts/code/')) body = { items: [], all_items: [], label_map: {} }
    else if (path === '/api/auth/product-categories') body = { unrestricted: true }
    else if (path === '/api/projects/sheet-fields') body = { groups: [], policies: [] }
    else if (['/api/projects', '/api/projects/archives/list', '/api/projects/archives/fields'].includes(path)) body = { items: [], total: 0 }
    await route.fulfill({ json: body })
  })
  await page.goto('http://127.0.0.1:5174/login')
  await page.getByRole('textbox', { name: '用户名', exact: true }).fill('test')
  await page.getByRole('textbox', { name: '密码', exact: true }).fill('test-only')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/project\/archive$/)
  await page.evaluate(() => localStorage.removeItem('access_token'))
  await page.goto('http://127.0.0.1:5174/project/list?keyword=demo')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByRole('textbox', { name: '用户名', exact: true }).fill('test')
  await page.getByRole('textbox', { name: '密码', exact: true }).fill('test-only')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/project\/list\?keyword=demo$/)
  for (const path of ['/sso/start', '/sso/start?sso_login_id=test&ts=1&sign=test-only', '/sso/login?loginid=test', '/sso/callback?ticket=test-only']) {
    await page.goto('http://127.0.0.1:5174' + path)
    await expect(page).toHaveURL(/\/project\/archive$/)
  }
  await page.evaluate(() => { localStorage.removeItem('access_token'); localStorage.setItem('pms_remember_token', 'test-only') })
  await page.goto('http://127.0.0.1:5174/sso/start')
  await expect(page).toHaveURL(/\/project\/archive$/)
  await page.goto('http://127.0.0.1:5174/system/role')
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  const priority = dialog.getByRole('spinbutton', { name: '首页优先级', exact: true })
  const numberControl = dialog.locator('.el-input-number').filter({ has: page.locator('#role-home-priority') })
  const geometry = await numberControl.evaluate(el => {
    const input = el.querySelector('input').getBoundingClientRect()
    const minus = el.querySelector('.el-input-number__decrease').getBoundingClientRect()
    const plus = el.querySelector('.el-input-number__increase').getBoundingClientRect()
    return { inputLeft: input.left, inputRight: input.right, minusRight: minus.right, plusLeft: plus.left }
  })
  assert.ok(geometry.inputLeft >= geometry.minusRight && geometry.inputRight <= geometry.plusLeft, JSON.stringify(geometry))
  await priority.fill('0')
  await priority.press('Tab')
  await expect(numberControl.locator('.el-input-number__decrease')).toHaveClass(/is-disabled/)
  await numberControl.locator('.el-input-number__increase').click()
  await expect(priority).toHaveValue('1')
  await numberControl.locator('.el-input-number__decrease').click()
  await expect(priority).toHaveValue('0')
  await priority.fill('999')
  await priority.press('Tab')
  await expect(numberControl.locator('.el-input-number__increase')).toHaveClass(/is-disabled/)
  await dialog.locator('.el-select__wrapper').filter({ has: page.locator('#role-home') }).click()
  await page.getByRole('option', { name: '项目进度', exact: true }).click()
  await dialog.getByRole('spinbutton', { name: '首页优先级', exact: true }).fill('20')
  await page.screenshot({ path: '/tmp/pms-role-home.png' })
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect.poll(() => saved?.home_menu_id).toBe(2)
  assert.equal(saved.home_priority, 20)
  await page.reload()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(page.getByRole('spinbutton', { name: '首页优先级', exact: true })).toHaveValue('20')
  await page.screenshot({ path: '/tmp/pms-role-home-fixed.png' })
  home = '/system/user'
  permissions = []
  await page.goto('http://127.0.0.1:5174/')
  await expect(page).toHaveURL(/\/403$/)
  assert.deepEqual(errors, [])
  console.log('role home browser passed: normal/deep-link/JWT/OA/remember login, role save, denied home')
} finally { await browser.close() }
