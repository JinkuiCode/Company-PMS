import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import vm from 'node:vm'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'
import * as core from '../src/query-system/core.ts'
import * as workspace from '../src/query-system/workspace.ts'

const fields = [{ field: 'code', label: 'Code', type: 'text' }]
const defaults = [{ field: 'code', shown: true, operator: 'contains', value: null, valueEnd: null }]
const { descriptor } = parse(readFileSync(new URL('../src/query-system/PmsQueryWorkspace.vue', import.meta.url), 'utf8'))
const script = compileScript(descriptor, { id: 'workspace-ownership' })
const compiled = ts.transpileModule(script.content, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText

export function fixture(t) {
  const data = new Map(), writes = []
  const storage = { getItem: key => data.get(key) ?? null, setItem: (key, value) => { writes.push(key); if(storage.fail)throw Error('storage unavailable');data.set(key, value) } }
  for (const [user, list, value] of [[1, 'archive', 'A'], [2, 'archive', 'B'], [1, 'projects', 'P']]) {
    workspace.saveScheme(storage, workspace.schemeStorageKey(user, list), [], {
      name: `${value}-scheme`, definitions: [{ ...defaults[0], value }], isDefault: true, preferences: { owner: value },
    }, fields)
  }
  writes.length = 0
  const auth = vue.reactive({ user: { id: 1 } })
  const props = vue.reactive({ listKey: 'archive', fields, defaults, ready: true })
  const confirmations=[],confirmResults=[];let leaveGuard
  const sandbox = { exports: {}, localStorage: storage, require: name => {
    if (name === 'vue') return vue
    if (name === 'vue-router') return {onBeforeRouteLeave:guard=>{leaveGuard=guard}}
    if (name === './core') return core
    if (name === './workspace') return workspace
    if (name === '@/stores/auth') return { useAuthStore: () => auth }
    if (name === 'element-plus') return { ElMessage: { warning() {}, success() {} },ElMessageBox:{confirm:(...args)=>{confirmations.push(args);const result=confirmResults.shift();return typeof result==='function'?result():result===false?Promise.reject('cancel'):Promise.resolve()}} }
    return {}
  } }
  vm.runInNewContext(compiled, sandbox)
  const component = sandbox.exports.default, setup = component.setup, events = []
  let state
  component.setup = (props, context) => {
    state = setup(props, { ...context, emit: (...args) => { events.push(args); context.emit(...args) } })
    return state
  }
  component.render = () => null
  // Mount the real setup with Vue lifecycle and reactive props, without a DOM or UI library.
  const renderer = vue.createRenderer({
    createComment: text => ({ text }), createText: text => ({ text }), createElement: tag => ({ tag }),
    insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
    parentNode: () => null, nextSibling: () => null,
  })
  const app = renderer.createApp({ render: () => vue.h(component, props) })
  app.mount({})
  t.after(() => app.unmount())
  function openDraft() {
    state.openSettings()
    state.name.value = 'A-draft'
    state.editDefinitions.value[0].value = 'private-A'
    state.configErrors.value = { name: 'old error' }
  }
  function assertCleared() {
    assert.equal(state.opened.value, false, 'identity changes must close settings')
    assert.equal(state.name.value, '')
    assert.equal(state.originalName.value, '')
    assert.equal(state.isDefault.value, false)
    assert.equal(state.editDefinitions.value.length, 0)
    assert.equal(Object.keys(state.configErrors.value).length, 0)
  }
  return { auth, props, state, data, writes, events, openDraft, assertCleared,storage,confirmations,confirmResults,get leaveGuard(){return leaveGuard} }
}

test('user change closes and discards the previous user settings draft', async t => {
  const f = fixture(t)
  f.openDraft()
  f.auth.user = { id: 2 }
  await vue.nextTick()
  f.assertCleared()
  // A late field callback must not make a closed session eligible to save again.
  f.state.name.value = 'late-draft'
  f.state.editDefinitions.value = [{ ...defaults[0], value: 'private-A' }]
  f.state.save()
  assert.equal(f.writes.length, 0)
  f.assertCleared()
})

test('list change closes and discards the previous list settings draft', async t => {
  const f = fixture(t)
  f.openDraft()
  f.props.listKey = 'projects'
  await vue.nextTick()
  f.assertCleared()
  f.state.save()
  assert.equal(f.writes.length, 0)
})

test('logout discards settings even when the next identity is not ready', async t => {
  const f = fixture(t)
  f.openDraft()
  f.auth.user = null
  f.props.ready = false
  await vue.nextTick()
  f.assertCleared()
  f.state.save()
  assert.equal(f.writes.length, 0)
})

test('identity change discards settings while the next list is loading', async t => {
  const f = fixture(t)
  f.openDraft()
  f.props.ready = false
  f.props.listKey = 'projects'
  await vue.nextTick()
  f.assertCleared()
})

test('save rejects an ownership change before queued watchers run', t => {
  const f = fixture(t)
  f.openDraft()
  const before = [...f.data]
  f.auth.user = { id: 2 }
  f.state.save()
  assert.equal(f.writes.length, 0, 'stale save must not write to either user')
  assert.deepEqual([...f.data], before)
  f.assertCleared()
})

test('closing settings discards its draft and rejects late save', async t => {
  const f = fixture(t)
  f.openDraft()
  f.state.opened.value = false
  await vue.nextTick()
  f.assertCleared()
  f.state.save()
  assert.equal(f.writes.length, 0)
})

test('the same owner can save, and reopening restores saved values', async t => {
  const f = fixture(t)
  f.openDraft()
  f.state.save()
  await vue.nextTick()
  assert.deepEqual(f.writes, [workspace.schemeStorageKey(1, 'archive')])
  const saved = workspace.readSchemes({ getItem: key => f.data.get(key) }, f.writes[0])
  assert.equal(saved.find(s => s.name === 'A-draft').definitions[0].value, 'private-A')
  f.assertCleared()
  f.state.openSettings()
  assert.equal(f.state.name.value, 'A-draft')
  assert.equal(f.state.editDefinitions.value[0].value, 'private-A')
})

test('a newly opened settings session belongs only to the new user', async t => {
  const f = fixture(t)
  f.openDraft()
  f.auth.user = { id: 2 }
  await vue.nextTick()
  f.state.openSettings()
  assert.equal(f.state.name.value, 'B-scheme')
  assert.equal(f.state.editDefinitions.value[0].value, 'B')
  f.state.name.value = 'B-saved'
  f.state.save()
  assert.deepEqual(f.writes, [workspace.schemeStorageKey(2, 'archive')])
  assert.equal(workspace.readSchemes({ getItem: key => f.data.get(key) }, workspace.schemeStorageKey(1, 'archive'))[0].name, 'A-scheme')
})

for (const identity of ['user', 'list', 'logout']) {
  for (const outcome of ['resolve', 'reject']) {
    test(`${identity} change invalidates pending reference validation while not ready (${outcome})`, async t => {
      const f = fixture(t)
      let resolve, reject
      const pending = new Promise((yes, no) => { resolve = yes; reject = no })
      f.props.fields = [{ ...fields[0], reference: { title: 'Codes', keyField: 'id', keyType: 'number', load: () => pending } }]
      await vue.nextTick()
      f.state.change([{ id: 1, field: 'code', operator: 'reference', value: [7], valueEnd: null, schemaVersion: 2 }])
      const query = f.state.query()
      assert.equal(f.state.busy.value, true)
      f.props.ready = false
      if (identity === 'user') f.auth.user = { id: 2 }
      else if (identity === 'logout') f.auth.user = null
      else f.props.listKey = 'projects'
      await vue.nextTick()
      if (outcome === 'resolve') resolve({ items: [{ value: 7, code: 'A', name: 'A' }], total: 1 })
      else reject(Error('old identity response'))
      await query
      assert.equal(f.events.filter(([event]) => event === 'query').length, 0, 'old validation must not emit a query')
      assert.equal(Object.keys(f.state.errors.value).length, 0, 'old errors must not enter the new identity')
      assert.equal(f.state.busy.value, false)
    })
  }
}

test('identity change immediately releases pending query busy state', async t => {
  const f = fixture(t)
  let resolve
  const pending = new Promise(yes => { resolve = yes })
  f.props.fields = [{ ...fields[0], reference: { title: 'Codes', keyField: 'id', keyType: 'number', load: () => pending } }]
  await vue.nextTick()
  f.state.change([{ id: 1, field: 'code', operator: 'reference', value: [7], valueEnd: null, schemaVersion: 2 }])
  const query = f.state.query()
  f.props.ready = false
  f.auth.user = { id: 2 }
  const busyAfterSwitch = f.state.busy.value
  resolve({ items: [{ value: 7, code: 'A', name: 'A' }], total: 1 })
  await query
  assert.equal(busyAfterSwitch, false, 'switching identity must release busy before the response')
})
