import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { parse } from '@vue/compiler-sfc'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { usePageLoad } from '../src/composables/usePageLoad.ts'

const source = readFileSync(new URL('../src/views/system/ParameterList.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const script = ts.transpileModule(descriptor.scriptSetup.content, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  transformers: { before: [context => root => ts.visitNode(root, function visit(node) {
    if (ts.isImportDeclaration(node)) return undefined
    return ts.visitEachChild(node, visit, context)
  })] },
}).outputText.replace(/export \{\};?\s*$/, '')
const fixture = 'synthetic-ui-initial-82'
const row = (value = fixture, reveal_status = 'available') => ({ code: 'user.initial_password', name: '用户初始密码', group: '用户管理', description: '', sensitive: true, configured: true, version: 1, value, reveal_status, reveal_message: reveal_status === 'legacy' ? '旧值不可逆，请重新保存' : null })

function harness(request = { get: async () => ({ items: [row()] }), put: async () => ({}) }) {
  const permissions = reactive({ view: true, edit: true })
  const auth = { hasPermission: code => permissions[code.endsWith(':view') ? 'view' : 'edit'] }
  const hooks = {}
  const context = vm.createContext({
    computed, nextTick, ref, watch, request, usePageLoad, useAuthStore: () => auth,
    onMounted: callback => { hooks.mount = callback },
    onBeforeUnmount: callback => { hooks.unmount = callback },
    onBeforeRouteLeave: callback => { hooks.leave = callback },
    useSystemQuery: () => ({ fields: [], defaults: [], draft: ref([]), submit() {}, filterRows: rows => rows, clearColumns() {}, columnContext: {}, columnFilters: {}, columnClass() {} }),
    ElMessage: { success() {} }, ElMessageBox: { confirm: async () => {} },
    document: { getElementById: () => null },
  })
  vm.runInContext(script + '\nglobalThis.subject = { items, value, editing, load, edit, save, revealSecret, currentValue, failed };', context)
  return { ...context.subject, permissions, hooks }
}

test('parameter current value is plaintext only for the initial-password allowlist', () => {
  assert.match(descriptor.template.content, /currentValue\(row\)/)
  assert.doesNotMatch(descriptor.scriptSetup.content, /localStorage|sessionStorage|indexedDB/)
  assert.match(descriptor.scriptSetup.content, /user\.initial_password/)
})

test('mail connection settings show their option label while SMTP password remains hidden', () => {
  const subject = harness()
  const connection = {code:'mail.security', configured:true, sensitive:false, value:'internal',
    options:[{value:'internal', label:'内网专用（不加密）'}]}
  assert.equal(subject.currentValue(connection), '内网专用（不加密）')
  assert.equal(subject.currentValue({...connection, value:'unknown'}), 'unknown')
  assert.equal(subject.currentValue({code:'mail.password', configured:true, sensitive:true, value:'synthetic-secret'}), '已设置 · 不回显')
})

test('permission loss clears memory and discards a late successful fetch', async () => {
  let resolve
  const subject = harness({ get: () => new Promise(done => { resolve = done }) })
  subject.items.value = [row()]
  subject.value.value = fixture
  subject.editing.value = subject.items.value[0]
  const pending = subject.load()
  subject.permissions.view = false
  assert.equal(subject.items.value.length, 0)
  assert.equal(subject.value.value, '')
  assert.equal(subject.editing.value, null)
  subject.permissions.view = true
  resolve({ items: [row()] })
  await pending
  assert.equal(subject.items.value.length, 0, 'old request must stay invalid after regrant')
})

test('403 clears revealed memory, and unmount invalidates in-flight requests', async () => {
  const denied = harness({ get: async () => { throw { response: { status: 403 } } } })
  denied.items.value = [row()]
  denied.value.value = fixture
  await denied.load()
  assert.equal(denied.items.value.length, 0)
  assert.equal(denied.value.value, '')
  assert.equal(denied.failed.value, true, '403清除内存后仍须保留读取失败反馈')
  let resolve
  const subject = harness({ get: () => new Promise(done => { resolve = done }) })
  subject.items.value = [row()]
  const pending = subject.load()
  assert.equal(typeof subject.hooks.unmount, 'function')
  subject.hooks.unmount()
  assert.equal(subject.items.value.length, 0)
  resolve({ items: [row()] })
  await pending
  assert.equal(subject.items.value.length, 0)
})

test('permission loss during save prevents refetch or stale draft restoration', async () => {
  let resolve, reads = 0
  const subject = harness({ get: async () => { reads++; return { items: [row()] } }, put: () => new Promise(done => { resolve = done }) })
  subject.items.value = [row()]
  await subject.edit(subject.items.value[0])
  subject.value.value = 'synthetic-new-ui-value'
  const pending = subject.save()
  subject.permissions.view = false
  resolve({})
  await pending
  assert.equal(reads, 0)
  assert.equal(subject.items.value.length, 0)
  assert.equal(subject.value.value, '')
})

test('editor never preloads the revealed initial value; edit revocation clears its draft', async () => {
  const subject = harness()
  subject.items.value = [row()]
  await subject.edit(subject.items.value[0])
  assert.equal(subject.value.value, '')
  subject.value.value = 'synthetic-editor-value'
  subject.permissions.edit = false
  assert.equal(subject.value.value, '')
  assert.equal(subject.editing.value, null)
  assert.equal(subject.items.value[0].value, fixture, 'view permission still permits current value')
})
