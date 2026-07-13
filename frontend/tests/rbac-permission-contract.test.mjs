import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const read = path => readFileSync(resolve(root, path), 'utf8')

const authStore = read('src/stores/auth.ts')
const authApi = read('src/api/auth.ts')
const router = read('src/router/index.ts')
const request = read('src/utils/request.ts')
const appLayout = read('src/layout/AppLayout.vue')
const projectList = read('src/views/project/ProjectList.vue')
const projectArchive = read('src/views/project/ProjectArchive.vue')
const roleList = read('src/views/system/RoleList.vue')
const userList = read('src/views/system/UserList.vue')
const dictList = read('src/views/system/DataDictionaryList.vue')
const enumList = read('src/views/system/EnumList.vue')

for (const field of ['role_codes', 'permissions', 'data_scope', 'product_lines']) {
  assert.match(authApi, new RegExp(field), `/auth/me 类型应包含 ${field}`)
}
assert.match(authStore, /function hasPermission/)
assert.match(authStore, /function hasAnyPermission/)
assert.match(router, /permission:\s*'project:list:view'/)
assert.match(router, /permission:\s*'project:archive:view'/)
assert.match(router, /permission:\s*'system:role:view'/)
assert.match(router, /path:\s*'403'/)
assert.match(router, /path:\s*'\/admin\/token'[\s\S]*?permission:\s*'system:user:edit'/)
assert.doesNotMatch(router, /PUBLIC_PATHS\s*=\s*\[[^\]]*\/admin\/token/)
assert.doesNotMatch(router, /\bnext\(/, '路由守卫应返回跳转结果，不再调用已弃用的 next 回调')
assert.match(request, /status\s*===\s*403/)
assert.match(request, /fetchUser/)
assert.match(appLayout, /route\.meta\.permission/)
assert.match(appLayout, /router\.replace\('\/403'\)/)
assert.match(userList, /:draggable="hasPermission\('system:user:edit'\)"/)

for (const permission of ['project:list:add', 'project:list:edit', 'project:list:delete']) {
  assert.match(projectList, new RegExp(`hasPermission\\('${permission.replaceAll(':', '\\:')}'\\)`))
}
for (const permission of [
  'project:archive:add',
  'project:archive:edit',
  'project:archive:delete',
  'project:archive:sync',
]) {
  assert.match(projectArchive, new RegExp(`hasPermission\\('${permission.replaceAll(':', '\\:')}'\\)`))
}
for (const [source, prefix] of [
  [roleList, 'system:role'],
  [userList, 'system:user'],
  [enumList, 'system:enum'],
]) {
  for (const action of ['add', 'edit', 'delete']) {
    assert.match(source, new RegExp(`hasPermission\\('${prefix}:${action}'\\)`))
  }
}
assert.match(router, /permission:\s*'system:dict:view'/)
assert.doesNotMatch(dictList, /system:dict:(add|edit|delete)/)

console.log('rbac permission frontend contract passed')
