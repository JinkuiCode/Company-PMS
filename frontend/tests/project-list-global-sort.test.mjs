import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import { computed, effectScope, ref } from 'vue'
import { _defaultComparator } from 'ag-grid-community'
import { useSystemQuery } from '../src/query-system/system-adapter.ts'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '../src/config/listUi.ts'

const source = readFileSync(new URL('../src/views/project/ProjectList.vue', import.meta.url), 'utf8')
const script = parse(source).descriptor.scriptSetup.content
const ast = ts.createSourceFile('ProjectList.ts', script, ts.ScriptTarget.Latest, true)
const sorter = await import('../src/query-system/client-row-sort.ts').catch(error => {
  if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error
  return {}
})

function declaration(name) {
  const node = ast.statements.find(statement =>
    ts.isVariableStatement(statement)
      ? statement.declarationList.declarations.some(item => item.name.getText(ast) === name)
      : ts.isFunctionDeclaration(statement) && statement.name?.text === name)
  return node?.getText(ast) || ''
}

function execute(code, bindings, result) {
  const js = ts.transpile(code, { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None })
  return new Function(...Object.keys(bindings), `${js}\nreturn ${result}`)(...Object.values(bindings))
}

function list(rows, state, pageSize = 2) {
  const page = ref(1), size = ref(pageSize), rowData = ref(structuredClone(rows)), progressSort = ref(state)
  const fields = ref([
    { field: 'project_code', label: 'Project', type: 'text' },
    { field: 'status', label: 'Status', type: 'number' },
  ])
  const query = useSystemQuery(() => fields.value, ['project_code'], { pagination: { page, size } })
  query.submit([])
  // Execute the production computed pipeline, not a duplicate sort/page implementation.
  const pipeline = execute(
    ['sheetFieldValue', 'filteredRowData', 'sortedRowData', 'pagedRowData'].map(declaration).join('\n'),
    { computed, rowData, progressSort, projectListFilterFields: fields, toQueryRecord: row => row,
      topRows: query.topRows, pageRows: query.pageRows, sortClientRows: sorter.sortClientRows },
    '{ filteredRowData, pagedRowData }',
  )
  return { ...pipeline, query, page, size, rowData, progressSort }
}

const rows = [5, 4, 3, 2, 1, 6].map(value => ({
  id: value, project_code: `P${value}`, status: value % 2,
  sheet_fields: { score: 7 - value },
}))
const codes = result => result.map(row => row.project_code)

test('production pipeline sorts the complete result before splitting multiple pages', () => {
  const scope = effectScope()
  scope.run(() => {
    const view = list(rows, [{ colId: 'project_code', sort: 'asc' }])
    assert.deepEqual(codes(view.pagedRowData.value), ['P1', 'P2'], 'first page must include records originally on later pages')
    view.page.value = 2
    assert.deepEqual(codes(view.pagedRowData.value), ['P3', 'P4'])
    view.page.value = 3
    assert.deepEqual(codes(view.pagedRowData.value), ['P5', 'P6'])
    view.progressSort.value = [{ colId: 'project_code', sort: 'desc' }]
    assert.deepEqual(codes(view.pagedRowData.value), ['P2', 'P1'])
    view.page.value = 1
    assert.deepEqual(codes(view.pagedRowData.value), ['P6', 'P5'])
    view.progressSort.value = []
    assert.deepEqual(codes(view.pagedRowData.value), ['P5', 'P4'], 'clearing sorting restores source order')
    assert.deepEqual(codes(view.rowData.value), codes(rows), 'sorting must not mutate the loaded result')
  })
  scope.stop()
})

test('top query is global, but funnel values and candidates stay on the sorted current page', async () => {
  const scope = effectScope()
  await scope.run(async () => {
    const view = list(rows, [{ colId: 'project_code', sort: 'asc' }])
    view.query.submit([{ id: 1, field: 'status', operator: 'equals', value: 1, valueEnd: null, schemaVersion: 2 }])
    assert.deepEqual(codes(view.pagedRowData.value), ['P1', 'P3'])
    assert.equal(view.filteredRowData.value.length, 3)
    view.query.columnContext.apply('project_code', { field: 'project_code', mode: 'values', values: ['P3', 'P5'] })
    assert.deepEqual(codes(view.pagedRowData.value), ['P3'], 'a matching value on the next page must not refill this page')
    assert.deepEqual((await view.query.columnContext.load('project_code', '', 1)).items.map(item => item.value), ['P1', 'P3'])
    assert.equal(view.filteredRowData.value.length, 3, 'column filters must not change the pagination total')
    assert.equal(view.page.value, 1)
    view.page.value = 2
    assert.deepEqual(view.query.columnFilters.value, [])
    assert.deepEqual(codes(view.pagedRowData.value), ['P5'])
  })
  scope.stop()
})

test('500-row pages retain globally sorted boundaries without pulling funnel matches from another page', () => {
  const scope = effectScope()
  scope.run(() => {
    const data = Array.from({ length: 1001 }, (_, index) => {
      const id = 1001 - index
      return { id, project_code: `P${String(id).padStart(4, '0')}`, status: 1 }
    })
    const view = list(data, [{ colId: 'project_code', sort: 'asc' }], 500)
    assert.equal(view.pagedRowData.value.length, 500)
    assert.equal(view.pagedRowData.value[0].id, 1)
    assert.equal(view.pagedRowData.value.at(-1).id, 500)
    view.query.columnContext.apply('project_code', { field: 'project_code', mode: 'values', values: ['P0500', 'P0501'] })
    assert.deepEqual(view.pagedRowData.value.map(row => row.id), [500])
    assert.equal(view.filteredRowData.value.length, 1001)
    view.page.value = 2
    assert.equal(view.pagedRowData.value[0].id, 501)
    assert.equal(view.pagedRowData.value.at(-1).id, 1000)
    view.page.value = 3
    assert.deepEqual(view.pagedRowData.value.map(row => row.id), [1001])
  })
  scope.stop()
})

test('dynamic sheet columns use their grid getter values across pages and react to updates', () => {
  const scope = effectScope()
  scope.run(() => {
    const view = list(rows, [{ colId: 'sheet:score', sort: 'asc' }])
    assert.deepEqual(codes(view.pagedRowData.value), ['P6', 'P5'])
    view.rowData.value.find(row => row.id === 1).sheet_fields.score = 0
    assert.deepEqual(codes(view.pagedRowData.value), ['P1', 'P6'])
  })
  scope.stop()
})

test('sort state preserves multi-sort priority, ignores cleared columns, and keeps equal rows stable', () => {
  assert.equal(typeof sorter.columnSortModel, 'function')
  assert.equal(typeof sorter.sortClientRows, 'function')
  const state = sorter.columnSortModel([
    { colId: 'name', sort: 'desc', sortIndex: 1, width: 150 },
    { colId: 'cleared', sort: null, sortIndex: 0 },
    { colId: 'group', sort: 'asc', sortIndex: 0 },
  ])
  assert.deepEqual(state, [{ colId: 'group', sort: 'asc' }, { colId: 'name', sort: 'desc' }])
  const data = [{ id: 1, group: 2, name: 'A' }, { id: 2, group: 1, name: 'A' },
    { id: 3, group: 1, name: 'B' }, { id: 4, group: 1, name: 'B' }]
  assert.deepEqual(sorter.sortClientRows(data, state, (row, field) => row[field]).map(row => row.id), [3, 4, 2, 1])
  const values = [{ value: null }, { value: 10 }, { value: 2 }, { value: undefined }, { value: 0 }]
  for (const sort of ['asc', 'desc']) {
    assert.deepEqual(sorter.sortClientRows(values, [{ colId: 'value', sort }], row => row.value),
      [...values].sort((a, b) => _defaultComparator(a.value, b.value) * (sort === 'asc' ? 1 : -1)),
      'numeric and empty ordering must remain identical to AG Grid')
  }
})

test('grid sort events, including restored/cleared states, drive the global sort and clear stale page filters', () => {
  assert.match(source, /@sort-changed="handleProgressSortChanged"/)
  let state = [{ colId: 'project_code', sort: 'desc', sortIndex: 0, width: 112 }]
  let cleared = 0, persisted = 0
  const progressSort = ref([])
  const sync = execute(declaration('handleProgressSortChanged'), {
    progressSort, columnSortModel: sorter.columnSortModel,
    gridApi: ref({ getColumnState: () => state }),
    clearColumns: () => cleared++, handleGridStructureChanged: () => persisted++,
  }, 'handleProgressSortChanged')
  sync()
  assert.deepEqual(progressSort.value, [{ colId: 'project_code', sort: 'desc' }])
  assert.equal(cleared, 1)
  state = [{ ...state[0], width: 180 }]
  sync()
  assert.equal(cleared, 1, 'width changes must not invalidate a page funnel')
  state = [{ colId: 'project_code', sort: null }]
  sync()
  assert.deepEqual(progressSort.value, [])
  assert.equal(cleared, 2)
  assert.equal(persisted, 2)
})

test('initial saved sorting is synchronized before enabling preference writes', () => {
  const calls = [], columnPreferenceWritesEnabled = ref(false)
  const complete = execute(declaration('completeColumnPreferenceRestore'), {
    columnPreferencesReady: ref(true), gridApi: ref({}), columnPreferenceWritesEnabled,
    restoreColumnState: () => calls.push('restore'),
    handleProgressSortChanged: () => { assert.equal(columnPreferenceWritesEnabled.value, false); calls.push('sort') },
  }, 'completeColumnPreferenceRestore')
  complete()
  assert.deepEqual(calls, ['restore', 'sort'])
  assert.equal(columnPreferenceWritesEnabled.value, true)
})

test('changing grid sort re-slices the complete result and invalidates the old page funnel', () => {
  const scope = effectScope()
  scope.run(() => {
    const view = list(rows, [{ colId: 'project_code', sort: 'asc' }])
    view.query.columnContext.apply('project_code', { field: 'project_code', mode: 'values', values: ['P1'] })
    assert.deepEqual(codes(view.pagedRowData.value), ['P1'])
    const sync = execute(declaration('handleProgressSortChanged'), {
      progressSort: view.progressSort, columnSortModel: sorter.columnSortModel,
      gridApi: ref({ getColumnState: () => [{ colId: 'project_code', sort: 'desc' }] }),
      clearColumns: view.query.clearColumns, handleGridStructureChanged: () => {},
    }, 'handleProgressSortChanged')
    sync()
    assert.deepEqual(view.query.columnFilters.value, [])
    assert.deepEqual(codes(view.pagedRowData.value), ['P6', 'P5'])
    assert.equal(view.page.value, 1)
  })
  scope.stop()
})

test('personal schemes restore only approved numeric page sizes and retain default 50', () => {
  assert.equal(DEFAULT_PAGE_SIZE, 50)
  assert.deepEqual(PAGE_SIZE_OPTIONS, [15, 20, 50, 100, 200, 300, 500])
  const pageSize = execute(declaration('pageSize'), { ref, DEFAULT_PAGE_SIZE }, 'pageSize')
  assert.equal(pageSize.value, 50)
  const run = execute(declaration('runQuery'), {
    submitQuery: () => {}, pageSize, PAGE_SIZE_OPTIONS,
    selectedSheetFieldKeys: ref([]), sheetFieldMetaMap: ref(new Map()), gridApi: ref(null),
  }, 'runQuery')
  for (const value of PAGE_SIZE_OPTIONS) {
    run([], { pageSize: value })
    assert.equal(pageSize.value, value)
  }
  for (const value of [0, 14, 16, 201, 499, 501, 1000, -1, 1.5, Infinity, NaN, '500', null, undefined]) {
    pageSize.value = DEFAULT_PAGE_SIZE
    run([], { pageSize: value })
    assert.equal(pageSize.value, 50, `invalid saved size ${String(value)} must not override the default`)
  }
})
