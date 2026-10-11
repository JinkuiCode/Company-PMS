import type { ListFilterField } from '../composables/useListFilters'
import type { QueryField } from './core'

export function toQueryFields<T>(fields: ListFilterField<T>[]): QueryField[] {
  return fields.map(f => ({ field:f.field, label:f.label, type:f.type === 'select' ? 'enum' : f.type, options:f.options?.(),reference:f.reference }))
}
export function toQueryRecord<T>(row:T,fields:ListFilterField<T>[]):Record<string,unknown> {
  return {...row,...Object.fromEntries(fields.map(f=>[f.field,f.getValue?f.getValue(row):(row as Record<string,unknown>)[f.field]]))}
}
