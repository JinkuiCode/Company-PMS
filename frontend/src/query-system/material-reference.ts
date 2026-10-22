import type { QueryCondition } from './core.ts'
import type { ReferenceRequest } from './reference.ts'
import { reportReference } from './report-adapter.ts'

export function normalizeMaterialCodes(value: unknown): string[] {
  if (!Array.isArray(value) || !value.length || value.length > 1000 || value.some(v => typeof v !== 'string' || !v.trim() || v.length > 256 || /[\u0000-\u001f\u007f]/.test(v))) throw Error('请选择1至1000个有效物料编码，单项最多256个字符')
  return [...new Set((value as string[]).map(v => v.trim().toLowerCase()))]
}

export function guardMaterialReferenceUrl<T extends object>(path: string, parameters: T, reference = false, notify?: (message: string) => void): T {
  const params = parameters as Record<string, unknown>
  if (!reference) {
    let conditions: { field?: string; operator?: string }[] = []
    try { conditions = JSON.parse(String(params.filters || '[]')) } catch { /* The request validator reports malformed filters. */ }
    reference = Array.isArray(params.material_codes) && !!params.material_codes.length || Array.isArray(conditions) && conditions.some(c => ['material_code', 'MaterialCode'].includes(c.field || '') && c.operator === 'reference')
  }
  if (reference) {
    const pairs: string[] = []
    for (const [key, value] of Object.entries(params)) for (const item of Array.isArray(value) ? value : [value]) {
      if (item != null) pairs.push(`${encodeURIComponent(key)}=${encodeURIComponent(typeof item === 'object' ? JSON.stringify(item) : String(item))}`)
    }
    if (new TextEncoder().encode(`/api${path}?${pairs.join('&')}`).length > 6000) {
      const message = '物料引用请求过长（最多6000字节），请减少选择或缩小其他条件；原选择保留'
      notify?.(message)
      throw Error(message)
    }
  }
  return parameters
}

export function materialReference(kind: 'purchase' | 'inventory' | 'stock-detail',
  load: (params: Record<string, unknown>) => Promise<{ items: { value: string | number; code?: string; label: string }[]; total?: number; has_more?: boolean }>, current: () => QueryCondition[] = () => []) {
  return reportReference('物料', 'code', 'string', load, (request: ReferenceRequest) => {
    const field = kind === 'inventory' ? 'organization_id' : 'organization_ids'
    const condition = (request.conditions || current()).find(c => c.field === field)
    const ids = condition ? (Array.isArray(condition.value) ? condition.value : condition.value == null ? [] : [condition.value]) : []
    if (condition && !['reference', 'equals', 'in'].includes(condition.operator) || ids.length > 200 || ids.some(v => typeof v !== 'number' || !Number.isSafeInteger(v) || v <= 0)) throw Error('请重新选择产品线')
    if (kind === 'stock-detail' && !ids.length) throw Error('请先选择产品线，再选择物料')
    if (kind === 'inventory' && ids.length > 1) throw Error('即时库存只能选择一个产品线')
    return kind === 'inventory' ? { organization_id: ids[0] } : { organization_ids: ids }
  })
}
