import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { test } from 'node:test'

const adapter = new URL('../src/query-system/report-adapter.ts', import.meta.url)
test('reports reuse the shared query workspace without local plan/query UI', () => {
  for (const name of ['PurchaseOverviewList', 'PurchaseProgressList', 'InventoryList', 'StockDetailList']) {
    const source = readFileSync(new URL(`../src/views/reports/${name}.vue`, import.meta.url), 'utf8')
    assert.match(source, /<PmsQueryWorkspace\b/, name)
    assert.doesNotMatch(source, /PmsReportQueryBar|PmsReportPlans|planOpen|savePlan\(/, name)
    assert.match(source, /@query="submitWorkspace"/, name)
    assert.match(source, /@clear-columns="clearColumnFilters"/, name)
    assert.match(source, /:legacy-schemes="legacyReportSchemes"/, `${name} loads old personal schemes through Workspace`)
    assert.match(source, /column_filters/, `${name} must send server-side column filters`)
    assert.match(source, /decorateQueryColumns(?:<[^>]+>)?\(/, `${name} uses the shared header funnel`)
    assert.match(source, /ready: \(\) => !!(?:accepted\b|acceptedParams\.value|result\.value\.applied) && !(?:loading\.value|result\.value\.loading)/, `${name} must disable column funnels until a query is accepted`)
    assert.match(source, /sort: createReportColumnSort\(/, `${name} restores server-side header sorting`)
    assert.match(source, /const defaultColDef[^\n]*comparator:\s*\(\)\s*=>\s*0/, `${name} must not let AG Grid sort only the current page`)
    assert.doesNotMatch(source, /matchesConditions\(|setFilterModel\(/, 'never filter a report page locally')
  }
})
test('overview export and query keep the full accepted aggregate scope separate from detail transfer', () => {
  const source = readFileSync(new URL('../src/views/reports/PurchaseOverviewList.vue', import.meta.url), 'utf8')
  assert.match(source, /view:\s*'overview'/)
  assert.match(source, /<ReportExportControl\b[^>]*report="purchase"/)
  assert.match(source, /const exportParameters\s*=\s*\(\)\s*=>\s*cloneQuery\(accepted!\.params\)/)
  assert.match(source, /metadata\.value\?\.overview_query_fields/)
  assert.match(source, /purchaseDetailEntry\(applied\.value\?\.draft/)
  assert.doesNotMatch(source, /rows\.value\.map.*project_code/, 'detail tab must not enumerate current-page project identities')
})
test('report adapter exists independently of shared control implementation', () => assert.ok(existsSync(adapter)))
if (existsSync(adapter)) {
  const { serializeReportConditions, reportFields, reportScope, reportReference, purchaseConditions,
    selectReportProgress, withReportProgress, reportPreferences, createReportRequest, reportColumnCandidates, serializeColumnFilters, linkReportScope, saveReportPreferences, legacyReportSchemes, purchaseDetailEntry, createReportColumnSort } = await import(adapter.href)
  const c = (field, operator, value, valueEnd = null) => ({ id: 1, field, operator, value, valueEnd, schemaVersion: 2 })
  test('wire protocol keeps array keys and version, without UI identities', () => {
    const input = [c('project_code', 'reference', ['P1', 'P2']), { ...c('qty', 'equals', 0), schemaVersion: 1 }]
    assert.deepEqual(JSON.parse(serializeReportConditions(input)), input.map(({ id, schemaVersion, ...wire }) => schemaVersion === 2 ? { ...wire, schemaVersion } : wire))
    assert.equal(input[0].id, 1)
  })
  test('all enum fields get real option references and report fields are deduplicated', async () => {
    const fields = reportFields([{ field: 'progress', label: '进度', type: 'enum', options: [{ value: 'done', label: '完成' }] }], [{ field: 'progress', label: '进度', type: 'enum', options: [{ value: 'done', label: '完成' }] }])
    assert.equal(fields.length, 1)
    assert.deepEqual((await fields[0].reference.load({ page: 1, pageSize: 10 })).items.map(r => r.value), ['done'])
  })
  test('stock base scope requires BOTH material and organization and warehouse is selection only', () => {
    const values = [c('material', 'contains', 'M1'), c('organization_ids', 'reference', [2, 1]), c('bill_date', 'between', '2026-10-01', '2026-10-11'), c('stock_id', 'reference', [3])]
    assert.deepEqual(reportScope('stock-detail', values).params, { material: 'M1', organization_ids: [1, 2], stock_id: 3, start_date: '2026-10-01', end_date: '2026-10-11' })
    assert.throws(() => reportScope('stock-detail', values.filter(v => v.field !== 'material')), /物料/)
    assert.throws(() => reportScope('stock-detail', values.filter(v => v.field !== 'organization_ids')), /组织/)
    assert.throws(() => reportScope('stock-detail', [...values.filter(v => v.field !== 'stock_id'), c('stock_id', 'contains', '3')]), /仓库/)
  })
  test('purchase scope extracts product line and keyword but never narrows reference arrays to one project', () => {
    const project = c('project_code', 'reference', ['P1', 'P2'])
    const result = reportScope('purchase', [c('organization_ids', 'in', [2]), c('keyword', 'contains', 'motor'), project])
    assert.deepEqual(result.params, { keyword: 'motor', organization_ids: [2] })
    assert.deepEqual(result.conditions, [project])
  })
  test('reference provider sends scoped server pagination, ids and batch, refuses truncated legacy responses', async () => {
    let params
    const ref = reportReference('项目', 'project_code', 'string', async p => { params = p; return { items: [{ value: 'P1', label: '项目1' }], total: 150 } }, () => ({ organization_ids: [2] }))
    assert.equal((await ref.load({ page: 2, pageSize: 50, ids: ['P1'], batch: { field: 'code', values: ['P1'] } })).total, 150)
    assert.deepEqual(params, { organization_ids: [2], keyword: undefined, page: 2, page_size: 50, ids: ['P1'], batch_field: 'code', batch_values: ['P1'] })
    const truncated = reportReference('项目', 'project_code', 'string', async () => ({ items: [], has_more: true }))
    await assert.rejects(truncated.load({ page: 1, pageSize: 50 }), /分页/)
  })
  test('purchase drilldown keeps the full submitted scope and fast state buttons replace only progress', () => {
    const conditions = purchaseConditions({ keyword: 'M', organization_ids: [2], project_code: 'P', supplier: 'S', dates: ['2026-10-01', '2026-10-11'], progress: '', conditions: [] })
    assert.ok(conditions.some(c => c.field === 'project_code' && c.operator === 'equals' && c.value === 'P'))
    const next = withReportProgress(conditions, 'complete')
    assert.equal(selectReportProgress(next, ['complete']), 'complete')
    assert.equal(next.filter(c => c.field === 'progress').length, 1)
    assert.deepEqual(withReportProgress(next, ''), conditions)
    assert.equal(next.at(-1).schemaVersion, 2)
  })
  test('total/detail transfer isolates aggregate filters while retaining base conditions and exact row scope', () => {
    assert.equal(typeof purchaseDetailEntry, 'function')
    const base = c('application_date', 'between', '2026-10-01', '2026-10-11')
    const reference = c('project_code', 'reference', [100, 200])
    const aggregate = c('completion_rate', 'greaterThan', 50)
    const submitted = { keyword: 'ACCEPTED', organization_ids: [2, 3], project_code: '', supplier: 'S', progress: '', dates: [], conditions: [base, reference, aggregate], column_filters: [{ field: 'completion_rate', mode: 'values', values: [100] }, { field: 'project_code', mode: 'values', values: ['PAGE-ONLY'] }] }
    const original = structuredClone(submitted)
    const fields = [{ field: 'application_date' }, { field: 'project_code' }]
    const tab = purchaseDetailEntry(submitted, fields)
    assert.deepEqual(tab.draft.conditions, [base, reference])
    assert.deepEqual(tab.draft.organization_ids, [2, 3])
    assert.deepEqual(tab.draft.column_filters, [])
    assert.equal(tab.scope, undefined)
    assert.equal(tab.draft.project_codes, undefined, 'must not substitute current-page projects for the submitted full scope')
    const scope = { project_code: 'P1', organization_id: 3, product_line_name: '生产' }
    const row = purchaseDetailEntry(submitted, fields, scope, 'review')
    assert.deepEqual(row.scope, scope)
    assert.equal(row.progress, 'review')
    assert.equal(row.draft.keyword, 'ACCEPTED')
    assert.deepEqual(row.draft.conditions, [base], 'exact project/org consumes multi-organization positive project references, which would otherwise fail reference scope validation')
    const emptyProject = purchaseDetailEntry({ ...submitted, conditions: [base] }, fields, { ...scope, project_code: '' })
    assert.equal(emptyProject.scope.project_code, '', 'empty project identity must remain exact, never mean all projects')
    row.scope.organization_id = 4; row.draft.organization_ids.push(9)
    assert.deepEqual(submitted, original, 'overview/export snapshot stays unchanged')
    assert.equal(scope.organization_id, 3)
    assert.deepEqual(purchaseDetailEntry(null, fields), { draft: null })
  })
  test('v2 supplier predicates remain native filters while legacy supplier contains retains its request parameter', () => {
    const native = c('supplier_name', 'notContains', '供应商A')
    const legacy = { ...c('supplier_name', 'contains', '旧供应商'), schemaVersion: 1 }
    assert.deepEqual(reportScope('purchase', [native]), { params: {}, conditions: [native] })
    assert.deepEqual(reportScope('purchase', [legacy]), { params: { supplier: '旧供应商' }, conditions: [] })
    const oldDraft = purchaseConditions({ keyword: '', organization_ids: [], project_code: '', supplier: '旧关联供应商', dates: [], progress: '', conditions: [] })
    assert.deepEqual(reportScope('purchase', oldDraft), { params: { supplier: '旧关联供应商' }, conditions: [] })
  })
  test('header sorting requests the whole accepted scope once, maps field names, and leaves drafts/pending page size untouched', async () => {
    assert.equal(typeof createReportColumnSort, 'function')
    const accepted = { page: 3, page_size: 50, keyword: 'ACCEPTED', organization_ids: [2], filters: '[base]', column_filters: '[columns]', project_code: 'P1', project_code_is_empty: false, sort: 'date', direction: 'desc' }
    const original = structuredClone(accepted), requests = [], columnStates = [], changes = []
    let loading = false
    const callback = createReportColumnSort({ accepted: () => accepted, loading: () => loading,
      fields: () => ({ application_date: 'date', bill_no: 'bill_no' }),
      grid: () => ({ applyColumnState: value => columnStates.push(value) }),
      changed: value => changes.push(value), load: async value => { requests.push(value) } })
    await callback('application_date', 'asc')
    assert.equal(requests.length, 1)
    assert.deepEqual(requests[0], { ...original, page: 1, sort: 'date', direction: 'asc' })
    assert.deepEqual(columnStates[0], { state: [{ colId: 'application_date', sort: 'asc' }], defaultState: { sort: null } })
    assert.deepEqual(changes, [{ sort: 'date', direction: 'asc' }])
    requests[0].organization_ids.push(9)
    assert.deepEqual(accepted, original)
    loading = true; await callback('bill_no', 'desc')
    loading = false; await callback('unsupported', 'asc')
    assert.equal(requests.length, 1, 'loading or unsupported sorting must not load or mutate state')
    assert.equal(columnStates.length, 1)
    await createReportColumnSort({ accepted: () => null, loading: () => false, fields: () => ({ bill_no: 'bill_no' }), load: () => { throw Error('not queried') } })('bill_no', 'asc')
  })
  test('plan preferences restore only known columns and supported pagination, not query values', () => {
    assert.deepEqual(reportPreferences({ visible: ['a', 'gone'], columns: [{ colId: 'a', width: 100 }, { colId: 'gone' }], pageSize: 200, keyword: 'ignored' }, ['a']), { visible: ['a'], columns: [{ colId: 'a', width: 100 }], pageSize: 200 })
    assert.deepEqual(reportPreferences({}, ['a']), {})
  })
  test('report request paging and retry retain submitted filters, ignoring later draft changes', async () => {
    const calls = []
    let reject = false
    const request = createReportRequest((draft, page, page_size) => ({ ...draft, page, page_size }), async params => {
      calls.push(params)
      if (reject) throw Error('offline')
      return { items: [params.filters], total: 10 }
    }, { items: [], total: 0, openings: [], summary: null })
    const draft = { filters: 'submitted', column_filters: 'column A', organization_ids: [1] }
    await request.query(draft, 1, 50)
    draft.filters = 'unsubmitted'
    await request.paginate(2, 50)
    assert.equal(calls.at(-1).filters, 'submitted')
    assert.equal(calls.at(-1).column_filters, 'column A')
    reject = true
    await request.query(draft, 1, 100)
    assert.equal(request.value.applied.filters, 'submitted')
    draft.filters = 'changed again'; reject = false
    await request.retry()
    assert.equal(request.value.applied.filters, 'unsubmitted')
    assert.equal(request.value.applied.page_size, 100)
  })
  test('column candidates use accepted scope, exclude only the current column and preserve null/empty selection', async () => {
    assert.equal(typeof reportColumnCandidates, 'function', 'server column candidate adapter is missing')
    const columns = [{ field: 'Stock', mode: 'values', values: [null, 'A'] }, { field: 'Unit', mode: 'values', values: [] }]
    const accepted = { keyword: 'submitted', page: 3, filters: 'query-v2', column_filters: serializeColumnFilters(columns), sort: 'bill_date', direction: 'desc' }
    let sent
    const result = await reportColumnCandidates(accepted, 'Stock', 'a', 2, async params => { sent = params; return { items: [{ value: null, label: '（空白）' }], has_more: true } })
    assert.equal(JSON.parse(sent.parameters).keyword, 'submitted')
    assert.equal(JSON.parse(sent.parameters).sort, 'bill_date')
    assert.equal(JSON.parse(sent.parameters).direction, 'desc')
    assert.equal(sent.keyword, 'a')
    assert.equal(sent.page, 2)
    assert.deepEqual(JSON.parse(sent.column_filters), [columns[1]])
    assert.deepEqual(result, { items: [{ value: null, label: '（空白）' }], hasMore: true })
    assert.deepEqual(JSON.parse(accepted.column_filters), columns)
  })
  test('changing product line resets an unchanged project selection without querying; new scheme values remain intact', () => {
    assert.equal(typeof linkReportScope, 'function', 'scope linkage adapter is missing')
    const previous = [c('organization_ids', 'reference', [1]), c('project_code', 'reference', [100])]
    const edited = [{ ...previous[0], value: [2] }, previous[1]]
    const linked = linkReportScope(edited, previous, 'organization_ids', ['project_code'])
    assert.deepEqual(linked[1].value, [])
    assert.deepEqual(previous[1].value, [100])
    const restored = [{ ...previous[0], value: [2] }, { ...previous[1], value: [200] }]
    assert.deepEqual(linkReportScope(restored, previous, 'organization_ids', ['project_code']), restored)
  })
  test('saving column preferences preserves every old personal plan and refuses corrupt source data', () => {
    assert.equal(typeof saveReportPreferences, 'function', 'legacy preservation writer is missing')
    const old = { plans: [{ name: '旧方案', filters: { project_code: 'P' } }], custom: 1, visible: ['old'] }
    const values = new Map([['legacy', JSON.stringify(old)]])
    const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
    saveReportPreferences(storage, 'legacy', { visible: ['new'] })
    assert.deepEqual(JSON.parse(values.get('legacy')), { ...old, visible: ['new'] })
    values.set('legacy', 'broken')
    assert.throws(() => saveReportPreferences(storage, 'legacy', {}))
    assert.equal(values.get('legacy'), 'broken')
  })
  test('legacy report plans migrate typed definitions plus preferences without overwriting their source', () => {
    assert.equal(typeof legacyReportSchemes, 'function', 'legacy scheme reader is missing')
    const old = [{ version: 1, name: '旧总表', state: { keyword: 'motor', project_code: 'P001', supplier: '', progress: '', organization_ids: [2], dates: [], conditions: [c('requested', 'greaterThan', 0)], overviewStatus: 'unfinished', visible: ['project_code'], columns: [], pageSize: 100 } }]
    const key = 'pms:purchase-overview:v1:991:plans', source = JSON.stringify(old)
    const storage = { getItem: name => name === key ? source : null, setItem: () => { throw Error('migration must be read only') } }
    const result = legacyReportSchemes(storage, 991, 'report-purchase-overview')
    assert.deepEqual(result.warnings, [])
    assert.equal(result.schemes[0].version, 2)
    assert.equal(result.schemes[0].name, '旧总表')
    assert.equal(result.schemes[0].preferences.overviewStatus, 'unfinished')
    assert.equal(result.schemes[0].preferences.pageSize, 100)
    assert.ok(result.schemes[0].definitions.some(d => d.field === 'keyword' && d.value === 'motor'))
    assert.ok(result.schemes[0].definitions.some(d => d.field === 'project_code' && d.operator === 'equals' && d.value === 'P001'))
  })
  test('legacy storage formats preserve detail scope, inventory selections and stock mandatory inputs', () => {
    const scope = { project_code: 'P1', organization_id: 2, product_line_name: '研发' }
    const values = new Map([
      ['pms:purchase-report:v1:991', JSON.stringify({ plans: [{ name: '采购', filters: { organization_ids: [2], project_code: '', progress: 'ordering' }, dates: [], conditions: [], scope, sort: { sort: 'date', direction: 'desc' } }] })],
      ['pms:inventory-report:v1:991:plans:v1', JSON.stringify([{ version: 1, name: '库存', state: { draft: { keyword: 'M', organization_id: 2, stock: 'W', conditions: [] }, visible: ['Stock'], pageSize: 200 } }])],
      ['pms:stock-detail:v1:991', JSON.stringify({ plans: [{ name: '收发', filters: { material: 'M', organization_id: 2, dates: ['2026-10-01', '2026-10-11'], stock_id: 3, conditions: [] }, size: 15 }] })],
    ])
    const storage = { getItem: key => values.get(key) ?? null }
    const purchase = legacyReportSchemes(storage, 991, 'report-purchase-progress')
    assert.deepEqual(purchase.schemes[0].preferences.scope, scope)
    assert.deepEqual(purchase.schemes[0].preferences.sort, { sort: 'date', direction: 'desc' })
    const inventory = legacyReportSchemes(storage, 991, 'report-inventory')
    assert.deepEqual(reportScope('inventory', inventory.schemes[0].definitions.map((d, i) => ({ ...d, id: i + 1 }))).params, { keyword: 'M', organization_id: 2 })
    assert.ok(inventory.schemes[0].definitions.some(d => d.field === 'Stock' && d.value === 'W'))
    const stock = legacyReportSchemes(storage, 991, 'report-stock-detail')
    assert.deepEqual(stock.warnings, [])
    assert.deepEqual(reportScope('stock-detail', stock.schemes[0].definitions.map((d, i) => ({ ...d, id: i + 1 }))).params, { material: 'M', organization_ids: [2], stock_id: 3, start_date: '2026-10-01', end_date: '2026-10-11' })
    assert.equal(stock.schemes[0].preferences.pageSize, 15)
    assert.equal(values.size, 3)
  })
  test('legacy invalid and duplicate schemes are reported without dropping their source or valid siblings', () => {
    const plans = [{ name: '重复', filters: { material: 'M' } }, { name: '重复', filters: { material: 'N' } }, { name: '坏条件', filters: { conditions: 'not-an-array' } }]
    const source = JSON.stringify({ plans })
    const migrated = legacyReportSchemes({ getItem: () => source }, 991, 'report-stock-detail')
    assert.equal(migrated.schemes.length, 1)
    assert.equal(migrated.warnings.length, 2)
    assert.match(migrated.warnings.join(' '), /原记录已保留/)
    assert.equal(JSON.parse(source).plans.length, 3)
  })
}
