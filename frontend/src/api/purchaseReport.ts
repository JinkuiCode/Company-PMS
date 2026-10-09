import request from '@/utils/request'

export interface PurchaseField {
  key: string; label: string; value_type: string; group: string; description: string
  list_available: boolean; editable: boolean
}
export interface PurchaseRow {
  id: number; bill_no: string; line_no: number; material_name: string; unit_name: string
  document_status: string; progress: string; progress_label: string; product_line_name: string
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
  overview_fields?: PurchaseField[]
  organizations?: { value: number; label: string }[]
  filter_fields?: import('@/report-query/state').ReportField[]
  fields: PurchaseField[]; progress_labels: Record<string, string>
  document_status_labels: Record<string, string>; start_date: string
}
export const getPurchaseMetadata = () => request.get<unknown, PurchaseMetadata>('/reports/purchase/metadata')
export const getPurchaseOptions = (field: 'project' | 'supplier', keyword: string, organization_ids: number[] = [], project_code = '') => request.get<unknown, { items: { value: string; label: string }[]; has_more: boolean }>('/reports/purchase/options', { params: { field, keyword, organization_ids, project_code }, paramsSerializer: { indexes: null }, timeout: 30000 })
export const getPurchaseRows = (params: { organization_ids: number[] }, signal: AbortSignal) => request.get<unknown, { items: PurchaseRow[]; total: number; queried_at: string }>('/reports/purchase', { params, paramsSerializer: { indexes: null }, signal, timeout: 60000 })
export interface PurchaseQueryDraft {
  keyword: string; project_code: string; supplier: string; progress: string; organization_ids: number[]
  dates: string[]; conditions: import('@/report-query/state').ReportCondition[]
}
export interface PurchaseOverviewRow {
  id: string; organization_id: number; project_code: string; product_line_name: string; project_name: string | null
  organization_name: string; total_lines: number; completion_rate: number | string
  complete_lines: number; review_lines: number
  [key: string]: string | number | null
}
export interface PurchaseDetailEntry {
  draft: PurchaseQueryDraft | null
  scope?: { project_code: string; organization_id: number; product_line_name: string }
  progress?: string
}
export const getPurchaseOverview = (params: { organization_ids: number[] }, signal: AbortSignal) => request.get<unknown, {
  items: PurchaseOverviewRow[]; total: number; total_lines: number; complete_lines: number; review_lines: number; queried_at: string
}>('/reports/purchase/overview', { params, paramsSerializer: { indexes: null }, signal, timeout: 60000 })
export const getPurchaseDetail = (id: string, signal: AbortSignal) => request.get<unknown, PurchaseDetail>(`/reports/purchase/${id}`, { signal, timeout: 60000 })
