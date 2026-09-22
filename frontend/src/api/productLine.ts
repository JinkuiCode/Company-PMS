import request from '@/utils/request'
export interface ProductLine {
  id: number; organization_id: number; organization_code: string; organization_name: string
  display_name: string; is_enabled: number; sort: number; updated_at: string
}
export interface Organization { organization_id: number; code: string; name: string }
export interface LineOption { value: number; label: string; disabled?: boolean }
export const getProductLines = (params: object) => request.get('/product-lines', { params }) as unknown as Promise<{ items: ProductLine[]; total: number }>
export const getOrganizations = (params: object) => request.get('/product-lines/organizations', { params }) as unknown as Promise<{ items: Organization[]; total: number }>
export const getRoleProductLines = () => request.get('/product-lines/role-options') as unknown as Promise<{ items: LineOption[] }>
export const getProductLineOptions = () => request.get('/product-lines/options') as unknown as Promise<{ options: LineOption[]; label_map: Record<string, string> }>
