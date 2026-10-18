import request from '@/utils/request'
import type { DraftSummary } from './formDraft'
export type ManagedDraft = DraftSummary & {
  status: 'active'
  creator_name: string
  creator_enabled: boolean
  product_line_name: string
  product_line_id: number
}
export type ManagedDraftDetail = ManagedDraft & {
  fields: { key: string; label: string; display: string }[]
  warnings: string[]
}
const base='/archive-draft-management'
export const archiveDraftManagementApi={
  list:(page:number,page_size:number)=>request.get<never,{items:ManagedDraft[];total:number}>(base,{params:{page,page_size}}),
  get:(id:string)=>request.get<never,ManagedDraftDetail>(`${base}/${encodeURIComponent(id)}`),
  delete:(id:string,expected_version:number)=>request.delete(`${base}/${encodeURIComponent(id)}`,{data:{expected_version}}),
}
