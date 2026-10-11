import { computed, ref } from 'vue'
import { cloneQuery, isEmpty, matchesConditions, validateConditions, type QueryCondition, type QueryField } from './core.ts'
import type { QueryDefinition } from './workspace.ts'
import { clientColumnCandidates, matchesColumnFilters, type ColumnFilter, type ColumnQueryContext } from './column-filters.ts'

export function serverQueryParams(conditions: QueryCondition[], columns: ColumnFilter[]) {
  return { filters: JSON.stringify(conditions.map(condition => ({...condition,schemaVersion:2}))), column_filters: JSON.stringify(columns) }
}
export function requireServerQueryVersion(result: { query_version?: number }, filtered: boolean) {
  const supported = result.query_version === 2
  if (filtered && !supported) throw Error('服务端尚未支持查询 v2 协议，未应用本页过滤')
  return supported
}

// Pages own data and layout; the workspace alone owns personal schemes.
export function useSystemQuery(source: () => QueryField[], shown: string[], capability: {ready?: () => boolean; requireQuery?: boolean} = {}) {
  const fields = computed(source)
  const defaults = computed<QueryDefinition[]>(() => [...shown.map(key => fields.value.find(field => field.field === key)).filter((field): field is QueryField => !!field), ...fields.value.filter(field => !shown.includes(field.field))].map(field => ({
    field: field.field, shown: shown.includes(field.field),
    operator: field.type === 'enum' ? 'in' : field.type === 'text' ? 'contains' : 'equals',
    value: null, valueEnd: null, schemaVersion: 2,
  })))
  const draft = ref<QueryCondition[]>([])
  const applied = ref<QueryCondition[]>([])
  const columnFilters = ref<ColumnFilter[]>([])
  const submitted = ref(false)
  let resultRows: Record<string, unknown>[] = []
  function submit(conditions: QueryCondition[]) {
    const errors = validateConditions(conditions, fields.value)
    if (Object.keys(errors).length) throw Error(Object.values(errors).join('；'))
    applied.value = cloneQuery(conditions)
    submitted.value = true
  }
  function topRows<T>(rows: T[], record: (row: T) => Record<string, unknown> = row => row as Record<string, unknown>): T[] {
    return rows.filter(row => matchesConditions(normalizeRecord(record(row)), applied.value, fields.value))
  }
  function normalizeRecord(row: Record<string, unknown>) {
    const result = {...row}
    for (const field of fields.value) {
      const value = row[field.field]
      if (isEmpty(value)) continue
      if (field.type === 'date') result[field.field] = String(value).slice(0,10)
      if (field.type === 'number' && Number.isFinite(Number(value))) result[field.field] = Number(value)
      if (field.type === 'enum') result[field.field] = field.options?.find(option => String(option.value) === String(value))?.value ?? value
    }
    return result
  }
  function setResultRows(rows: Record<string, unknown>[]) { resultRows = rows }
  function filterRows<T>(rows: T[], record: (row: T) => Record<string, unknown> = row => row as Record<string, unknown>): T[] {
    const result = topRows(rows, record)
    setResultRows(result.map(row => normalizeRecord(record(row))))
    return result.filter(row => matchesColumnFilters(normalizeRecord(record(row)), columnFilters.value, fields.value))
  }
  function clearColumns() { if (columnFilters.value.length) columnFilters.value = [] }
  function columnClass(field: string) { return columnFilters.value.some(filter => filter.field === field) ? 'pms-query-filtered-column' : '' }
  const columnContext: ColumnQueryContext = {
    ready: () => (!capability.requireQuery || submitted.value) && (capability.ready?.() ?? true),
    fields: () => fields.value,
    filters: () => columnFilters.value,
    load: async (field, keyword, page) => {
      if (!columnContext.ready?.()) throw Error('请先完成查询，再使用列筛选')
      return clientColumnCandidates(resultRows, fields.value, columnFilters.value, field, keyword, page)
    },
    apply: (field, filter) => { columnFilters.value = [...columnFilters.value.filter(item => item.field !== field), ...(filter ? [cloneQuery(filter)] : [])] },
  }
  return { fields, defaults, draft, applied, submitted, submit, topRows, filterRows, columnFilters, clearColumns, columnContext, setResultRows, columnClass }
}

export async function loadCompleteDataset<T, R extends { items: T[]; total: number }>(
  load: (page: number, pageSize: number) => Promise<R>, pageSize: number, current = () => true, identity?: (row: T) => string | number,
): Promise<R> {
  const items: T[] = []
  let first: R | undefined
  const seen = new Set<string | number>()
  for (let page = 1; page <= 1000; page++) {
    if (!current()) throw Error('查询已取消')
    const result = await load(page, pageSize)
    if (!current()) throw Error('查询已取消')
    if (!Array.isArray(result.items) || !Number.isSafeInteger(result.total) || result.total < 0) throw Error('查询数据不完整，请刷新重试')
    first ??= result
    if (result.total !== first.total) throw Error('查询期间数据发生变化，请刷新重试')
    if (identity) for (const row of result.items) {
      const key = identity(row)
      if (seen.has(key)) throw Error('跨页数据重复，查询期间数据发生变化，请刷新重试')
      seen.add(key)
    }
    items.push(...result.items)
    if (items.length === result.total) return { ...first, items }
    if (!result.items.length || items.length > result.total) throw Error('查询数据不完整，请刷新重试')
  }
  throw Error('数据量超出完整查询范围，需要服务端查询协议；未应用部分数据')
}
