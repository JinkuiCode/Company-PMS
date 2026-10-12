import type { GridOptions } from 'ag-grid-community'

export const DEFAULT_PAGE_SIZE = 50
export const PAGE_SIZE_OPTIONS = [15, 20, 50, 100, 200, 300, 500]
export const PMS_ACTION_COLUMN = {
  width: 112,
  minWidth: 112,
  maxWidth: 112,
  resizable: false,
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
