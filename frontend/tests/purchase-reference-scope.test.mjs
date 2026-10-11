import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'
import * as adapter from '../src/query-system/report-adapter.ts'
import { validateReferences } from '../src/query-system/workspace.ts'

const source = readFileSync(new URL('../src/views/reports/PurchaseProgressList.vue', import.meta.url), 'utf8')
const condition = (field, value, id = 1) => ({ id, field, operator: 'reference', value, valueEnd: null, schemaVersion: 2 })
function pageReferenceScope(oldScope, oldDraft) {
  const declaration = source.slice(source.indexOf('const referenceScope ='), source.indexOf('const projectReference ='))
  assert.ok(declaration.length, 'exercise the actual page provider scope callback')
  const { outputText } = ts.transpileModule(declaration, { compilerOptions: { target: ts.ScriptTarget.ES2022 } })
  return new Function('reportScope', 'purchaseReferenceScope', 'projectScope', 'conditions', `${outputText}; return referenceScope`)(
    adapter.reportScope, adapter.purchaseReferenceScope, { value: oldScope }, { value: oldDraft })
}

test('scheme project validation uses the current organization before its scope preferences are restored', async () => {
  const requests = []
  const oldScope = { project_code: 'OLD', organization_id: 2, product_line_name: '旧产品线' }
  const oldDraft = [condition('organization_ids', [2]), condition('project_code', [20], 2)]
  const current = [condition('organization_ids', [3]), condition('project_code', [30], 2)]
  const original = structuredClone({ oldScope, oldDraft, current })
  const reference = adapter.reportReference('项目档案', 'id', 'number', async params => {
    requests.push(params)
    const found = params.organization_ids.includes(3) && params.ids.includes(30)
    return { items: found ? [{ value: 30, label: '组织3项目' }] : [], total: found ? 1 : 0 }
  }, pageReferenceScope(oldScope, oldDraft))
  const failures = await validateReferences(current, [{ field: 'project_code', label: '项目编码', type: 'text', reference }])
  assert.deepEqual(failures, {}, 'a valid project must not be rejected by the previous scheme organization')
  assert.deepEqual(requests[0].organization_ids, [3])
  assert.deepEqual(requests[0].ids, [30])
  assert.deepEqual({ oldScope, oldDraft, current }, original)
})

test('current reference conditions are authoritative, including an empty or unscoped scheme', () => {
  const scope = pageReferenceScope({ project_code: 'OLD', organization_id: 2 }, [condition('organization_ids', [2])])
  assert.deepEqual(scope({ conditions: [] }), { organization_ids: [] })
  assert.deepEqual(scope({ conditions: [condition('project_code', [30])] }), { organization_ids: [] })
  assert.deepEqual(scope({}), { organization_ids: [] }, 'missing query conditions never reuse old detail scope or a draft')
  const current = [condition('organization_ids', [3, 4])]
  assert.deepEqual(scope({ conditions: current, line: 3 }), { organization_ids: [3] })
  assert.throws(() => scope({ conditions: current, line: 2 }), /当前查询范围/)
  assert.deepEqual(scope({ conditions: current }), { organization_ids: [3, 4] })
})

test('reference validation separation preserves exact row drill and restored scheme business scope', () => {
  const rowScope = { project_code: 'ROW', organization_id: 3, product_line_name: '生产' }
  const submitted = { keyword: '', organization_ids: [2, 3], project_code: '', supplier: '', dates: [], progress: '', conditions: [condition('project_code', [20, 30])], column_filters: [] }
  const entry = adapter.purchaseDetailEntry(submitted, [{ field: 'project_code' }], rowScope)
  assert.deepEqual(entry.scope, rowScope)
  assert.deepEqual(entry.draft.conditions, [])
  assert.deepEqual(adapter.reportPreferences({ scope: rowScope }, []).scope, rowScope)
  assert.match(source, /if \(plan\.scope !== undefined\) projectScope\.value = plan\.scope \|\| undefined/)
  assert.match(source, /project_code:projectScope\.value\.project_code,organization_ids:\[projectScope\.value\.organization_id\]/)
  assert.match(source, /project_code_is_empty: !!projectScope\.value && !projectScope\.value\.project_code/)
})
