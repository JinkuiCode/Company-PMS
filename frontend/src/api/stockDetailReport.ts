import request from '@/utils/request'
import { guardMaterialReferenceUrl } from '@/query-system/material-reference'
import { ElMessage } from 'element-plus'
import type { StockDetailParameters, StockDetailResult } from '@/views/reports/stockDetailState'
import type { QueryField } from '@/query-system/core'

export interface StockDetailField { key: string; label: string; type: string; width: number }
export interface StockDetailMetadata {
  fields: StockDetailField[]
  filter_fields?: QueryField[]
  query_fields?: QueryField[]
  column_filter_fields?: QueryField[]
  sort_fields?: string[]
  default_sort?: { sort: string; direction: 'asc' | 'desc' }
  summary_scope_note?: string
  opening_scope_note?: string
  organizations: { value: number; label: string }[]
}
export interface StockCandidate { value: string | number; code: string; label: string; name?: string }
export type StockDetailQueryParameters = StockDetailParameters & { column_filters?: string; sort?: string; direction?: 'asc' | 'desc' }
export const getStockDetailMetadata = () => request.get<unknown, StockDetailMetadata>('/reports/stock-detail/metadata')
export const getStockDetailRows = (params: StockDetailQueryParameters, signal: AbortSignal) =>
  request.get<unknown, StockDetailResult>('/reports/stock-detail', { params: guardMaterialReferenceUrl('/reports/stock-detail', params, false, ElMessage.error), paramsSerializer: { indexes: null }, signal, timeout: 60000 })
export const getStockDetailCandidates = (field: 'material' | 'stock', keyword: string, organizationIds: number[] = []) =>
  request.get<unknown, { items: StockCandidate[]; has_more: boolean }>('/reports/stock-detail/options', {
    params: { field, keyword, organization_ids: organizationIds }, paramsSerializer: { indexes: null }, timeout: 30000,
  })
export const getStockDetailReference = (field: 'material' | 'stock', params: Record<string, unknown>) => request.get<unknown, { items: StockCandidate[]; total?: number; has_more?: boolean }>('/reports/stock-detail/options', { params: field === 'material' ? guardMaterialReferenceUrl('/reports/stock-detail/options', { ...params, field }, true, ElMessage.error) : { ...params, field }, paramsSerializer: { indexes: null }, timeout: 30000 })
export const getStockDetailColumnCandidates = (params: Record<string, unknown>) => request.get<unknown, { items: import('@/query-system/column-filters').ColumnCandidate[]; has_more: boolean }>('/reports/stock-detail/column-options', { params, paramsSerializer: { indexes: null }, timeout: 60000 })
