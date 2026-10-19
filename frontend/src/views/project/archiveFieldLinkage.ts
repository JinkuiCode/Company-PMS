/** Consume the scoped server registry; do not duplicate business mappings. */
export interface ArchiveFieldLinkage {
  line_profiles: Record<string, string>
  profiles: Record<string, Record<string, number[]>>
}
const linkedFields = ['machine_model', 'equipment_series'] as const

function incompatible(metadata: ArchiveFieldLinkage | null, line: unknown, field: string, value: unknown) {
  if (!metadata || !linkedFields.includes(field as typeof linkedFields[number])) return false
  const profile = metadata.profiles[metadata.line_profiles[String(line)] || '']
  if (!profile || value === null || value === undefined || value === '') return false
  const assigned = Object.values(metadata.profiles).some(group => (group[field] || []).some(item => String(item) === String(value)))
  return assigned && !(profile[field] || []).some(item => String(item) === String(value))
}

export function filterArchiveLinkedOptions<T extends { value: unknown }>(
  metadata: ArchiveFieldLinkage | null, line: unknown, field: string, options: T[],
): T[] {
  return options.filter(option => !incompatible(metadata, line, field, option.value))
}

export function reconcileArchiveLinkedFields(metadata: ArchiveFieldLinkage | null, values: Record<string, unknown>): string[] {
  const cleared: string[] = []
  for (const field of linkedFields) {
    if (incompatible(metadata, values.product_line_id, field, values[field])) {
      values[field] = null
      cleared.push(field)
    }
  }
  return cleared
}
