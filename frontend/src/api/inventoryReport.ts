import request from '@/utils/request'
import { guardMaterialReferenceUrl } from '@/query-system/material-reference'
import { ElMessage } from 'element-plus'

export interface InventoryField {
  key: string; label: string; value_type: string; width: number; group: string
  description: string; editable: boolean; list_available: boolean
}
export type InventoryRow = Record<string, string | number | null>
export interface InventoryMetadata {
  fields: InventoryField[]
  organizations: { value: number; label: string }[]
  query_fields?: import('@/query-system/core').QueryField[]
  column_filter_fields?: import('@/query-system/core').QueryField[]
}
export const getInventoryMetadata = () => request.get<unknown, InventoryMetadata>('/reports/inventory/metadata')
export const getInventoryRows = (params: object, signal: AbortSignal) => request.get<unknown, {items: InventoryRow[]; total: number; queried_at: string}>('/reports/inventory', {params:guardMaterialReferenceUrl('/reports/inventory',params,false,ElMessage.error),paramsSerializer:{indexes:null}, signal, timeout: 60000})
export const getInventoryMaterialReference = (params: Record<string, unknown>) => request.get<unknown, { items: { value: string; code: string; label: string; name?: string }[]; total: number; has_more: boolean }>('/reports/inventory/material-reference-options', { params: guardMaterialReferenceUrl('/reports/inventory/material-reference-options', params, true, ElMessage.error), paramsSerializer:{indexes:null}, timeout:30000 })
export const getInventoryStocks = (keyword: string, organization_id?: number) => request.get<unknown, {items: {value: string; label: string}[]; has_more: boolean}>('/reports/inventory/options', {params: {field: 'Stock', keyword, organization_id}, timeout: 30000})
export const getInventoryReference = (params: Record<string, unknown>) => request.get<unknown, { items: { value: string; label: string; code?: string; name?: string }[]; total?: number; has_more?: boolean }>('/reports/inventory/options', { params: { ...params, field: 'Stock' }, paramsSerializer: { indexes: null }, timeout: 30000 })
export const getInventoryColumnCandidates = (params: Record<string, unknown>) => request.get<unknown, { items: import('@/query-system/column-filters').ColumnCandidate[]; has_more: boolean }>('/reports/inventory/column-options', { params, timeout: 60000 })
