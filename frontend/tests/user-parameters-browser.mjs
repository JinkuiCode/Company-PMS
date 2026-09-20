import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
let page
try {
  page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
  page.setDefaultTimeout(10000)
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  let mustChange = false
  let created, reset = 0, parameterSave
  const saves = []
  const users = [{ id: 2, username: 'A001', real_name: '测试员工', email: 'staff@aelsystem.com', mobile: '', dept_id: 1, status: 1, role_ids: [1], role_names: ['操作员'] }]
  let parameter = { code: 'user.initial_password', name: '用户初始密码', group: '账号安全', description: '用于新建用户和管理员重置密码', sensitive: true, configured: false, version: 0, value: null }
  let permissions = ['system:user:view', 'system:user:add', 'system:user:edit', 'system:user:reset-password', 'system:parameter:view', 'system:parameter:edit']
  await page.addInitScript(() => localStorage.setItem('access_token', 'ui-test'))
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method()
    if (url.origin !== 'http://127.0.0.1:5174') return route.abort()
    if (!path.startsWith('/api/')) return route.continue()
    let body = []
    if (path === '/api/auth/me') body = { id: 1, username: 'admin-test', real_name: '测试管理员', home_path: '/system/user', must_change_password: mustChange, permissions: mustChange ? [] : permissions }
    else if (path === '/api/my-menus') body = [{ id: 11, path: '/system/user', menu_name: '用户管理', menu_type: 'C', icon: 'User', children: [] }, { id: 18, path: '/system/parameter', menu_name: '参数设置', menu_type: 'C', icon: 'Setting', children: [] }]
    else if (path === '/api/users' && method === 'GET') body = { items: users, total: users.length }
    else if (path === '/api/users' && method === 'POST') { created = route.request().postDataJSON(); body = { id: 3 } }
    else if (path === '/api/users/2' && method === 'PUT') { saves.push(route.request().postDataJSON()); body = users[0] }
    else if (path === '/api/users/2/reset-password') { reset++; body = { message: '已重置' } }
    else if (path === '/api/users/oa-options') { assert.equal(url.searchParams.get('keyword'), '004'); body = { items: [{ username: 'A0045', real_name: '待开户员工' }], total: 1 } }
    else if (path === '/api/depts/tree') body = [{ id: 1, dept_name: '技术部', children: [] }]
    else if (path === '/api/roles/options') body = [{ id: 1, role_name: '操作员', status: 1 }]
    else if (path === '/api/parameters') body = { items: [parameter, { code: 'test.display', name: '显示参数', group: '界面', description: '仅 mock 分组测试', sensitive: false, configured: true, version: 1, value: 'compact' }] }
    else if (path === '/api/parameters/user.initial_password') { parameterSave = route.request().postDataJSON(); parameter = { ...parameter, configured: true, version: 1 }; body = parameter }
    else if (path === '/api/auth/change-password') { const data = route.request().postDataJSON(); assert.equal(data.new_password, data.confirm_password); mustChange = false; body = { access_token: 'changed-token', must_change_password: false } }
    await route.fulfill({ json: body })
  })
  await page.goto('http://127.0.0.1:5174/system/user')
  await page.getByRole('button', { name: '新增用户', exact: true }).click()
  let drawer = page.locator('.pms-form-drawer').filter({ has: page.locator('#user-real-name') })
  await expect(drawer).toBeVisible()
  await expect(drawer.getByRole('textbox', { name: '邮箱', exact: true })).toHaveValue('@aelsystem.com')
  await expect(drawer.locator('input[type=password]')).toHaveCount(0)
  await drawer.getByRole('button', { name: '创建用户' }).click()
  await expect(drawer.getByText('请输入账号（工号）', { exact: true }).first()).toBeVisible()
  await expect(drawer.locator('#user-username')).toHaveAttribute('aria-invalid', 'true')
  await expect(drawer.locator('#user-username')).toHaveAttribute('aria-required', 'true')
  await expect(drawer.locator('#user-username')).toHaveAttribute('aria-describedby', 'user-username-error')
  await expect(drawer.locator('#user-username')).toBeFocused()
  await page.screenshot({ path: '/tmp/pms-user-B-errors.png' })
  // Initial empty query is fulfilled locally without checking keyword; search request below is asserted.
  await page.route('**/api/users/oa-options?keyword=&**', route => route.fulfill({ json: { items: [], total: 0 } }))
  await drawer.getByRole('button', { name: '引用 OA' }).click()
  const picker = page.getByRole('dialog', { name: '引用 OA 员工' })
  await picker.getByRole('textbox', { name: '搜索 OA 员工' }).fill('004')
  await picker.getByRole('button', { name: '选择', exact: true }).click()
  await expect(picker).toBeHidden()
  await expect(drawer.getByRole('textbox', { name: '账号（工号）' })).toHaveValue('A0045')
  await drawer.getByRole('textbox', { name: '邮箱', exact: true }).fill('person@aelsystem.com')
  const geometry = await drawer.evaluate(el => ({ width: el.getBoundingClientRect().width, footerBottom: el.querySelector('.el-drawer__footer').getBoundingClientRect().bottom, height: innerHeight }))
  assert.equal(Math.round(geometry.width), 492)
  assert.ok(geometry.footerBottom <= geometry.height)
  await page.screenshot({ path: '/tmp/pms-user-B-1366.png' })
  await drawer.getByRole('button', { name: '创建用户' }).click()
  await expect.poll(() => created?.username).toBe('A0045')
  assert.equal('password' in created, false)
  assert.equal(created.email, 'person@aelsystem.com')
  await expect(drawer).toBeHidden()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(drawer.getByRole('textbox', { name: '账号（工号）' })).toBeDisabled()
  await drawer.locator('#user-real-name').fill('未保存草稿')
  await drawer.getByRole('button', { name: '重置密码', exact: true }).click()
  await page.getByRole('button', { name: '确认重置' }).click()
  await expect.poll(() => reset).toBe(1)
  assert.equal(saves.length, 0, 'reset must not save profile drafts')
  await expect(drawer.locator('#user-real-name')).toHaveValue('未保存草稿')
  await drawer.getByRole('button', { name: '保存', exact: true }).click()
  await expect.poll(() => saves.length).toBe(1)
  assert.equal(saves[0].real_name, '未保存草稿')
  await expect(drawer).toBeHidden()
  // Establish an actual SPA history entry, then test cancel and confirm on Back.
  await page.getByRole('menuitem', { name: '参数设置' }).click()
  await page.getByRole('menuitem', { name: '用户管理' }).click()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await drawer.locator('#user-real-name').fill('后退保留草稿')
  await page.evaluate(() => history.back())
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(page.getByRole('button', { name: '继续编辑', exact: true })).toHaveCount(0)
  await expect(page).toHaveURL(/\/system\/user$/)
  await expect(drawer.locator('#user-real-name')).toHaveValue('后退保留草稿')
  await page.evaluate(() => history.back())
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page).toHaveURL(/\/system\/parameter$/)
  assert.equal(saves.length, 1)
  const group = page.getByRole('combobox', { name: '参数分组' })
  await group.press('ArrowDown')
  await page.getByRole('option', { name: '界面', exact: true }).click()
  await expect(page.getByText('用户初始密码', { exact: true })).toHaveCount(0)
  await expect(page.getByText('显示参数', { exact: true })).toBeVisible()
  await group.press('ArrowDown')
  await page.getByRole('option', { name: '账号安全', exact: true }).click()
  await expect(page.getByText('显示参数', { exact: true })).toHaveCount(0)
  await page.getByRole('textbox', { name: '搜索参数', exact: true }).fill('不存在')
  await expect(page.getByText('用户初始密码', { exact: true })).toHaveCount(0)
  await page.getByRole('textbox', { name: '搜索参数', exact: true }).fill('')
  await page.getByRole('button', { name: '修改', exact: true }).click()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  const secret = page.getByRole('textbox', { name: '新参数值' })
  await expect(secret).toHaveAttribute('aria-invalid', 'true')
  await expect(secret).toHaveAttribute('aria-required', 'true')
  await expect(secret).toHaveAttribute('aria-describedby', 'parameter-user.initial_password-error')
  await expect(secret).toBeFocused()
  await page.getByRole('textbox', { name: '新参数值' }).fill('test-only')
  await expect(secret).toHaveAttribute('type', 'password')
  await page.getByRole('button', { name: /password|密码/i }).click()
  await expect(secret).toHaveAttribute('type', 'text')
  await expect(secret).toHaveValue('test-only')
  await page.getByRole('button', { name: /password|密码/i }).click()
  await expect(secret).toHaveAttribute('type', 'password')
  await page.screenshot({ path: '/tmp/pms-parameter-A.png' })
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect.poll(() => parameterSave?.version).toBe(0)
  await expect(page.getByText('已设置 · 不回显')).toBeVisible()
  await expect(page.locator('input[type=password]')).toHaveCount(0)
  await page.getByRole('button', { name: '修改', exact: true }).click()
  await expect(secret).toHaveValue('')
  await expect(secret).toHaveAttribute('type', 'password')
  await expect(page.getByText('已设置 · 不回显')).toBeVisible()
  await page.getByRole('button', { name: '取消', exact: true }).click()
  mustChange = true
  await page.goto('http://127.0.0.1:5174/system/user')
  await expect(page).toHaveURL(/\/change-password$/)
  await expect(page.locator('#new-password')).toHaveAttribute('aria-describedby', 'new-password-hint')
  await page.getByRole('button', { name: '保存并继续' }).click()
  await expect(page.locator('#new-password')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator('#new-password')).toHaveAttribute('aria-required', 'true')
  await expect(page.locator('#new-password')).toHaveAttribute('aria-describedby', 'new-password-hint new-password-error')
  await expect(page.locator('#new-password')).toBeFocused()
  await page.getByRole('textbox', { name: '新密码', exact: true }).fill('example8')
  await page.getByRole('button', { name: '保存并继续' }).click()
  await expect(page.locator('#confirm-password')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator('#confirm-password')).toHaveAttribute('aria-describedby', 'confirm-password-error')
  await expect(page.locator('#confirm-password')).toBeFocused()
  await page.getByRole('textbox', { name: '确认新密码', exact: true }).fill('example8')
  await page.getByRole('button', { name: '保存并继续' }).click()
  await expect(page).toHaveURL(/\/system\/user$/)
  permissions = permissions.filter(p => p !== 'system:user:reset-password')
  await page.reload()
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(page.getByRole('button', { name: '重置密码', exact: true })).toHaveCount(0)
  await page.setViewportSize({ width: 1600, height: 900 })
  await expect.poll(() => drawer.evaluate(el => Math.round(el.getBoundingClientRect().right))).toBe(1584)
  await page.screenshot({ path: '/tmp/pms-user-B-1600.png', animations: 'disabled' })
  await drawer.getByRole('button', { name: '取消', exact: true }).click()
  permissions = ['system:user:view', 'system:user:reset-password']
  await page.reload()
  await page.getByRole('button', { name: '查看', exact: true }).click()
  await expect(drawer.locator('#user-real-name')).toBeDisabled()
  await expect(drawer.getByRole('button', { name: '保存', exact: true })).toHaveCount(0)
  await drawer.getByRole('button', { name: '重置密码', exact: true }).click()
  await page.getByRole('button', { name: '确认重置' }).click()
  await expect.poll(() => reset).toBe(2)
  assert.equal(saves.length, 1, 'reset-only permission must not save a profile')
  assert.deepEqual(errors, [])
  console.log('user/parameter browser passed: OA, email, separate save/reset, reset-only permission, route draft guard, input a11y/focus, group/search, new secret reveal, stored secret masked, forced password redirect; 1366/1600 drawer; all API mocked')
} catch (e) {
  if (page) { await page.screenshot({ path: '/tmp/pms-user-test-failure.png' }); console.log(await page.locator('body').innerText()) }
  throw e
} finally { await browser.close() }
