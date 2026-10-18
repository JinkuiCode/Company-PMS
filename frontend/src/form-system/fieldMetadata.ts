export interface PmsFieldPolicy {
  visible?: boolean
  editable?: boolean
  required?: boolean
  list_available?: boolean
}

/** Merge server metadata with a page's stricter code-defined ceiling. */
export function resolveFieldMetadata(policy?: PmsFieldPolicy, ceiling: {
  hidden?: boolean
  readonly?: boolean
  required?: boolean
  readonlyReason?: string
} = {}) {
  const visible = !ceiling.hidden && policy?.visible !== false
  const editable = visible && !ceiling.readonly && policy?.editable !== false
  return {
    visible, editable,
    required: visible && (ceiling.required ?? policy?.required === true),
    listAvailable: visible && policy?.list_available !== false,
    readonlyReason: visible && !editable ? ceiling.readonlyReason || '此字段仅供查看' : '',
  }
}

/** Project known structured errors onto currently visible form fields, in presentation order. */
export function mapFormFieldErrors(error: unknown, fieldsInOrder: readonly string[], visible: (key: string) => boolean) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  const candidates: Array<{ key: unknown; message: unknown }> = []
  if (Array.isArray(detail)) {
    for (const field of detail) {
      if (!Array.isArray(field?.loc) || field.loc[0] !== 'body') continue
      candidates.push({ key: field.loc.at(-1), message: field.msg })
    }
  } else if (detail && typeof detail === 'object') {
    const value = detail as { code?: unknown; fields?: unknown; field_key?: unknown; message?: unknown }
    if (['FIELD_POLICY_VALIDATION_FAILED', 'FIELD_POLICY_INVALID'].includes(String(value.code)) && Array.isArray(value.fields)) {
      for (const field of value.fields) candidates.push({ key: field?.field_key, message: field?.message })
    } else if (['ARCHIVE_UNIQUE_CONFLICT', 'ARCHIVE_FIELD_REQUIRED'].includes(String(value.code))) {
      candidates.push({ key: value.field_key, message: value.message })
    }
  }
  const errors: Record<string, string> = {}
  for (const key of fieldsInOrder) {
    if (!visible(key) || Object.hasOwn(errors, key)) continue
    const field = candidates.find(item => item.key === key)
    if (field) errors[key] = typeof field.message === 'string' && field.message.trim() ? field.message : '请检查此字段'
  }
  return { errors, firstField: Object.keys(errors)[0] ?? null }
}
