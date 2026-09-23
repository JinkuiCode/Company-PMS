import request from '@/utils/request'
import type { StockDetailParameters, StockDetailResult } from '@/views/reports/stockDetailState'

export interface StockDetailField { key: string; label: string; type: string; width: number }
export interface StockDetailMetadata {
  fields: StockDetailField[]
  organizations: { value: number; label: string }[]
}
export interface StockCandidate { value: string | number; code: string; label: string }
export const getStockDetailMetadata = () => request.get<unknown, StockDetailMetadata>('/reports/stock-detail/metadata')
export const getStockDetailRows = (params: StockDetailParameters, signal: AbortSignal) =>
  request.get<unknown, StockDetailResult>('/reports/stock-detail', { params, signal, timeout: 60000 })
export const getStockDetailCandidates = (field: 'material' | 'stock', keyword: string, organizationId?: number) =>
  request.get<unknown, { items: StockCandidate[]; has_more: boolean }>('/reports/stock-detail/options', {
    params: { field, keyword, organization_id: organizationId }, timeout: 30000,
  })
