import { computed, watch, type Ref } from 'vue'
import { cloneQuery, isEmpty, type QueryField } from './core.ts'
import { clientColumnCandidates, matchesColumnFilters, type ColumnFilter, type ColumnQueryContext } from './column-filters.ts'
import { columnPopupGroup } from './column-popup.ts'

export function normalizeColumnRecord(row: Record<string, unknown>, fields: QueryField[]) {
  const result = { ...row }
  for (const field of fields) {
    const value = result[field.field]
    if (isEmpty(value)) continue
    if (field.type === 'date') result[field.field] = String(value).slice(0, 10)
    if (field.type === 'number' && Number.isFinite(Number(value))) result[field.field] = Number(value)
    if (field.type === 'enum') result[field.field] = field.options?.find(o => String(o.value) === String(value))?.value ?? value
  }
  return result
}

// Consumers supply the accepted, unfiltered page, never the full query dataset.
export function usePageColumnFilter<T>(rows: Readonly<Ref<T[]>>, fields: () => QueryField[], filters: Ref<ColumnFilter[]>,
  boundary: () => unknown[], record: (row: T) => Record<string, unknown> = row => row as Record<string, unknown>, ready: () => boolean = () => true) {
  const normalized = () => rows.value.map(row => normalizeColumnRecord(record(row), fields()))
  const clear = () => { columnPopupGroup.close(); if (filters.value.length) filters.value = [] }
  watch([() => rows.value, ...boundary().map((_, i) => () => boundary()[i])], clear, { flush: 'sync' })
  const context: ColumnQueryContext = {
    ready, fields, filters: () => filters.value,
    load: async (field, keyword, page) => {
      if (!ready()) throw Error('请先完成查询，再使用列筛选')
      return clientColumnCandidates(normalized(), fields(), filters.value, field, keyword, page)
    },
    apply: (field, filter) => {
      if (!ready()) return
      filters.value = [...filters.value.filter(item => item.field !== field), ...(filter ? [cloneQuery(filter)] : [])]
    },
  }
  const filterRows = (source: T[]) => source.filter(row => matchesColumnFilters(normalizeColumnRecord(record(row), fields()), filters.value, fields()))
  const visibleRows = computed(() => filterRows(rows.value))
  return { context, visibleRows, filterRows, clear }
}
