import request from '@/utils/request'
import type { StockDetailParameters, StockDetailResult } from '@/views/reports/stockDetailState'
import type { ReportField } from '@/report-query/state'

export interface StockDetailField { key: string; label: string; type: string; width: number }
export interface StockDetailMetadata {
  fields: StockDetailField[]
  filter_fields?: ReportField[]
  summary_scope_note?: string
  opening_scope_note?: string
  organizations: { value: number; label: string }[]
}
export interface StockCandidate { value: string | number; code: string; label: string }
export const getStockDetailMetadata = () => request.get<unknown, StockDetailMetadata>('/reports/stock-detail/metadata')
export const getStockDetailRows = (params: StockDetailParameters, signal: AbortSignal) =>
  request.get<unknown, StockDetailResult>('/reports/stock-detail', { params, paramsSerializer: { indexes: null }, signal, timeout: 60000 })
export const getStockDetailCandidates = (field: 'material' | 'stock', keyword: string, organizationIds: number[] = []) =>
  request.get<unknown, { items: StockCandidate[]; has_more: boolean }>('/reports/stock-detail/options', {
    params: { field, keyword, organization_ids: organizationIds }, paramsSerializer: { indexes: null }, timeout: 30000,
  })
