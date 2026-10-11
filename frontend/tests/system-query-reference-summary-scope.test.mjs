import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import vm from 'node:vm'
import { parse, compileScript } from '@vue/compiler-sfc'
import ts from 'typescript'
import * as vue from 'vue'
import * as core from '../src/query-system/core.ts'
import * as reference from '../src/query-system/reference.ts'
import * as summaries from '../src/query-system/reference-summary.ts'

const { descriptor } = parse(readFileSync(new URL('../src/query-system/PmsQueryConditionRow.vue', import.meta.url), 'utf8'))
const script = compileScript(descriptor, { id: 'reference-summary-scope' })
const compiled = ts.transpileModule(script.content, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText

function deferredSource() {
  const calls = []
  const load = query => new Promise((resolve, reject) => {
    calls.push({ query: JSON.parse(JSON.stringify(query)), resolve, reject })
  })
  return { source: { title: 'Projects', keyField: 'id', keyType: 'number', load }, calls }
}

function fixture(t, source = deferredSource(), field = { field: 'project_code', label: 'Project', type: 'text', reference: source.source }) {
  const condition = { id: 1, field: field.field, operator: 'reference', value: [7], valueEnd: null, schemaVersion: 2 }
  const scope = { id: 2, field: 'organizations', operator: 'in', value: [1], valueEnd: null, schemaVersion: 2 }
  const props = vue.reactive({
    condition, conditions: [condition, scope],
    fields: [field], prefix: 'Query ',
  })
  const sandbox = { exports: {}, require: name => {
    if (name === 'vue') return vue
    if (name === './core') return core
    if (name === './reference') return reference
    if (name === './reference-summary') return summaries
    return {}
  } }
  vm.runInNewContext(compiled, sandbox)
  const component = sandbox.exports.default, setup = component.setup
  let state
  component.setup = (props, context) => {
    state = setup(props, context)
    return state
  }
  component.render = () => null
  const renderer = vue.createRenderer({
    createComment: text => ({ text }), createText: text => ({ text }), createElement: tag => ({ tag }),
    insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
    parentNode: () => null, nextSibling: () => null,
  })
  const app = renderer.createApp({ render: () => vue.h(component, props) })
  app.mount({})
  t.after(() => app.unmount())
  return { props, state, source, unmount: () => app.unmount() }
}

const record = code => ({ value: 7, code, name: code })
async function finish(call, code, total = 1) {
  call.resolve({ items: [record(code)], total })
  await vue.nextTick()
}

for (const change of ['metadata', 'source', 'load']) {
  test(`${change} replacement invalidates a late summary with unchanged field and IDs`, async t => {
    const f = fixture(t), next = deferredSource()
    if (change === 'metadata') f.props.fields = [{ ...f.props.fields[0], reference: next.source }]
    else if (change === 'source') f.props.fields[0].reference = next.source
    else f.props.fields[0].reference.load = next.source.load
    await vue.nextTick()
    await finish(f.source.calls[0], 'A-7')
    assert.equal(f.state.summary.value.text, '7', 'the previous metadata must not supply the current label')
    assert.equal(next.calls.length, 1, 'the new source must resolve unchanged IDs')
    await finish(next.calls[0], 'B-7')
    assert.equal(f.state.summary.value.text, 'B-7')
  })
}

for (const change of ['replace', 'mutate']) {
  test(`associated conditions ${change} invalidates and reloads the summary`, async t => {
    const f = fixture(t)
    await finish(f.source.calls[0], 'A-7')
    if (change === 'replace') f.props.conditions = [f.props.condition, { ...f.props.conditions[1], value: [2] }]
    else f.props.conditions[1].value[0] = 2
    await vue.nextTick()
    assert.equal(f.state.summary.value.text, '7', 'accepted labels must clear when their scope changes')
    assert.equal(f.source.calls.length, 2)
    assert.deepEqual(f.source.calls[1].query.conditions[1].value, [2])
    await finish(f.source.calls[1], 'B-7')
    assert.equal(f.state.summary.value.text, 'B-7')
  })
}

test('a late old-scope page cannot overwrite a newer scope or continue pagination', async t => {
  const f = fixture(t)
  f.props.condition.value = [7, 8]
  await vue.nextTick()
  const old = f.source.calls.at(-1)
  f.props.conditions[1].value = [2]
  await vue.nextTick()
  const current = f.source.calls.at(-1)
  assert.notEqual(current, old, 'the changed scope must start its own request')
  current.resolve({ items: [record('B-7'), { value: 8, code: 'B-8', name: 'B-8' }], total: 2 })
  await vue.nextTick()
  const count = f.source.calls.length
  await finish(old, 'A-7', 2)
  assert.equal(f.state.summary.value.text, 'B-7、B-8')
  assert.equal(f.source.calls.length, count, 'a stale page must not request another page in the new scope')
})

test('enum option metadata updates the label without changing the selected value', async t => {
  const f = fixture(t, undefined, { field: 'status', label: 'Status', type: 'enum', options: [{ value: 7, label: 'A' }] })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(f.state.summary.value.text, 'A')
  f.props.fields[0].options[0].label = 'B'
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(f.state.summary.value.text, 'B')
})

test('removing the reference metadata rejects its late summary', async t => {
  const f = fixture(t)
  delete f.props.fields[0].reference
  await vue.nextTick()
  await finish(f.source.calls[0], 'A-7')
  assert.equal(f.state.summary.value.text, '7')
})

test('an unchanged context keeps the accepted summary without another load', async t => {
  const f = fixture(t)
  await finish(f.source.calls[0], 'A-7')
  f.props.prefix = 'Other '
  await vue.nextTick()
  assert.equal(f.state.summary.value.text, 'A-7')
  assert.equal(f.source.calls.length, 1)
})
