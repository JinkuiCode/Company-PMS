import type { ColumnState } from 'ag-grid-community'

type OverviewLayout = {
  visible?: string[]
  columns?: ColumnState[]
  metricLayoutVersion?: number
  [key: string]: unknown
}

export function migrateOverviewLayout(value: object): OverviewLayout {
  const input = value as OverviewLayout
  if (input.metricLayoutVersion === 1) return input
  const next = { ...input, metricLayoutVersion: 1 }
  if (Array.isArray(input.visible)) {
    next.visible = ['product_line_name', ...input.visible.filter(key => key !== 'product_line_name' && key !== 'conversion_rate')]
    const index = next.visible.indexOf('completion_rate')
    next.visible.splice(index < 0 ? next.visible.length : index + 1, 0, 'conversion_rate')
  }
  if (Array.isArray(input.columns) && input.columns.length) {
    const line = input.columns.find(column => column.colId === 'product_line_name')
    const conversion = input.columns.find(column => column.colId === 'conversion_rate')
    next.columns = [{ ...line, colId: 'product_line_name', hide: false, pinned: 'left' },
      ...input.columns.filter(column => !['product_line_name', 'conversion_rate'].includes(column.colId))]
    const index = next.columns.findIndex(column => column.colId === 'completion_rate')
    next.columns.splice(index < 0 ? next.columns.length : index + 1, 0,
      { sort: null, sortIndex: null, ...conversion, colId: 'conversion_rate', hide: false })
  }
  return next
}
