export interface StockDetailFilters {
  material: string
  dates: string[]
  organization_id?: number | null
  organization_ids?: number[]
  stock_id: number | null
}
export interface StockDetailParameters {
  material: string
  start_date: string
  end_date: string
  organization_ids: number[]
  stock_id?: number
  page: number
  page_size: number
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
export type StockDetailRequestState = StockDetailResult & { queried_at: string; loading: boolean; error: string }
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
    page, page_size: pageSize }
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
  let value: StockDetailRequestState = { items: [], openings: [], total: 0, queried_at: '', loading: false, error: '', summary: null }
  let revision = 0
  let controller: AbortController | null = null
  function update(patch: Partial<typeof value>) { value = { ...value, ...patch }; changed(value) }
  function clear() {
    ++revision
    controller?.abort(); controller = null
    update({ items: [], openings: [], total: 0, queried_at: '', loading: false, error: '', summary: null })
  }
  return {
    get value() { return value },
    clear,
    async query(filters: StockDetailFilters, page: number, size: number) {
      clear()
      let parameters: StockDetailParameters
      try { parameters = buildStockDetailQuery(filters, page, size) }
      catch (error) { update({ error: error instanceof Error ? error.message : '查询条件无效' }); return }
      const current = revision
      controller = new AbortController()
      update({ loading: true })
      try {
        const result = await load(parameters, controller.signal)
        if (current === revision) update({ ...result, queried_at: result.queried_at || '' })
      } catch {
        if (current === revision) update({ error: '物料收发明细加载失败，请重试；持续失败请联系管理员' })
      } finally {
        if (current === revision) { controller = null; update({ loading: false }) }
      }
    },
  }
}
