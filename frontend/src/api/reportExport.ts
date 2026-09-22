import request from '@/utils/request'

export type ReportName = 'inventory' | 'purchase'
export interface ReportExportJob {
  id: string; report: ReportName; status: 'queued' | 'running' | 'success' | 'failed' | 'expired'
  processed: number; message: string | null; created_at: string; finished_at: string | null
}
export const createReportExport = (report: ReportName, parameters: object, columns: string[]) =>
  request.post<unknown, ReportExportJob>('/report-exports', { report, parameters, columns })
export const listReportExports = (report: ReportName) => request.get<unknown, ReportExportJob[]>('/report-exports', { params: { report } })
export const downloadReportExport = (id: string) => request.get<unknown, Blob>(`/report-exports/${id}/download`, { responseType: 'blob', timeout: 0 })
