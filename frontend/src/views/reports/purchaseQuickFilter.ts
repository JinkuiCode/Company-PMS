import type { ReportCondition } from '@/report-query/state'

export function selectedPurchaseProgress(conditions: ReportCondition[], values: string[]): string {
  const progress = conditions.filter(condition => condition.field === 'progress')
  if (!progress.length) return ''
  const condition = progress[0]!
  return progress.length === 1 && condition.operator === 'equals' && values.includes(String(condition.value))
    ? String(condition.value) : 'custom'
}

export function withPurchaseProgress(conditions: ReportCondition[], value: string): ReportCondition[] {
  const next = conditions.filter(condition => condition.field !== 'progress')
  if (value) next.push({ id: Math.max(0, ...conditions.map(condition => condition.id)) + 1, field: 'progress', operator: 'equals', value, valueEnd: null })
  return next
}

export function restorePurchaseProgress(conditions: ReportCondition[], legacy: string): ReportCondition[] {
  return legacy && !conditions.some(condition => condition.field === 'progress') ? withPurchaseProgress(conditions, legacy) : conditions
}
