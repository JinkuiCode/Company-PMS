import request from '@/utils/request'
import type { PersistentDraft } from '@/form-system/usePersistentDraft'
const base = '/form-drafts/archive-create'
export const archiveDraftApi = {
  productLines: () => request.get(`${base}/product-lines`) as unknown as Promise<{ options: import('./productLine').LineOption[]; label_map: Record<string,string> }>,
  get: (id: string) => request.get(`${base}/${id}`) as unknown as Promise<PersistentDraft>,
  save: (body: { id: string; expected_version: number | null; payload: Record<string, unknown> }) => request.post(base, body) as unknown as Promise<PersistentDraft>,
  submit: (id: string, version: number) => request.post(`${base}/${id}/submit`, { expected_version: version }) as unknown as Promise<{ id: number }>,
  list: (page: number, page_size: number) => request.get(base, { params: { page, page_size } }) as unknown as Promise<{items: DraftSummary[]; total: number}>,
  delete: (id: string, expected_version: number) => request.delete(`${base}/${id}`, { data: { expected_version } }),
}
export type DraftSummary = Pick<PersistentDraft, 'id' | 'version'> & { project_code: string; project_name: string; updated_at: string }
