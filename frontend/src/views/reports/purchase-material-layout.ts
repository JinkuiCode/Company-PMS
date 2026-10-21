const CODE = 'material_code'
const NAME = 'material_name'

export function purchaseMaterialLayoutVersion(keys: string[]): 1 | undefined {
  return keys.includes(CODE) && keys.includes(NAME) ? 1 : undefined
}

// Migrate only the new default; later user choices remain authoritative.
export function migratePurchaseMaterialLayout<T extends Record<string, any>>(value: T, keys: string[], current: { colId: string; pinned?: string | boolean | null }[] = []): T {
  const result = { ...value } as Record<string, any>
  if (!purchaseMaterialLayoutVersion(keys) || result.purchaseMaterialLayoutVersion === 1) return result as T
  if (Array.isArray(result.visible)) {
    const visible = result.visible.filter((key: string) => key !== CODE)
    const anchor = visible.indexOf(NAME)
    const prefix = Math.max(visible.indexOf('product_line_name'), visible.indexOf('project_code')) + 1
    visible.splice(anchor < 0 ? prefix : anchor, 0, CODE)
    result.visible = visible
  }
  if (Array.isArray(result.columns) || Array.isArray(result.visible)) {
    const existing = Array.isArray(result.columns) ? result.columns : []
    // AG Grid appends unspecified columns after the supplied applyOrder state.
    const order: string[] = [...new Set<string>([...existing.map((column: { colId: string }) => column.colId), ...current.map(column => column.colId), ...keys])]
    const columns: Record<string, any>[] = order.map(colId => ({ ...existing.find((column: { colId: string }) => column.colId === colId), colId }))
    const name = columns.find(column => column.colId === NAME)!
    const code = columns.find(column => column.colId === CODE)!
    result.columns = columns.filter(column => column.colId !== CODE)
    result.columns.splice(result.columns.findIndex((column: { colId: string }) => column.colId === NAME), 0,
      { ...code, hide: false, pinned: name.pinned === undefined ? current.find(column => column.colId === NAME)?.pinned ?? null : name.pinned })
  }
  result.purchaseMaterialLayoutVersion = 1
  return result as T
}
