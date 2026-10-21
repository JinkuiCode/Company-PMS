import type { ColumnState } from 'ag-grid-community'

export interface PmsColumnPreference {
  selected_column_keys: string[]
  columnState: ColumnState[]
  layout_version?: number
}
export interface PmsColumnSchema {
  allowed: ReadonlySet<string>
  defaults: readonly string[]
  fixed: ReadonlySet<string>
  layoutVersion?: number
}
type ReadResult = { status: 'ready'; value: PmsColumnPreference }
  | { status: 'empty' | 'anonymous' | 'invalid' | 'unsupported' | 'unavailable' }

function layoutStatus(value: { layout_version?: unknown }, schema: PmsColumnSchema): 'invalid' | 'unsupported' | null {
  if (schema.layoutVersion === undefined || value.layout_version === undefined) return null
  if (!Number.isSafeInteger(value.layout_version) || (value.layout_version as number) < 1) return 'invalid'
  return (value.layout_version as number) > schema.layoutVersion ? 'unsupported' : null
}

export function normalizeColumnPreference(value: { selected_column_keys?: unknown; columnState?: unknown; layout_version?: unknown }, schema: PmsColumnSchema): PmsColumnPreference {
  if (layoutStatus(value, schema)) throw new Error('列布局版本无效，请重新配置')
  const selected = Array.isArray(value.selected_column_keys) ? value.selected_column_keys : schema.defaults
  const seen = new Set<string>()
  return {
    ...(schema.layoutVersion !== undefined && value.layout_version !== undefined ? { layout_version: value.layout_version as number } : {}),
    selected_column_keys: [...new Set(selected.filter((key): key is string => typeof key === 'string' && schema.allowed.has(key)))],
    columnState: (Array.isArray(value.columnState) ? value.columnState : []).filter(state => {
      if (!state || typeof state !== 'object' || typeof state.colId !== 'string' || seen.has(state.colId)) return false
      if (!schema.allowed.has(state.colId) && !schema.fixed.has(state.colId)) return false
      seen.add(state.colId)
      return true
    }).map(state => ({ ...state })),
  }
}

/** Local preferences only; reading never migrates or deletes stored data. */
export function createColumnPreferences(options: {
  pageKey: string
  ownerId: () => number | null
  storage: () => Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
  legacyPrefix?: string
  legacySelectionKey?: string
}) {
  function key() {
    const owner = options.ownerId()
    if (!Number.isSafeInteger(owner) || owner == null || owner <= 0) return null
    return options.legacyPrefix ? `${options.legacyPrefix}:${owner}` : `pms:columns:${options.pageKey}:${owner}`
  }
  function read(schema: PmsColumnSchema): ReadResult {
    const storageKey = key()
    if (!storageKey) return { status: 'anonymous' }
    try {
      const raw = options.storage().getItem(storageKey)
      if (raw === null) return { status: 'empty' }
      let value
      try { value = JSON.parse(raw) } catch { return { status: 'invalid' } }
      if (!value || typeof value !== 'object' || Array.isArray(value)) return { status: 'invalid' }
      const version = value.schema_version ?? 0
      if (version !== 0 && version !== 1) return { status: 'unsupported' }
      if (version === 1 && (value.owner_id !== options.ownerId() || value.page_key !== options.pageKey)) return { status: 'unsupported' }
      const status = layoutStatus(value, schema)
      if (status) return { status }
      return { status: 'ready', value: normalizeColumnPreference({
        ...value,
        selected_column_keys: value.selected_column_keys ?? (options.legacySelectionKey ? value[options.legacySelectionKey] : undefined),
      }, schema) }
    } catch { return { status: 'unavailable' } }
  }
  function write(value: PmsColumnPreference, schema: PmsColumnSchema) {
    const storageKey = key()
    if (!storageKey) return { status: 'anonymous' as const }
    const current = read(schema)
    if (current.status !== 'ready' && current.status !== 'empty') return { status: current.status }
    try {
      const normalized = normalizeColumnPreference(value, schema)
      options.storage().setItem(storageKey, JSON.stringify({
        ...(options.legacySelectionKey ? { [options.legacySelectionKey]: normalized.selected_column_keys } : {}),
        schema_version: 1, page_key: options.pageKey, owner_id: options.ownerId(), ...normalized,
      }))
      return { status: 'saved' as const }
    } catch { return { status: 'unavailable' as const } }
  }
  function clear() {
    const storageKey = key()
    if (!storageKey) return { status: 'anonymous' as const }
    try { options.storage().removeItem(storageKey); return { status: 'cleared' as const } }
    catch { return { status: 'unavailable' as const } }
  }
  return { key, read, write, clear }
}
