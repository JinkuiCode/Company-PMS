import { cloneQuery, type QueryCondition } from '../query-system/core.ts'
import type { ColumnFilter } from '../query-system/column-filters.ts'

export type BusinessExportSnapshot = {
  parameters: Record<string, unknown>
  filters: QueryCondition[]
  column_filters: ColumnFilter[]
  sort: { colId: string; sort: 'asc' | 'desc' }[]
  columns: string[]
}
type ExportColumn = { getColId: () => string; getColDef: () => { field?: string } }
type ExportGrid = {
  getAllDisplayedColumns: () => ExportColumn[]
  getColumnState: () => { colId: string; sort?: 'asc' | 'desc' | null; sortIndex?: number | null }[]
  getColumn: (id: string) => ExportColumn | null | undefined
}
function columnKey(column: ExportColumn | null | undefined) {
  return column?.getColDef().field || (column?.getColId().startsWith('sheet:') ? column.getColId() : undefined)
}

export function businessExportSnapshot(filters: QueryCondition[], columnFilters: ColumnFilter[], grid: ExportGrid | null | undefined, parameters: Record<string, unknown> = {}): BusinessExportSnapshot {
  if (!grid) throw Error('请等待表格加载完成')
  const columns = grid.getAllDisplayedColumns().map(columnKey).filter((key): key is string => !!key)
  if (!columns.length) throw Error('没有可见业务列可导出')
  const sort = grid.getColumnState().filter(state => state.sort === 'asc' || state.sort === 'desc')
    .sort((a, b) => (a.sortIndex ?? Number.MAX_SAFE_INTEGER) - (b.sortIndex ?? Number.MAX_SAFE_INTEGER))
    .map(state => {
      const colId = columnKey(grid.getColumn(state.colId))
      if (!colId) throw Error('排序字段已失效，请刷新重试')
      return { colId, sort: state.sort as 'asc' | 'desc' }
    })
  return cloneQuery({ parameters, filters, column_filters: columnFilters, sort, columns })
}
