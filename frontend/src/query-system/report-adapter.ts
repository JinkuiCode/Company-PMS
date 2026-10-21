import { adaptConditions, cloneQuery, hasConditionValue, type QueryCondition, type QueryField, type QueryOperator } from './core.ts'
import { optionReference, type QueryReference, type ReferenceRequest, type ReferenceResult } from './reference.ts'
import type { ColumnFilter, ColumnCandidate } from './column-filters.ts'
import type { QueryScheme } from './workspace.ts'
import type { PurchaseQueryDraft, PurchaseDetailEntry } from '../api/purchaseReport.ts'
import { PAGE_SIZE_OPTIONS } from '../config/listUi.ts'
import { normalizeMaterialCodes } from './material-reference.ts'

export type ReportKind = 'purchase' | 'inventory' | 'stock-detail'
export type ReportQueryField = QueryField & { operators?: QueryOperator[] }
export type ReportDefinition = { field: string; shown: boolean; operator: QueryOperator; value: QueryCondition['value']; valueEnd: QueryCondition['valueEnd']; schemaVersion?: 2 }
export const activeReportConditions = (conditions: QueryCondition[]) => conditions.filter(hasConditionValue)
export function linkReportScope(next: QueryCondition[], previous: QueryCondition[], scopeField: string, dependents: string[]): QueryCondition[] {
  const scope = (values: QueryCondition[]) => JSON.stringify(activeReportConditions(values).filter(c => c.field === scopeField).map(c => [c.operator, Array.isArray(c.value) ? [...c.value].sort() : c.value]))
  if (scope(next) === scope(previous)) return cloneQuery(next)
  return cloneQuery(next).map(c => {
    const old = previous.find(p => p.field === c.field)
    if (!dependents.includes(c.field) || !old || old.operator !== c.operator || JSON.stringify(old.value) !== JSON.stringify(c.value)) return c
    return { ...c, value: Array.isArray(c.value) ? [] : null, valueEnd: null, schemaVersion: 2 }
  })
}
export function serializeReportConditions(conditions: QueryCondition[]) {
  return JSON.stringify(conditions.map(({ field, operator, value, valueEnd, schemaVersion }) => ({ field, operator, value, valueEnd, ...(schemaVersion === 2 ? { schemaVersion } : {}) })))
}
export function serializeColumnFilters(filters: ColumnFilter[]) { return JSON.stringify(filters) }
export function purchaseDetailEntry(submitted: PurchaseQueryDraft | null, fields: Pick<QueryField, 'field'>[], scope?: PurchaseDetailEntry['scope'], progress = ''): PurchaseDetailEntry {
  if (!submitted) return { draft: null }
  const draft = cloneQuery(submitted), compatible = new Set(fields.map(f => f.field))
  // A selected row's exact tuple replaces positive project references spanning multiple organizations.
  draft.conditions = draft.conditions.filter(c => compatible.has(c.field) && !(scope && c.operator === 'reference' && ['project_code', 'project_name'].includes(c.field)))
  draft.column_filters = []
  return { draft, ...(scope ? { scope: cloneQuery(scope) } : {}), ...(progress ? { progress } : {}) }
}
type SortDirection = 'asc' | 'desc'
type ReportSortGrid = { applyColumnState: (value: { state: { colId: string; sort: SortDirection }[]; defaultState: { sort: null } }) => unknown }
export function createReportColumnSort<Params extends { page: number }>(context: {
  accepted: () => Params | null; loading: () => boolean; fields: () => Record<string, string>;
  grid?: () => ReportSortGrid | null; changed?: (value: { sort: string; direction: SortDirection }) => void;
  unsupported?: (field: string) => void; load: (params: Params & { sort: string; direction: SortDirection }) => unknown;
}) {
  return (field: string, direction: SortDirection) => {
    const accepted = context.accepted(), fields = context.fields()
    if (!accepted || context.loading()) return
    if (!Object.hasOwn(fields, field)) { context.unsupported?.(field); return }
    const params = { ...cloneQuery(accepted), page: 1, sort: fields[field]!, direction }
    context.grid?.()?.applyColumnState({ state: [{ colId: field, sort: direction }], defaultState: { sort: null } })
    context.changed?.({ sort: params.sort, direction })
    return context.load(params)
  }
}
export async function reportColumnCandidates(accepted: object | null, field: string, keyword: string, page: number,
  load: (params: Record<string, unknown>) => Promise<{ items: ColumnCandidate[]; has_more?: boolean; hasMore?: boolean }>) {
  if (!accepted) throw Error('请先查询报表，再筛选列值')
  const params = cloneQuery(accepted) as Record<string, unknown>
  const filters: ColumnFilter[] = JSON.parse(String(params.column_filters || '[]'))
  params.column_filters = serializeColumnFilters(filters.filter(c => c.field !== field))
  const result = await load({ parameters: JSON.stringify(params), column_filters: params.column_filters, field, keyword, page, page_size: 100 })
  return { items: result.items, hasMore: result.has_more ?? result.hasMore ?? false }
}
export function reportFields(fields: QueryField[], common: ReportQueryField[] = []): ReportQueryField[] {
  const result = new Map<string, ReportQueryField>()
  for (const field of [...common, ...fields]) {
    if (result.has(field.field)) continue
    const reference = field.reference && typeof field.reference.load === 'function' ? field.reference : undefined
    result.set(field.field, field.type === 'enum' && !reference
      ? { ...field, reference: optionReference(field.label, field.field, field.options || []) } : { ...field, reference })
  }
  return [...result.values()]
}
export function reportDefaults(fields: string[], date?: { field: string; start: string; end: string }): ReportDefinition[] {
  return fields.map(field => ({ field, shown: true, operator: field === date?.field || field === 'application_date' ? 'between' : /organization/.test(field) ? 'reference' : field === 'project_code' || field === 'stock_id' ? 'reference' : 'contains',
    value: field === date?.field ? date.start : /organization/.test(field) || ['project_code', 'stock_id'].includes(field) ? [] : null,
    valueEnd: field === date?.field ? date.end : null, schemaVersion: 2 }))
}
export const STOCK_MATERIAL_FIELDS = ['material_code', 'material_name', 'specification']
export function stockMaterialCondition(source: QueryCondition[]) {
  return activeReportConditions(source).find(c => c.field === 'material_code' && c.operator === 'reference' && Array.isArray(c.value) && c.value.length)
    || activeReportConditions(source).find(c => STOCK_MATERIAL_FIELDS.includes(c.field)
    && ['contains', 'equals', 'startsWith', 'endsWith'].includes(c.operator)
    && typeof c.value === 'string' && !!c.value.trim())
}
function selectedKeys(condition: QueryCondition, label: string): (string | number)[] {
  if (!['equals', 'in', 'reference'].includes(condition.operator)) throw Error(`${label}只能选择，不支持文字匹配或排除`)
  const keys = Array.isArray(condition.value) ? condition.value : [condition.value]
  if (keys.some(value => value == null || value === '')) throw Error(`请重新选择${label}`)
  return [...new Set(keys)] as (string | number)[]
}
export function reportScope(kind: ReportKind, source: QueryCondition[]) {
  const params: Record<string, unknown> = {}, conditions: QueryCondition[] = []
  for (const condition of activeReportConditions(source)) {
    const { field, operator, value, valueEnd } = condition
    if (field === 'organization_ids' || field === 'organization_id') {
      if (field in params) throw Error('组织范围只能设置一个条件')
      const ids = selectedKeys(condition, '组织')
      if (ids.some(id => typeof id !== 'number' || !Number.isSafeInteger(id) || id <= 0) || ids.length > 200) throw Error('请重新选择组织')
      if (field === 'organization_id') {
        if (ids.length !== 1) throw Error('即时库存只能选择一个组织')
        params.organization_id = ids[0]
      } else params.organization_ids = (ids as number[]).sort((a, b) => a - b)
    } else if (field === 'keyword' || field === 'material') {
      if (field in params || operator !== 'contains' || typeof value !== 'string' || !value.trim() || value.length > 100) throw Error(field === 'material' ? '请填写物料，物料仅支持包含查询' : '关键字仅支持一个包含条件，最多100个字符')
      params[field] = value.trim()
    } else if (kind === 'purchase' && field === 'supplier_name' && condition.schemaVersion !== 2) {
      if ('supplier' in params || operator !== 'contains' || typeof value !== 'string' || value.length > 100) throw Error('供应商仅支持一个包含条件，最多100个字符')
      params.supplier = value.trim()
    } else if (kind === 'stock-detail' && field === 'bill_date') {
      if ('start_date' in params || operator !== 'between' || typeof value !== 'string' || typeof valueEnd !== 'string') throw Error('收发日期必须设置一个完整日期区间')
      params.start_date = value; params.end_date = valueEnd
    } else if (kind === 'stock-detail' && field === 'stock_id') {
      if ('stock_id' in params) throw Error('仓库只能设置一个条件')
      const ids = selectedKeys(condition, '仓库')
      if (ids.length !== 1 || typeof ids[0] !== 'number' || !Number.isSafeInteger(ids[0]) || ids[0] <= 0) throw Error('请选择一个仓库')
      params.stock_id = ids[0]
    } else if (kind === 'stock-detail' && field === 'stock_name') {
      throw Error('仓库只能通过仓库选项选择')
    } else conditions.push(cloneQuery(condition))
  }
  if (kind === 'stock-detail') {
    const material = stockMaterialCondition(source)
    if (material) {
      if (material.operator === 'reference') {
        params.material_codes = normalizeMaterialCodes(material.value)
        const index = conditions.findIndex(c => c.id === material.id)
        if (index >= 0) conditions.splice(index, 1)
      } else {
        if ((material.value as string).length > 100) throw Error('物料条件最多100个字符')
        params.material = (material.value as string).trim(); params.material_field = material.field; params.material_operator = material.operator
      }
    }
    if (!params.material && !(params.material_codes as string[] | undefined)?.length) throw Error('请填写物料后再查询')
    if (!(params.organization_ids as number[] | undefined)?.length) throw Error('请选择至少一个库存组织后再查询')
    if (!params.start_date || !params.end_date) throw Error('请选择完整、有效的起止日期')
  }
  return { params, conditions }
}
export function purchaseReferenceScope(query?: Pick<ReferenceRequest, 'conditions' | 'line'>): { organization_ids: number[] } {
  // Reference validation runs before scheme preferences restore the business drill scope.
  const selected = (reportScope('purchase', query?.conditions ?? []).params.organization_ids as number[] | undefined) ?? []
  if (query?.line != null && selected.length && !selected.includes(query.line)) throw Error('所选项目产品线不在当前查询范围')
  return { organization_ids: query?.line != null ? [query.line] : selected }
}
type ReferenceCandidate = { value: string | number; label: string; code?: string; name?: string; lineName?: string; product_line_name?: string }
type CandidatePage = { items: ReferenceCandidate[]; total?: number; has_more?: boolean }
export function reportReference(title: string, keyField: string, keyType: 'number' | 'string',
  load: (params: Record<string, unknown>) => Promise<CandidatePage>, scope: (query: import('./reference.ts').ReferenceRequest) => Record<string, unknown> = () => ({})): QueryReference {
  return { title, keyField, keyType, async load(query): Promise<ReferenceResult> {
    const result = await load({ ...scope(query), keyword: query.keyword, page: query.page, page_size: query.pageSize,
      ids: query.ids, batch_field: query.batch?.field, batch_values: query.batch?.values })
    if (result.total == null && (result.has_more || query.page > 1 || query.ids || query.batch)) throw Error('引用接口尚未支持完整分页或精确引用校验，请重试或联系管理员')
    return { total: result.total ?? result.items.length, items: result.items.map(item => ({ value: item.value, code: item.code || String(item.value), name: item.name || item.label, lineName: item.lineName ?? item.product_line_name })) }
  } }
}
export function purchaseConditions(draft: { keyword: string; organization_ids: number[]; project_code: string; supplier: string; dates: string[]; progress: string; conditions: unknown[] }): QueryCondition[] {
  const conditions = adaptConditions(draft.conditions || [])
  const add = (field: string, operator: QueryOperator, value: QueryCondition['value'], valueEnd: QueryCondition['valueEnd'] = null) => conditions.push({ id: Math.max(0, ...conditions.map(c => c.id)) + 1, field, operator, value, valueEnd, schemaVersion: 2 })
  if (draft.keyword) add('keyword', 'contains', draft.keyword)
  if (draft.organization_ids.length) add('organization_ids', 'reference', [...draft.organization_ids])
  if (draft.project_code) add('project_code', 'equals', draft.project_code)
  if (draft.supplier) {
    add('supplier_name', 'contains', draft.supplier)
    conditions[conditions.length - 1]!.schemaVersion = 1
  }
  if (draft.dates.length === 2) add('application_date', 'between', draft.dates[0]!, draft.dates[1]!)
  if (draft.progress && !conditions.some(c => c.field === 'progress')) add('progress', 'equals', draft.progress)
  return conditions
}
export function selectReportProgress(conditions: QueryCondition[], values: string[]) {
  const progress = activeReportConditions(conditions).filter(c => c.field === 'progress')
  if (!progress.length) return ''
  return progress.length === 1 && progress[0]!.operator === 'equals' && values.includes(String(progress[0]!.value)) ? String(progress[0]!.value) : 'custom'
}
export function withReportProgress(conditions: QueryCondition[], value: string): QueryCondition[] {
  const next = conditions.filter(c => c.field !== 'progress')
  if (value) next.push({ id: Math.max(0, ...conditions.map(c => c.id)) + 1, field: 'progress', operator: 'equals', value, valueEnd: null, schemaVersion: 2 })
  return next
}
export function reportPreferences(value: object, keys: string[]) {
  const raw = value as { visible?: unknown; columns?: unknown; pageSize?: unknown; sort?: any; overviewStatus?: unknown; scope?: any }
  const result: { visible?: string[]; columns?: { colId: string; [key: string]: unknown }[]; pageSize?: number; sort?: { sort: string; direction: 'asc' | 'desc' }; overviewStatus?: string; scope?: { project_code: string; organization_id: number; product_line_name: string } | null } = {}
  if (Array.isArray(raw.visible)) result.visible = raw.visible.filter((k): k is string => typeof k === 'string' && keys.includes(k))
  if (Array.isArray(raw.columns)) result.columns = raw.columns.filter(c => c && keys.includes(c.colId))
  if (typeof raw.pageSize === 'number' && PAGE_SIZE_OPTIONS.includes(raw.pageSize)) result.pageSize = raw.pageSize
  if (raw.sort && typeof raw.sort.sort === 'string' && ['asc', 'desc'].includes(raw.sort.direction)) result.sort = cloneQuery(raw.sort)
  if (typeof raw.overviewStatus === 'string' && ['', 'unfinished', 'complete', 'review'].includes(raw.overviewStatus)) result.overviewStatus = raw.overviewStatus
  if (raw.scope === null) result.scope = null
  else if (raw.scope && typeof raw.scope.project_code === 'string' && Number.isSafeInteger(raw.scope.organization_id) && raw.scope.organization_id > 0 && typeof raw.scope.product_line_name === 'string') result.scope = cloneQuery(raw.scope)
  return result
}
export function saveReportPreferences(storage: Pick<Storage, 'getItem' | 'setItem'>, key: string, preferences: object) {
  const saved = JSON.parse(storage.getItem(key) || '{}')
  if (!saved || typeof saved !== 'object' || Array.isArray(saved)) throw Error('旧个人设置格式无效，未覆盖原记录')
  storage.setItem(key, JSON.stringify({ ...saved, ...preferences }))
}
export function legacyReportSchemes(storage: Pick<Storage, 'getItem'>, userId: number | string, listKey: string): { schemes: QueryScheme[]; warnings: string[] } {
  const keys: Record<string, string> = {
    'report-purchase-overview': `pms:purchase-overview:v1:${userId}:plans`,
    'report-purchase-progress': `pms:purchase-report:v1:${userId}`,
    'report-inventory': `pms:inventory-report:v1:${userId}:plans:v1`,
    'report-stock-detail': `pms:stock-detail:v1:${userId}`,
  }
  const result: { schemes: QueryScheme[]; warnings: string[] } = { schemes: [], warnings: [] }
  const key = keys[listKey]
  if (!key || !userId) return result
  const raw = storage.getItem(key)
  if (!raw) return result
  let plans: unknown
  try {
    const data = JSON.parse(raw)
    plans = ['report-purchase-progress', 'report-stock-detail'].includes(listKey) ? data.plans || [] : data
    if (!Array.isArray(plans)) throw Error()
  } catch { result.warnings.push('旧个人查询方案格式无效，原记录已保留'); return result }
  for (const input of plans as Record<string, any>[]) {
    const name = typeof input?.name === 'string' ? input.name : ''
    try {
      if (!name || result.schemes.some(p => p.name === name)) throw Error('方案名称为空或重复')
      const state = input.state || input, draft = state.draft || state.filters || state
      let conditions: QueryCondition[], common: string[]
      if (listKey.startsWith('report-purchase')) {
        conditions = purchaseConditions({ keyword: draft.keyword || '', project_code: draft.project_code || '', supplier: draft.supplier || '', progress: draft.progress || '', organization_ids: draft.organization_ids || [], dates: state.dates || draft.dates || [], conditions: state.conditions || draft.conditions || [] })
        common = ['keyword', 'organization_ids', 'project_code', 'application_date', 'supplier_name']
      } else {
        conditions = adaptConditions(draft.conditions || [])
        const add = (field: string, operator: QueryOperator, value: QueryCondition['value'], valueEnd: QueryCondition['valueEnd'] = null) => conditions.push({ id: conditions.length + 1, field, operator, value, valueEnd, schemaVersion: 2 })
        if (listKey === 'report-inventory') {
          if (draft.keyword) add('keyword', 'contains', draft.keyword)
          if (draft.organization_id != null) add('organization_id', 'reference', [draft.organization_id])
          if (draft.stock) add('Stock', 'contains', draft.stock)
          common = ['keyword', 'organization_id', 'Stock']
        } else {
          if (conditions.some(c => c.field === 'stock_name')) throw Error('旧仓库文字附加条件不再支持，请改用仓库选择')
          if (draft.material) add('material', 'contains', draft.material)
          const organizations = draft.organization_ids || (draft.organization_id != null ? [draft.organization_id] : [])
          if (organizations.length) add('organization_ids', 'reference', organizations)
          if (draft.stock_id != null) add('stock_id', 'reference', [draft.stock_id])
          if (draft.dates?.length === 2) add('bill_date', 'between', draft.dates[0], draft.dates[1])
          common = ['material', 'organization_ids', 'bill_date', 'stock_id']
        }
      }
      if (new Set(conditions.map(c => c.field)).size !== conditions.length) throw Error('同一字段有多个条件，需人工整理，未合并或删除条件')
      const definitions = conditions.map(({ id, ...c }) => ({ ...c, shown: true }))
      definitions.push(...reportDefaults(common).filter(d => !definitions.some(c => c.field === d.field)))
      if (definitions.length > 20) throw Error('条件超过20项')
      result.schemes.push({ version: 2, name, isDefault: false, definitions,
        preferences: { visible: cloneQuery(state.visible || []), columns: cloneQuery(state.columns || []), pageSize: state.pageSize ?? state.size ?? 50,
          ...(state.sort ? { sort: cloneQuery(state.sort) } : {}),
          ...(listKey === 'report-purchase-overview' ? { overviewStatus: state.overviewStatus || '' } : {}),
          ...(listKey === 'report-purchase-progress' ? { scope: cloneQuery(state.scope || null) } : {}),
        } })
    } catch (error) { result.warnings.push(`旧方案“${name || '未命名'}”未迁移：${error instanceof Error ? error.message : '格式无效'}；原记录已保留`) }
  }
  return result
}

// Keep submitted parameters authoritative for paging, retries and exports.
export function createReportRequest<Draft, Params extends { page: number; page_size: number }, Result extends { items: unknown[]; total: number }>(
  build: (draft: Draft, page: number, size: number) => Params,
  load: (params: Params, signal: AbortSignal) => Promise<Result>, initial: Result,
  changed: (state: Result & { loading: boolean; error: string; queried_at: string; applied: Params | null }) => void = () => {},
) {
  let value = { ...initial, loading: false, error: '', queried_at: '', applied: null as Params | null }
  let revision = 0, controller: AbortController | null = null
  let failed: { params: Params; kind: 'submit' | 'page' } | null = null
  const update = (patch: Partial<typeof value>) => { value = { ...value, ...patch }; changed(value) }
  function invalidate() { ++revision; controller?.abort(); controller = null; failed = null; update({ loading: false, error: '' } as Partial<typeof value>) }
  async function execute(params: Params, kind: 'submit' | 'page') {
    const run = ++revision, snapshot = cloneQuery(params)
    controller?.abort(); controller = new AbortController(); failed = null
    update({ loading: true, error: '' } as Partial<typeof value>)
    try {
      const result = await load(cloneQuery(snapshot), controller.signal)
      if (run !== revision) return false
      update({ ...result, applied: snapshot, queried_at: (result as { queried_at?: string }).queried_at || '' } as unknown as Partial<typeof value>); return true
    } catch {
      if (run === revision) { failed = { params: snapshot, kind }; update({ error: '报表加载失败，请重试；下方保留上次查询结果' } as Partial<typeof value>) }
    } finally { if (run === revision) update({ loading: false } as Partial<typeof value>) }
    return false
  }
  return {
    get value() { return value }, get retryKind() { return failed?.kind ?? null }, invalidate,
    clear() { invalidate(); update({ ...initial, applied: null, queried_at: '' } as unknown as Partial<typeof value>) },
    retry: () => failed ? execute(failed.params, failed.kind) : Promise.resolve(false),
    submit: (params: Params) => execute(params, 'submit'),
    paginate: (page: number, page_size: number) => value.applied ? execute({ ...value.applied, page, page_size }, 'page') : Promise.resolve(false),
    async query(draft: Draft, page: number, size: number) {
      try { return await execute(build(cloneQuery(draft), page, size), 'submit') }
      catch (error) { invalidate(); update({ error: error instanceof Error ? error.message : '查询条件无效' } as Partial<typeof value>); return false }
    },
  }
}
