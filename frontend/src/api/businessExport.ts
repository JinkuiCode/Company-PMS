import request from '@/utils/request'
import type { BusinessExportSnapshot } from '../business-export/snapshot'

export type BusinessExportResource = { kind: 'projects' } | { kind: 'tasks'; projectId: number } | { kind: 'archives' | 'archive_changes' }
export function businessExportPermission(resource: BusinessExportResource) {
  return ['archives','archive_changes'].includes(resource.kind) ? 'project:archive:export' : 'project:list:export'
}
export function businessViewPermission(resource: BusinessExportResource) {
  return ['archives','archive_changes'].includes(resource.kind) ? 'project:archive:view' : 'project:list:view'
}
export function businessExportFilename(resource: BusinessExportResource) {
  return { projects: '项目列表.xlsx', tasks: '项目进度.xlsx', archives: '项目档案.xlsx',archive_changes:'项目档案变更.xlsx' }[resource.kind]
}
export function downloadBusinessExport(resource: BusinessExportResource, snapshot: BusinessExportSnapshot) {
  let path = '/projects/export'
  if (resource.kind === 'archives') path = '/projects/archives/export'
  if (resource.kind === 'archive_changes') path = '/projects/archive-changes/export'
  if (resource.kind === 'tasks') {
    if (!Number.isSafeInteger(resource.projectId) || resource.projectId <= 0) throw Error('项目身份无效，不能导出任务')
    path = `/projects/${resource.projectId}/tasks/export`
  }
  return request.post<unknown, Blob>(path, snapshot, { responseType: 'blob', timeout: 0 })
}
