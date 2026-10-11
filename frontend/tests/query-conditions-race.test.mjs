import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { parse } from '@vue/compiler-sfc'
import { reactive, ref, computed, watch, nextTick } from 'vue'
import * as core from '../src/query-system/core.ts'
import * as reference from '../src/query-system/reference.ts'

const { descriptor } = parse(fs.readFileSync(new URL('../src/query-system/PmsQueryConditions.vue', import.meta.url), 'utf8'))
const script = ts.createSourceFile('conditions.ts', descriptor.scriptSetup.content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
const code = ts.createPrinter().printFile(ts.factory.updateSourceFile(script, script.statements.filter(s => !ts.isImportDeclaration(s))))
const js = ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function fixture(load) {
  const props = reactive({ opened: true, modelValue: [], fields: [{ field: 'project_code', label: '编号', type: 'text', reference: { title: '档案', keyField: 'id', keyType: 'number', load } }] })
  const emitted = []
  const context = vm.createContext({ ...core, ...reference, ref, computed, watch, nextTick, useId: () => 'test-id', defineProps: () => props, defineEmits: () => (event, value) => emitted.push({ event, value }), defineExpose: () => {} })
  const editor = vm.runInContext(`(function(){${js}; return {apply,draft,errors,applying};})()`, context)
  editor.draft.value = [{ id: 1, field: 'project_code', operator: 'reference', value: [42], valueEnd: null, schemaVersion: 2 }]
  return { props, emitted, editor }
}
const result = { items: [{ value: 42, code: 'REF-42', name: '项目42' }], total: 1 }

{
  const pending = deferred(), { props, emitted, editor } = fixture(() => pending.promise)
  const apply = editor.apply()
  assert.equal(editor.applying.value, true)
  props.opened = false
  await nextTick()
  props.opened = true
  await nextTick()
  pending.resolve(result)
  await apply
  assert.equal(emitted.length, 0, '关闭并重开后，旧引用校验不得应用空草稿或覆盖新会话')
  assert.equal(editor.draft.value.length, 0)
}
{
  const pending = deferred(), { props, emitted, editor } = fixture(() => pending.promise)
  const apply = editor.apply()
  props.opened = false
  await nextTick()
  pending.resolve(result)
  await apply
  assert.equal(emitted.length, 0, '关闭面板后不得提交旧条件')
}
{
  const first = deferred(), second = deferred()
  let calls = 0
  const { props, emitted, editor } = fixture(() => ++calls === 1 ? first.promise : second.promise)
  const oldApply = editor.apply()
  props.opened = false
  await nextTick()
  props.opened = true
  await nextTick()
  editor.draft.value = [{ id: 2, field: 'project_code', operator: 'reference', value: [43], valueEnd: null, schemaVersion: 2 }]
  const newApply = editor.apply()
  first.reject(new Error('旧请求失败'))
  await oldApply
  assert.equal(editor.applying.value, true, '旧请求收尾不得解除新请求锁定')
  assert.deepEqual({ ...editor.errors.value }, {})
  second.resolve({ items: [{ value: 43 }], total: 1 })
  await newApply
  assert.equal(emitted.length, 1)
  assert.deepEqual(JSON.parse(JSON.stringify(emitted[0].value[0].value)), [43])
}
{
  const pending = deferred(), { props, emitted, editor } = fixture(() => pending.promise)
  const apply = editor.apply()
  props.modelValue = [{ id: 3, field: 'project_code', operator: 'contains', value: 'NEW', valueEnd: null, schemaVersion: 2 }]
  await nextTick()
  pending.resolve(result)
  await apply
  assert.equal(emitted.length, 0, '外部重置或重选方案后旧请求不得覆盖新条件')
}
console.log('query condition race passed: reopen, close, stale failure, new apply and scheme reset')
