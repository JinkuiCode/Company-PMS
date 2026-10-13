import { normalizeActionColumnState } from '../../config/listUi.ts'

// Migrate old layouts once; subsequently preserve the user's new display choices.
export function reportIdentityVersion(fields: { key: string }[]): 1 | undefined {
  return fields.some(field => field.key === 'product_line_name') ? 1 : undefined
}

export function migrateReportIdentity<T extends Record<string, any>>(value: T, removed = ['project_name']): T {
  const result = { ...value } as Record<string, any>
  const firstMigration = result.reportIdentityVersion !== 1
  if (Array.isArray(result.visible)) {
    result.visible = result.visible.filter((key: string) => !removed.includes(key))
    if (firstMigration) result.visible = ['product_line_name', ...result.visible.filter((key: string) => key !== 'product_line_name')]
  }
  if (Array.isArray(result.columns)) {
    result.columns = normalizeActionColumnState(result.columns.filter((column: { colId: string }) => !removed.includes(column.colId)), 'purchase_actions')
    if (firstMigration && result.columns.length) {
      const line = result.columns.find((column: { colId: string }) => column.colId === 'product_line_name') || { colId: 'product_line_name', width: 140 }
      result.columns = [{ ...line, hide: false, pinned: 'left' }, ...result.columns.filter((column: { colId: string }) => column.colId !== 'product_line_name')]
    }
  }
  if (result.sort && removed.includes(result.sort.sort)) delete result.sort
  result.reportIdentityVersion = 1
  return result as T
}
