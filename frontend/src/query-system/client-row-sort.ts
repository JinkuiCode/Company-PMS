import { _defaultComparator, type ColumnState } from 'ag-grid-community'

export type ClientRowSort = { colId: string; sort: 'asc' | 'desc' }

export function columnSortModel(columns: readonly Pick<ColumnState, 'colId' | 'sort' | 'sortIndex'>[]): ClientRowSort[] {
  return columns
    .filter(column => column.sort === 'asc' || column.sort === 'desc')
    .sort((a, b) => (a.sortIndex ?? Infinity) - (b.sortIndex ?? Infinity))
    .map(column => ({ colId: column.colId, sort: column.sort as ClientRowSort['sort'] }))
}

export function sortClientRows<T>(rows: T[], model: readonly ClientRowSort[], value: (row: T, colId: string) => unknown): T[] {
  if (!model.length) return rows
  // Keep AG Grid's raw-value/null ordering and stable ties before slicing a page.
  return [...rows].sort((a, b) => {
    for (const column of model) {
      const compared = _defaultComparator(value(a, column.colId), value(b, column.colId))
      if (compared) return column.sort === 'asc' ? compared : -compared
    }
    return 0
  })
}
