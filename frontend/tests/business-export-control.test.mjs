import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { test } from 'node:test'
import vm from 'node:vm'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'

const source = new URL('../src/business-export/BusinessExportControl.vue', import.meta.url)
assert.ok(existsSync(source), 'Business documents need their own reusable export control')
const { descriptor } = parse(readFileSync(source, 'utf8'))
const script = compileScript(descriptor, { id: 'business-export' })
const compiled = ts.transpileModule(script.content, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText

function fixture(t) {
  const permissions = ['project:list:view', 'project:list:export']
  const auth = vue.reactive({ user: { id: 1, permissions }, hasPermission(code) { return this.user?.permissions.includes(code) ?? false } })
  const payload = { filters: [], column_filters: [], sort: [], columns: ['project_name'] }
  const props = vue.reactive({ resource: { kind: 'projects' }, snapshot: () => payload, disabled: false })
  const calls = [], downloads = [], warnings = [], revoked = []
  let resolve, reject
  const pending = new Promise((yes, no) => { resolve = yes; reject = no })
  const api = {
    businessExportPermission: () => 'project:list:export', businessViewPermission: () => 'project:list:view',
    businessExportFilename: () => '项目列表.xlsx',
    downloadBusinessExport: async (...args) => { calls.push(args); return pending },
  }
  const sandbox = {
    exports: {}, Blob, Error, setTimeout: callback => { callback(); return 1 },
    URL: { createObjectURL: () => 'blob:test', revokeObjectURL: url => revoked.push(url) },
    document: { createElement: () => { const link = { click() { downloads.push({ href: this.href, name: this.download }) } }; return link } },
    require: name => name === 'vue' ? vue : name === '@/stores/auth' ? { useAuthStore: () => auth }
      : name === '@/api/businessExport' ? api : name === 'element-plus' ? { ElMessage: { warning: text => warnings.push(text) } } : {},
  }
  vm.runInNewContext(compiled, sandbox)
  const component = sandbox.exports.default, setup = component.setup
  let state
  component.setup = (props, context) => { state = setup(props, context); return state }
  component.render = () => null
  const renderer = vue.createRenderer({
    createComment: text => ({ text }), createText: text => ({ text }), createElement: tag => ({ tag }),
    insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null,
  })
  const app = renderer.createApp({ render: () => vue.h(component, props) })
  app.mount({})
  t.after(() => app.unmount())
  return { auth, props, payload, calls, downloads, warnings, revoked, state, resolve, reject, app }
}

test('only authorized, submitted results can be exported', async t => {
  const f = fixture(t)
  f.props.disabled = true
  await vue.nextTick()
  await f.state.submit()
  assert.equal(f.calls.length, 0)
  f.props.disabled = false
  f.auth.user.permissions = ['project:list:view']
  await vue.nextTick()
  await f.state.submit()
  assert.equal(f.calls.length, 0, 'view alone cannot export')
  f.auth.user.permissions = ['project:list:export']
  await f.state.submit()
  assert.equal(f.calls.length, 0, 'export alone cannot view')
})

test('export takes one request and downloads its full submitted snapshot', async t => {
  const f = fixture(t)
  const first = f.state.submit()
  await f.state.submit()
  assert.equal(f.calls.length, 1, 'duplicate click must not generate a second file')
  assert.deepEqual(f.calls[0][1], f.payload)
  f.resolve(new Blob(['xlsx']))
  await first
  assert.deepEqual(f.downloads, [{ href: 'blob:test', name: '项目列表.xlsx' }])
  assert.deepEqual(f.revoked, ['blob:test'])
  assert.equal(f.state.submitting.value, false)
})

test('a request failure resets busy without downloading', async t => {
  const f = fixture(t)
  const first = f.state.submit()
  f.reject(Error('request failure'))
  await first
  assert.equal(f.downloads.length, 0)
  assert.equal(f.state.submitting.value, false)
})

for (const identity of ['user', 'resource', 'permission', 'unmount']) {
  test(`${identity} change blocks a pending file from downloading`, async t => {
    const f = fixture(t)
    const first = f.state.submit()
    if (identity === 'user') f.auth.user = { id: 2, permissions: [...f.auth.user.permissions] }
    if (identity === 'resource') f.props.resource = { kind: 'tasks', projectId: 9 }
    if (identity === 'permission') f.auth.user.permissions = ['project:list:view']
    if (identity === 'unmount') f.app.unmount()
    await vue.nextTick()
    f.resolve(new Blob(['old owner']))
    await first
    assert.equal(f.downloads.length, 0)
  })
}

test('invalid snapshot warns without sending a request', async t => {
  const f = fixture(t)
  f.props.snapshot = () => { throw Error('没有可见业务列可导出') }
  await vue.nextTick()
  await f.state.submit()
  assert.equal(f.calls.length, 0)
  assert.deepEqual(f.warnings, ['没有可见业务列可导出'])
  assert.equal(f.state.submitting.value, false)
})

test('export reuses approved shared compact styling and label', () => {
  assert.ok(descriptor.template.content.includes('class="pms-button-export"'))
  assert.ok(descriptor.template.content.includes('导出数据'))
  assert.ok(descriptor.template.content.includes('size="small"'))
  assert.equal(descriptor.styles.length, 0, 'No new styles')
})
