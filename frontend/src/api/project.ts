import request from '@/utils/request'

export interface ArchiveRegion {
  value: string
  label: string
  children: Array<{ value: string; label: string }>
}

export function getArchiveRegions(): Promise<ArchiveRegion[]> {
  return request.get('/projects/archives/regions') as unknown as Promise<ArchiveRegion[]>
}
