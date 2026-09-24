import type { ReportCondition } from '../../report-query/state'

const quantityFormat = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false,
})
export function formatStockQuantity(value: unknown): string {
  if (value === null || value === undefined || value === '') return ''
  // Keep decimal strings intact: Intl accepts them without binary float conversion.
  const formatted = quantityFormat.format(value as number)
  return formatted === '0.00' || formatted === '-0.00' ? '' : formatted
}

export interface StockDetailFilters {
  material: string
  dates: string[]
  organization_id?: number | null
  organization_ids?: number[]
  stock_id: number | null
  conditions?: ReportCondition[]
}
export interface StockDetailParameters {
  material: string
  start_date: string
  end_date: string
  organization_ids: number[]
  stock_id?: number
  page: number
  page_size: number
  filters?: string
}
export interface StockDetailRow {
  row_id: string
  row_kind: 'movement' | 'opening'
  [key: string]: string | number | null
}
export interface StockDetailResult {
  items: StockDetailRow[]
  openings: StockDetailRow[]
  total: number
  queried_at?: string
  summary?: Record<string, string | number | null> | null
}
export type StockDetailRequestState = StockDetailResult & { queried_at: string; loading: boolean; error: string; applied: StockDetailParameters | null }
function isDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}
export function buildStockDetailQuery(filters: StockDetailFilters, page: number, pageSize: number): StockDetailParameters {
  const material = typeof filters.material === 'string' ? filters.material.trim() : ''
  if (!material || material.length > 100) throw new Error('请填写物料后再查询')
  const dates = filters.dates
  if (!Array.isArray(dates) || dates.length !== 2 || !dates.every(isDate)) throw new Error('请选择完整、有效的起止日期')
  if (dates[0]! > dates[1]!) throw new Error('起始日期不得晚于截止日期')
  const organizations = stockDetailOrganizations(filters)
  if (!organizations.length) throw new Error('请选择至少一个库存组织后再查询')
  for (const id of [filters.organization_id, filters.stock_id]) {
    if (id != null && (!Number.isSafeInteger(id) || id <= 0)) throw new Error('请重新选择组织或仓库')
  }
  if (!Number.isSafeInteger(page) || page < 1 || page > 1000000 || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 500) throw new Error('分页参数无效')
  return { material, start_date: dates[0]!, end_date: dates[1]!,
    organization_ids: organizations, stock_id: filters.stock_id ?? undefined,
    page, page_size: pageSize,
    filters: filters.conditions?.length ? JSON.stringify(filters.conditions.map(({ field, operator, value, valueEnd }) => ({ field, operator, value, valueEnd }))) : undefined }
}

export function stockDetailOrganizations(filters: StockDetailFilters): number[] {
  const ids = filters.organization_ids ?? (filters.organization_id == null ? [] : [filters.organization_id])
  if (!Array.isArray(ids) || ids.length > 200 || ids.some(id => !Number.isSafeInteger(id) || id <= 0)) throw new Error('请重新选择组织')
  if (ids.length && filters.organization_id != null && filters.organization_ids != null) throw new Error('请勿同时指定单组织和多组织条件')
  return [...new Set(ids)].sort((a, b) => a - b)
}

export function createStockDetailRequest(
  load: (parameters: StockDetailParameters, signal: AbortSignal) => Promise<StockDetailResult>,
  changed: (value: Readonly<StockDetailRequestState>) => void = () => {},
) {
  let value: StockDetailRequestState = { items: [], openings: [], total: 0, queried_at: '', loading: false, error: '', summary: null, applied: null }
  type RequestKind = 'submit' | 'page'
  let failed: { parameters: StockDetailParameters; kind: RequestKind } | null = null
  let revision = 0
  let controller: AbortController | null = null
  function update(patch: Partial<typeof value>) { value = { ...value, ...patch }; changed(value) }
  function invalidate() {
    ++revision
    controller?.abort(); controller = null
    failed = null
    update({ loading: false, error: '' })
  }
  function clear() {
    invalidate()
    update({ items: [], openings: [], total: 0, queried_at: '', loading: false, error: '', summary: null, applied: null })
  }
  async function execute(parameters: StockDetailParameters, kind: RequestKind = 'submit') {
    const current = ++revision
    controller?.abort()
    controller = new AbortController()
    const snapshot = { ...parameters, organization_ids: [...parameters.organization_ids] }
    failed = null
    update({ loading: true, error: '' })
    try {
      const result = await load({ ...snapshot, organization_ids: [...snapshot.organization_ids] }, controller.signal)
      if (current === revision) {
        update({ ...result, summary: result.summary ?? null, queried_at: result.queried_at || '', applied: snapshot })
        return true
      }
    } catch {
      if (current === revision) {
        failed = { parameters: snapshot, kind }
        update({ error: '物料收发明细加载失败，请重试；持续失败请联系管理员' })
      }
    } finally {
      if (current === revision) { controller = null; update({ loading: false }) }
    }
    return false
  }
  return {
    get value() { return value },
    get retryKind() { return failed?.kind ?? null },
    clear,
    invalidate,
    retry: () => failed ? execute(failed.parameters, failed.kind) : Promise.resolve(),
    paginate: (page: number, size: number) => value.applied ? execute({ ...value.applied, page, page_size: size }, 'page') : Promise.resolve(),
    async query(filters: StockDetailFilters, page: number, size: number) {
      let parameters: StockDetailParameters
      try { parameters = buildStockDetailQuery(filters, page, size) }
      catch (error) {
        ++revision; controller?.abort(); controller = null; failed = null
        update({ loading: false, error: error instanceof Error ? error.message : '查询条件无效' }); return
      }
      return execute(parameters)
    },
  }
}
