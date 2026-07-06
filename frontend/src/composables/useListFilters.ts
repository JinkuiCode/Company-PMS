import { computed, ref, toValue, type MaybeRefOrGetter } from 'vue'

export type ListFilterType = 'text' | 'select' | 'date' | 'number'
export type ListFilterOperator =
  | 'contains'
  | 'equals'
  | 'notEquals'
  | 'before'
  | 'after'
  | 'greaterThan'
  | 'lessThan'
  | 'between'

export type ListFilterValue = string | number | null

export type ListFilterOption = {
  label: string
  value: string | number
}

export type ListFilterField<T = Record<string, any>> = {
  field: string
  label: string
  type: ListFilterType
  operators?: ListFilterOperator[]
  options?: () => ListFilterOption[]
  getValue?: (row: T) => unknown
}

export type ListCustomFilter = {
  id: number
  field: string
  operator: ListFilterOperator
  value: ListFilterValue
  valueEnd: ListFilterValue
}

export const listFilterOperatorLabels: Record<ListFilterOperator, string> = {
  contains: '包含',
  equals: '等于',
  notEquals: '不等于',
  before: '早于',
  after: '晚于',
  greaterThan: '大于',
  lessThan: '小于',
  between: '介于',
}

export function defaultListFilterOperators(type: ListFilterType): ListFilterOperator[] {
  if (type === 'select') return ['equals', 'notEquals']
  if (type === 'date') return ['equals', 'before', 'after', 'between']
  if (type === 'number') return ['equals', 'greaterThan', 'lessThan', 'between']
  return ['contains', 'equals']
}

function emptyListFilterValue(type: ListFilterType): ListFilterValue {
  return type === 'number' ? null : ''
}

export function createListFilter<T = Record<string, any>>(field: ListFilterField<T>, id: number): ListCustomFilter {
  const operators = field.operators || defaultListFilterOperators(field.type)
  return {
    id,
    field: field.field,
    operator: operators[0],
    value: emptyListFilterValue(field.type),
    valueEnd: emptyListFilterValue(field.type),
  }
}

export function getListFilterField<T>(fields: ListFilterField<T>[], field: string) {
  return fields.find(item => item.field === field)
}

export function getListFilterOperators<T>(fields: ListFilterField<T>[], field: string) {
  const filterField = getListFilterField(fields, field)
  if (!filterField) return []
  return filterField.operators || defaultListFilterOperators(filterField.type)
}

export function isEmptyListFilterValue(value: unknown) {
  return value === null || value === undefined || value === ''
}

export function hasListFilterValue(filter: ListCustomFilter) {
  if (filter.operator === 'between') {
    return !isEmptyListFilterValue(filter.value) && !isEmptyListFilterValue(filter.valueEnd)
  }
  return !isEmptyListFilterValue(filter.value)
}

function normalizeTextValue(value: unknown) {
  return String(value ?? '').trim().toLowerCase()
}

function normalizeDateValue(value: unknown) {
  return String(value ?? '').slice(0, 10)
}

function normalizeNumberValue(value: unknown) {
  if (isEmptyListFilterValue(value)) return null
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function getRowFilterValue<T>(row: T, field: ListFilterField<T>) {
  if (field.getValue) return field.getValue(row)
  return (row as any)[field.field]
}

export function matchesListFilter<T>(row: T, filter: ListCustomFilter, fields: ListFilterField<T>[]) {
  if (!hasListFilterValue(filter)) return true

  const field = getListFilterField(fields, filter.field)
  if (!field) return true

  const rowValue = getRowFilterValue(row, field)

  if (field.type === 'date') {
    const rowDate = normalizeDateValue(rowValue)
    const filterDate = normalizeDateValue(filter.value)
    const filterEndDate = normalizeDateValue(filter.valueEnd)
    if (!rowDate || !filterDate) return false

    if (filter.operator === 'equals') return rowDate === filterDate
    if (filter.operator === 'before') return rowDate < filterDate
    if (filter.operator === 'after') return rowDate > filterDate
    if (filter.operator === 'between') {
      if (!filterEndDate) return false
      const startDate = filterDate <= filterEndDate ? filterDate : filterEndDate
      const endDate = filterDate <= filterEndDate ? filterEndDate : filterDate
      return rowDate >= startDate && rowDate <= endDate
    }
    return true
  }

  if (field.type === 'number') {
    const rowNumber = normalizeNumberValue(rowValue)
    const filterNumber = normalizeNumberValue(filter.value)
    const filterEndNumber = normalizeNumberValue(filter.valueEnd)
    if (rowNumber === null || filterNumber === null) return false

    if (filter.operator === 'equals') return rowNumber === filterNumber
    if (filter.operator === 'greaterThan') return rowNumber > filterNumber
    if (filter.operator === 'lessThan') return rowNumber < filterNumber
    if (filter.operator === 'between') {
      if (filterEndNumber === null) return false
      const startNumber = Math.min(filterNumber, filterEndNumber)
      const endNumber = Math.max(filterNumber, filterEndNumber)
      return rowNumber >= startNumber && rowNumber <= endNumber
    }
    return true
  }

  const normalizedRowValue = normalizeTextValue(rowValue)
  const normalizedFilterValue = normalizeTextValue(filter.value)

  if (filter.operator === 'contains') {
    return normalizedRowValue.includes(normalizedFilterValue)
  }
  if (filter.operator === 'equals') {
    return normalizedRowValue === normalizedFilterValue
  }
  if (filter.operator === 'notEquals') {
    return normalizedRowValue !== normalizedFilterValue
  }
  return true
}

export function useListFilters<T>(fields: MaybeRefOrGetter<ListFilterField<T>[]>) {
  const customFilters = ref<ListCustomFilter[]>([])
  const filterSequence = ref(1)

  const activeCustomFilterCount = computed(() => customFilters.value.filter(hasListFilterValue).length)

  function addCustomFilter() {
    const firstField = toValue(fields)[0]
    if (!firstField) return
    customFilters.value.push(createListFilter(firstField, filterSequence.value++))
  }

  function removeCustomFilter(id: number) {
    customFilters.value = customFilters.value.filter(filter => filter.id !== id)
  }

  function clearCustomFilters() {
    customFilters.value = []
  }

  function applyCustomFilters(rows: T[]) {
    const fieldList = toValue(fields)
    const activeFilters = customFilters.value.filter(hasListFilterValue)
    if (!activeFilters.length) return rows
    return rows.filter(row => activeFilters.every(filter => matchesListFilter(row, filter, fieldList)))
  }

  return {
    customFilters,
    activeCustomFilterCount,
    addCustomFilter,
    removeCustomFilter,
    clearCustomFilters,
    applyCustomFilters,
  }
}
