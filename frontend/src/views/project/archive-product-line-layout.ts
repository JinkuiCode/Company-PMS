import type { PmsColumnPreference } from '@/list-system/columnPreferences'
import type { ColumnState } from 'ag-grid-community'

export const ARCHIVE_PRODUCT_LINE_LAYOUT_VERSION = 1
const LINE = 'product_line_id'
const CODE = 'project_code'
const SELECTION = 'archive_selection'

/** Initial defaults only: stateful pinning would undo a user's later unpin. */
export function archiveProductLineDefaultColumns<T extends { colId?: string; pinned?: unknown }>(columns: T[], canShow: boolean): T[] {
  const defaults = columns.map(column => [LINE, CODE].includes(column.colId || '')
    ? { ...column, initialPinned: 'left', pinned: undefined } : { ...column })
  if (!canShow || !defaults.some(column => column.colId === LINE)) return defaults
  const leading = [SELECTION, LINE, CODE]
  return [...leading.flatMap(key => defaults.filter(column => column.colId === key)),
    ...defaults.filter(column => !leading.includes(column.colId || ''))]
}

/** Project the old layout once; do not mutate storage or any other preference. */
export function migrateArchiveProductLineLayout(value: PmsColumnPreference, current: ColumnState[], canShow: boolean): PmsColumnPreference {
  if (!canShow || value.layout_version === ARCHIVE_PRODUCT_LINE_LAYOUT_VERSION) return value
  const existing = new Map(value.columnState.map(column => [column.colId, column]))
  const baseline = new Map(current.map(column => [column.colId, column]))
  const order = [...new Set([...existing.keys(), ...baseline.keys()])]
  const leading = [SELECTION, LINE, CODE].filter(key => order.includes(key))
  const columns = [...leading, ...order.filter(key => !leading.includes(key))].map(colId => {
    const state = { ...(existing.get(colId) || baseline.get(colId)), colId }
    return colId === LINE || colId === CODE ? { ...state, pinned: 'left' as const, ...(colId === LINE ? { hide: false } : {}) } : state
  })
  return {
    layout_version: ARCHIVE_PRODUCT_LINE_LAYOUT_VERSION,
    selected_column_keys: [LINE, ...value.selected_column_keys.filter(key => key !== LINE)],
    columnState: columns,
  }
}
