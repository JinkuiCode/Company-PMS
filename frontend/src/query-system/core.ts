import type { QueryReference } from './reference.ts'
export type QueryType = 'text' | 'enum' | 'number' | 'date'
export type QueryOperator = 'reference' | 'contains' | 'notContains' | 'equals' | 'notEquals' | 'startsWith' | 'endsWith' | 'in' | 'notIn' | 'greaterThan' | 'greaterOrEqual' | 'lessThan' | 'lessOrEqual' | 'between' | 'isEmpty' | 'notEmpty' | 'before' | 'after'
export type QueryScalar = string | number | null
export type QueryValue = QueryScalar | (string | number)[]
export type QueryOption = { value: string | number; label: string }
export type QueryField = { field: string; label: string; type: QueryType; options?: QueryOption[]; reference?:QueryReference; required?:boolean; operators?:QueryOperator[] }
export type QueryCondition = { id: number; field: string; operator: QueryOperator; value: QueryValue; valueEnd: QueryScalar; schemaVersion?: 1 | 2 }
export const cloneQuery = <T>(value: T): T => JSON.parse(JSON.stringify(value))
const emptyOperators: QueryOperator[] = ['isEmpty', 'notEmpty']
export const isEmpty = (value: unknown) => value === null || value === undefined || value === ''
export function operatorsFor(type: QueryType): QueryOperator[] {
  if (type === 'enum') return ['equals', 'notEquals', 'in', 'notIn', ...emptyOperators]
  if (type === 'text') return ['contains', 'notContains', 'equals', 'notEquals', 'startsWith', 'endsWith', ...emptyOperators]
  return ['equals', 'notEquals', 'greaterThan', 'greaterOrEqual', 'lessThan', 'lessOrEqual', 'between', ...emptyOperators]
}
export function operatorLabel(operator: QueryOperator, type: QueryType) {
  const labels: Record<QueryOperator, string> = { reference:'引用', contains:'包含', notContains:'不包含', equals:'等于', notEquals:'不等于', startsWith:'左包含', endsWith:'右包含', in:'属于', notIn:'不属于', between:'区间', isEmpty:'为空', notEmpty:'不为空', greaterThan:'大于', greaterOrEqual:'大于等于', lessThan:'小于', lessOrEqual:'小于等于', before:'早于', after:'晚于' }
  if (type === 'date') Object.assign(labels, { greaterThan:'晚于', greaterOrEqual:'不早于', lessThan:'早于', lessOrEqual:'不晚于' })
  return labels[operator]
}
export function hasConditionValue(condition: QueryCondition) {
  if (emptyOperators.includes(condition.operator)) return true
  if (['in','notIn','reference'].includes(condition.operator)) return Array.isArray(condition.value) && condition.value.length > 0
  return !isEmpty(condition.value) && (condition.operator !== 'between' || !isEmpty(condition.valueEnd))
}
export function operatorsForField(field:QueryField):QueryOperator[] {
  if(field.operators) return [...field.operators]
  const operators=operatorsFor(field.type)
  if(field.type==='enum') operators.unshift('reference','contains','notContains','startsWith','endsWith')
  else if(field.reference) operators.unshift('reference')
  return operators
}
export function adaptConditions(value: unknown): QueryCondition[] {
  if (!Array.isArray(value) || value.length > 20 || value.some(c => !c || typeof c !== 'object' || Array.isArray(c))) throw Error('筛选条件格式无效')
  return value.map((c, index) => ({ ...cloneQuery(c), id:index + 1, schemaVersion:c.schemaVersion ?? 1 }))
}
function validDate(value: unknown) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0,10) === value
}
export function validateConditions(conditions: QueryCondition[], fields: QueryField[]): Record<number, string> {
  const errors: Record<number, string> = {}
  if (!Array.isArray(conditions) || conditions.length > 20) return { 0:'最多20个筛选条件' }
  for (const c of conditions) {
    if (!c || typeof c !== 'object') { errors[0] = '筛选条件格式无效'; continue }
    const f = fields.find(field => field.field === c.field)
    if (!f) { errors[c.id] = '筛选字段已失效，请重新选择'; continue }
    if (![undefined,1,2].includes(c.schemaVersion)) { errors[c.id] = '查询条件版本无效'; continue }
    const operators = operatorsForField(f)
    if (c.schemaVersion !== 2 && f.type === 'date') operators.push('before','after')
    if (!operators.includes(c.operator)) { errors[c.id] = '请选择有效的匹配方式'; continue }
    if (emptyOperators.includes(c.operator)) continue
    if (!hasConditionValue(c)) { errors[c.id] = c.operator === 'between' ? '请填写完整区间' : '请填写条件值'; continue }
    const values = ['in','notIn','reference'].includes(c.operator) && Array.isArray(c.value) ? c.value : c.operator === 'between' ? [c.value,c.valueEnd] : [c.value]
    if(c.operator==='reference') {
      if(!Array.isArray(c.value)||values.length>1000||values.some(v=>f.type==='enum' ? !f.options?.some(o=>o.value===v) : f.reference?.keyType==='number' ? typeof v!=='number'||!Number.isSafeInteger(v)||v<=0 : typeof v!=='string'||!v||v.length>256)) errors[c.id]='引用记录已失效或引用键无效'
    } else if(f.type==='enum' && ['contains','notContains','startsWith','endsWith'].includes(c.operator)) {
      if(typeof c.value!=='string'||!c.value.trim()||c.value.length>256) errors[c.id]='请输入有效文本（最多256个字符）'
    } else if (f.type === 'enum') {
      if (values.length > 100 || values.some(v => !f.options?.some(o => o.value === v))) errors[c.id] = '选项已失效，请重新选择'
    } else if (f.type === 'text') {
      if (values.length>1000||values.some(v=>typeof v!=='string'||!v.trim()||v.length>256)) errors[c.id] = '请输入有效文本（最多256个字符）'
    } else if (f.type === 'number') {
      if (values.some(v => typeof v !== 'number' || !Number.isFinite(v) || Math.abs(v) > 999999999999)) errors[c.id] = '请输入有效数字'
    } else if (values.some(v => !validDate(v))) errors[c.id] = '请输入有效日期'
    if (!errors[c.id] && c.operator === 'between' && c.schemaVersion === 2 && (c.value as string | number) > (c.valueEnd as string | number)) errors[c.id] = f.type === 'date' ? '开始日期不能晚于结束日期' : '最小值不能大于最大值'
  }
  return errors
}
export function matchesConditions(row: Record<string, unknown>, conditions: QueryCondition[], fields: QueryField[]) {
  if (Object.keys(validateConditions(conditions,fields)).length) return false
  return conditions.every(c => {
    const f = fields.find(f => f.field === c.field)!
    let value = c.operator==='reference' && f.reference ? row[f.reference.keyField] : row[c.field], expected = c.value
    const empty = isEmpty(value) || (typeof value === 'string' && !value.trim())
    if (c.operator === 'isEmpty') return empty
    if (c.operator === 'notEmpty') return !empty
    if (empty) return false
    if(c.operator==='reference') return Array.isArray(expected)&&expected.includes(value as string|number)
    if (f.type==='enum'&&['contains','notContains','startsWith','endsWith'].includes(c.operator)) value=f.options?.find(o=>o.value===value)?.label ?? ''
    if (f.type === 'text' || ['contains','notContains','startsWith','endsWith'].includes(c.operator)) { value = String(value).trim().toLowerCase(); expected = Array.isArray(expected)?expected.map(v=>String(v).trim().toLowerCase()):String(expected).trim().toLowerCase() }
    if (f.type === 'date') value = String(value).slice(0,10)
    switch (c.operator) {
      case 'contains': return String(value).includes(String(expected))
      case 'notContains': return !String(value).includes(String(expected))
      case 'startsWith': return String(value).startsWith(String(expected))
      case 'endsWith': return String(value).endsWith(String(expected))
      case 'equals': return value === expected
      case 'notEquals': return value !== expected
      case 'in': return Array.isArray(expected) && expected.includes(value as string | number)
      case 'notIn': return Array.isArray(expected) && !expected.includes(value as string | number)
      case 'greaterThan': case 'after': return (value as string | number) > (expected as string | number)
      case 'greaterOrEqual': return (value as string | number) >= (expected as string | number)
      case 'lessThan': case 'before': return (value as string | number) < (expected as string | number)
      case 'lessOrEqual': return (value as string | number) <= (expected as string | number)
      case 'between': {
        let start = expected as string | number, end = c.valueEnd as string | number
        if (c.schemaVersion !== 2 && start > end) [start,end] = [end,start]
        return (value as string | number) >= start && (value as string | number) <= end
      }
      default: return false
    }
  })
}
