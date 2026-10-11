import request from '@/utils/request'
import type { BusinessExportSnapshot } from '../business-export/snapshot'

export type BusinessExportResource = { kind: 'projects' } | { kind: 'tasks'; projectId: number } | { kind: 'archives' }
export function businessExportPermission(resource: BusinessExportResource) {
  return resource.kind === 'archives' ? 'project:archive:export' : 'project:list:export'
}
export function businessViewPermission(resource: BusinessExportResource) {
  return resource.kind === 'archives' ? 'project:archive:view' : 'project:list:view'
}
export function businessExportFilename(resource: BusinessExportResource) {
  return { projects: '项目列表.xlsx', tasks: '项目进度.xlsx', archives: '项目档案.xlsx' }[resource.kind]
}
export function downloadBusinessExport(resource: BusinessExportResource, snapshot: BusinessExportSnapshot) {
  let path = '/projects/export'
  if (resource.kind === 'archives') path = '/projects/archives/export'
  if (resource.kind === 'tasks') {
    if (!Number.isSafeInteger(resource.projectId) || resource.projectId <= 0) throw Error('项目身份无效，不能导出任务')
    path = `/projects/${resource.projectId}/tasks/export`
  }
  return request.post<unknown, Blob>(path, snapshot, { responseType: 'blob', timeout: 0 })
}
