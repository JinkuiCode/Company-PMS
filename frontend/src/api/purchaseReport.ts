import request from '@/utils/request'

export interface PurchaseField {
  key: string; label: string; value_type: string; group: string; description: string
  list_available: boolean; editable: boolean
}
export interface PurchaseRow {
  id: number; bill_no: string; line_no: number; material_name: string; unit_name: string
  document_status: string; progress: string; progress_label: string
  [key: string]: string | number | null
}
export interface PurchaseDocument {
  id: number; order_id?: number; bill_no: string; line_no: number; supplier_name?: string
  order_date?: string; stock_date?: string; return_date?: string; quantity: number | string
  unit_name?: string; document_status: string; cancel_status: string; effective: boolean | null
  source_kind?: string; receipt_id?: number
}
export interface PurchaseDetail {
  request: PurchaseRow; orders: PurchaseDocument[]; receipts: PurchaseDocument[]; returns: PurchaseDocument[]
  summary: { issues: string[]; [key: string]: unknown }; queried_at: string
}
export interface PurchaseMetadata {
  fields: PurchaseField[]; progress_labels: Record<string, string>
  document_status_labels: Record<string, string>; start_date: string
}
export const getPurchaseMetadata = () => request.get<unknown, PurchaseMetadata>('/reports/purchase/metadata')
export const getPurchaseOptions = (field: 'project' | 'supplier', keyword: string) => request.get<unknown, { items: { value: string; label: string }[]; has_more: boolean }>('/reports/purchase/options', { params: { field, keyword }, timeout: 30000 })
export const getPurchaseRows = (params: object, signal: AbortSignal) => request.get<unknown, { items: PurchaseRow[]; total: number; queried_at: string }>('/reports/purchase', { params, signal, timeout: 60000 })
export const getPurchaseDetail = (id: string, signal: AbortSignal) => request.get<unknown, PurchaseDetail>(`/reports/purchase/${id}`, { signal, timeout: 60000 })
