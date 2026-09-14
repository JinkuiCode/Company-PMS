import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import ts from 'typescript'
import { ref, reactive } from 'vue'
import { AxiosError } from 'axios'

const source = readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
const compiled = ts.transpileModule(script + '\nexport { handleLogin, formRef, loading }', {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const require = createRequire(import.meta.url)
function mountHandler(login) {
  const errors = [], successes = [], routes = []
  const exports = {}
  vm.runInNewContext(compiled, {
    exports,
    require(name) {
      if (name === 'vue') return { ref, reactive }
      if (name === 'vue-router') return { useRouter: () => ({ push: path => routes.push(path) }) }
      if (name === 'element-plus') return { ElMessage: { error: m => errors.push(m), success: m => successes.push(m) } }
      if (name === '@element-plus/icons-vue') return { User: {}, Lock: {} }
      if (name === '@/stores/auth') return { useAuthStore: () => ({ login }) }
      if (name === '@/form-system') return { PmsTextControl: {} }
      return require(name)
    },
  })
  exports.formRef.value = { validate: async () => true }
  return { ...exports, errors, successes, routes }
}
function rejectWith(status, detail, url = '/auth/login') {
  return async () => { throw new AxiosError('Request rejected', undefined, { url }, undefined, { status, data: { detail } }) }
}
let component = mountHandler(rejectWith(401, '用户名或密码错误'))
await component.handleLogin()
assert.deepEqual(component.errors, ['用户名或密码错误'], 'Wrong credentials must show exactly one error on the login page')
assert.equal(component.loading.value, false)
assert.deepEqual(component.routes, [])
component = mountHandler(rejectWith(401, { unexpected: true }))
await component.handleLogin()
assert.deepEqual(component.errors, ['用户名或密码错误'], 'Malformed login error must not render an object')
component = mountHandler(rejectWith(500, '服务异常'))
await component.handleLogin()
assert.deepEqual(component.errors, [], 'Non-401 errors are already shown by the request interceptor')
assert.equal(component.loading.value, false)
component = mountHandler(rejectWith(401, '会话已失效', '/auth/me'))
await component.handleLogin()
assert.deepEqual(component.errors, [], 'User-info 401 was already handled by the interceptor and must not be duplicated')
component = mountHandler(async () => {})
await component.handleLogin()
assert.deepEqual(component.successes, ['登录成功'])
assert.deepEqual(component.routes, ['/dashboard'])
assert.deepEqual(component.errors, [])
console.log('login feedback contract passed: credential rejection, safe fallback, no duplicate errors, successful login')
