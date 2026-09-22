import request from '@/utils/request'

export interface InventoryField {
  key: string; label: string; value_type: string; width: number; group: string
  description: string; editable: boolean; list_available: boolean
}
export type InventoryRow = Record<string, string | number | null>
export interface InventoryMetadata {
  fields: InventoryField[]
  organizations: { value: number; label: string }[]
}
export const getInventoryMetadata = () => request.get<unknown, InventoryMetadata>('/reports/inventory/metadata')
export const getInventoryRows = (params: object, signal: AbortSignal) => request.get<unknown, {items: InventoryRow[]; total: number; queried_at: string}>('/reports/inventory', {params, signal, timeout: 60000})
export const getInventoryStocks = (keyword: string, organization_id?: number) => request.get<unknown, {items: {value: string; label: string}[]; has_more: boolean}>('/reports/inventory/options', {params: {field: 'Stock', keyword, organization_id}, timeout: 30000})
