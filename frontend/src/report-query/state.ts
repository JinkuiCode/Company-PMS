export type ReportOperator = 'contains' | 'notContains' | 'equals' | 'notEquals' | 'startsWith' | 'endsWith' | 'greaterThan' | 'greaterOrEqual' | 'lessThan' | 'lessOrEqual' | 'between' | 'isEmpty' | 'notEmpty'
export type ReportCondition = { id: number; field: string; operator: ReportOperator; value: string | number | null; valueEnd: string | number | null }
export type ReportField = { field: string; label: string; type: 'text' | 'number' | 'date' | 'enum'; operators?: ReportOperator[]; options?: {value: string | number; label: string}[] }
export const operatorLabels: Record<ReportOperator, string> = { contains:'包含', notContains:'不包含', equals:'等于', notEquals:'不等于', startsWith:'开头是', endsWith:'结尾是', greaterThan:'大于', greaterOrEqual:'大于等于', lessThan:'小于', lessOrEqual:'小于等于', between:'区间', isEmpty:'为空', notEmpty:'不为空' }
export const cloneQuery = <T>(value: T): T => JSON.parse(JSON.stringify(value))
export function operatorsFor(type: ReportField['type']): ReportOperator[] {
  if (type === 'enum') return ['equals','notEquals','isEmpty','notEmpty']
  if (type === 'date') return ['equals','notEquals','greaterThan','greaterOrEqual','lessThan','lessOrEqual','between','isEmpty','notEmpty']
  return type === 'number' ? ['equals','notEquals','greaterThan','greaterOrEqual','lessThan','lessOrEqual','between','isEmpty','notEmpty'] : ['contains','notContains','equals','notEquals','startsWith','endsWith','isEmpty','notEmpty']
}
export function validateConditions(conditions: ReportCondition[], fields: ReportField[]) {
  if (!Array.isArray(conditions) || conditions.length > 20) return '最多20个筛选条件'
  for (const c of conditions) {
    if (!c || typeof c !== 'object') return '筛选条件格式无效'
    const f = fields.find(f => f.field === c.field)
    if (!f) return '筛选字段已失效，请重新选择'
    if (!(f.operators || operatorsFor(f.type)).includes(c.operator)) return `${f.label}运算符无效`
    if (['isEmpty','notEmpty'].includes(c.operator)) continue
    const values = c.operator === 'between' ? [c.value, c.valueEnd] : [c.value]
    if (values.some(v => v == null || String(v).trim() === '')) return `请填写${f.label}筛选值`
    if (values.some(v => typeof v !== 'string' && typeof v !== 'number')) return `${f.label}筛选值无效`
    if (f.type === 'date') {
      if (values.some(v => typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(v) || !Number.isFinite(Date.parse(v)) || new Date(v).toISOString().slice(0,10) !== v)) return `${f.label}日期无效`
      if (c.operator === 'between' && String(c.value) > String(c.valueEnd)) return `${f.label}区间顺序无效`
    } else if (f.type === 'enum') {
      if (!f.options?.some(o => o.value === c.value)) return `${f.label}选项已失效`
    } else if (f.type === 'number') {
      if (values.some(v => !Number.isFinite(Number(v)) || Math.abs(Number(v)) > 999999999999)) return `${f.label}数值范围无效`
      if (c.operator === 'between' && Number(c.value) > Number(c.valueEnd)) return `${f.label}区间顺序无效`
    } else if (String(c.value).length > 256) return `${f.label}最多256个字符`
  }
  return ''
}

// The accepted snapshot changes only after success; tickets make old responses harmless.
export function createReportSession<T>(initial: T) {
  return {
    draft: cloneQuery(initial), applied: null as T | null, revision: 0,
    get dirty(): boolean { return this.applied !== null && JSON.stringify(this.draft) !== JSON.stringify(this.applied) },
    begin(value?: T) { return { revision: ++this.revision, value: cloneQuery(value ?? this.draft) } },
    accept(ticket: { revision: number; value: T }) { if (ticket.revision !== this.revision) return false; this.applied = cloneQuery(ticket.value); return true },
    fail(ticket: { revision: number }) { return ticket.revision === this.revision },
    invalidate() { ++this.revision },
    restore(value: T) { this.invalidate(); this.draft = cloneQuery(value) },
  }
}
