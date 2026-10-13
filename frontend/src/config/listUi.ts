import type { ColumnState, GridOptions } from 'ag-grid-community'

export const DEFAULT_PAGE_SIZE = 50
export const PAGE_SIZE_OPTIONS = [15, 20, 50, 100, 200, 300, 500]
export function pmsActionColumn(count = 1) {
  const width = count <= 1 ? 64 : count === 2 ? 96 : 16 + count * 40
  return { width, minWidth: width, maxWidth: width, resizable: false, flex: 0 }
}
export const PMS_ACTION_COLUMN = pmsActionColumn(2)
export const PMS_SINGLE_ACTION_COLUMN = pmsActionColumn(1)

export function normalizeActionColumnState<T extends Partial<ColumnState> & { colId: string }>(state: T[], key: string, count = 1): T[] {
  return state.map(column => column.colId === key
    ? { ...column, width: pmsActionColumn(count).width, flex: null, hide: false, pinned: 'right' as const }
    : { ...column })
}
export const PMS_GRID_OPTIONS: GridOptions = {
  rowHeight: 32,
  headerHeight: 30,
  groupHeaderHeight: 26,
  tooltipShowDelay: 200,
  tooltipHideDelay: 10000,
  tooltipInteraction: true,
}
export const PMS_TABLE_CONFIG = {
  showOverflowTooltip: true,
  tooltipOptions: { showAfter: 200, hideAfter: 100, enterable: true },
}
