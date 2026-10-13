import request from '@/utils/request'
export type FeedbackRow = {
  id:number; report_no:string; type_id:number; module_id:number; category_id:number; category_name:string; impact_id:number;
  title:string; description:string; expected_result:string; steps:string; status_id:number; author_id:number; author_name:string;
  handler_name:string; outcome_id:number|null; cause_id:number|null; opinion:string|null; created_at:string; updated_at:string;
  version:number; mail_status:string; followups?:any[]; attachments?:any[]; notifications?:any[]
}
export const getFeedback = (id:number) => request.get(`/feedback/${id}`) as unknown as Promise<FeedbackRow>
export const getFeedbackList = (params:object) => request.get('/feedback',{params}) as unknown as Promise<{items:FeedbackRow[];total:number;query_version:number}>
export const getFeedbackStats = (mine:boolean) => request.get('/feedback/statistics',{params:{mine}}) as unknown as Promise<any>
export const submitFeedback = (data:object) => request.post('/feedback',data) as unknown as Promise<FeedbackRow>
export const handleFeedback = (id:number,data:object) => request.post(`/feedback/${id}/handling`,data) as unknown as Promise<FeedbackRow>
export const supplementFeedback = (id:number,data:object) => request.post(`/feedback/${id}/supplements`,data) as unknown as Promise<FeedbackRow>
export const retryFeedbackMail = (id:number) => request.post(`/feedback/notifications/${id}/retry`)
export async function uploadFeedbackFile(row:FeedbackRow,file:File,submissionId?:string) {
  const data = new FormData(); data.append('version',String(row.version)); data.append('file',file)
  if(submissionId)data.append('submission_id',submissionId)
  return request.post(`/feedback/${row.id}/attachments`,data) as unknown as Promise<{version:number}>
}
export async function downloadFeedbackFile(id:number,name:string) {
  const blob = await request.get(`/feedback/attachments/${id}/download`,{responseType:'blob'}) as unknown as Blob
  downloadBlob(blob,name)
}
export async function exportFeedback(params:object) {
  const blob = await request.get('/feedback/export',{params,responseType:'blob',timeout:120000}) as unknown as Blob
  downloadBlob(blob,'问题提报.xlsx')
}
function downloadBlob(blob:Blob,name:string) {
  const url=URL.createObjectURL(blob), link=document.createElement('a'); link.href=url; link.download=name; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000)
}
