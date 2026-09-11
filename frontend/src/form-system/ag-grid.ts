import type { CellClassParams, ColDef } from 'ag-grid-community'

export const PMS_AG_GRID_FORM_CLASS = 'pms-form-grid'

function normalizeCellClass(value: string | string[] | null | undefined): string[] {
  if (!value) return []
  return Array.isArray(value) ? value : [value]
}

export function mergePmsAgCellClass<TData>(definition: ColDef<TData>): ColDef<TData> {
  const existing = definition.cellClass
  return {
    ...definition,
    cellClass: (params: CellClassParams<TData>) => {
      const base = typeof existing === 'function' ? existing(params) : existing
      return [...normalizeCellClass(base), 'pms-form-grid__cell']
    },
  }
}
