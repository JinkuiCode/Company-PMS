import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'

const moduleUrl = new URL('../src/business-export/snapshot.ts', import.meta.url)
assert.ok(existsSync(moduleUrl), 'Business export must have a shared submitted-query snapshot')
const { businessExportSnapshot } = await import(moduleUrl.href)
const column = (id, field) => ({ getColId: () => id, getColDef: () => ({ field }) })
const columns = [column('project_name', 'project_name'), column('sheet:arrival', undefined), column('progress_actions', undefined)]
const hidden = column('pm_name', 'pm_name')
const grid = {
  getAllDisplayedColumns: () => columns,
  getColumnState: () => [
    { colId: 'project_name', sort: 'asc', sortIndex: 1 },
    { colId: 'pm_name', sort: 'desc', sortIndex: 0, hide: true },
    { colId: 'sheet:arrival', sort: null },
  ],
  getColumn: id => [...columns, hidden].find(c => c.getColId() === id),
}
const applied = [{ id: 1, field: 'status', operator: 'in', value: [2], valueEnd: null, schemaVersion: 2 }]
const filters = [{ field: 'project_name', mode: 'values', values: ['设备A', null] }]
const snapshot = businessExportSnapshot(applied, filters, grid)
assert.deepEqual(snapshot.filters, applied)
assert.deepEqual(snapshot.column_filters, filters)
assert.deepEqual(snapshot.columns, ['project_name', 'sheet:arrival'], 'Displayed order only, no hidden/action columns')
assert.deepEqual(snapshot.sort, [{ colId: 'pm_name', sort: 'desc' }, { colId: 'project_name', sort: 'asc' }], 'Preserve multi-sort priority, including hidden sorted columns')
assert.deepEqual(snapshot.parameters, {}, 'Parameters match the business export API')
assert.deepEqual(Object.keys(snapshot).sort(), ['column_filters', 'columns', 'filters', 'parameters', 'sort'], 'Export full results, not page/row IDs')
applied[0].value.push(3)
filters[0].values.length = 0
columns.reverse()
assert.deepEqual(snapshot.filters[0].value, [2], 'Pending export keeps its submitted snapshot')
assert.deepEqual(snapshot.column_filters[0].values, ['设备A', null])
assert.deepEqual(snapshot.columns, ['project_name', 'sheet:arrival'])
assert.throws(() => businessExportSnapshot([], [], null), /表格/)
assert.throws(() => businessExportSnapshot([], [], { ...grid, getAllDisplayedColumns: () => [column('actions')] }), /可见/)
console.log('business export snapshot passed: applied query, columns, blank values, full results and sort priority')
