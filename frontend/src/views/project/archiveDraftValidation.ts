/** Draft identity and product-line scope; formal creation keeps all effective rules. */
export function archiveDraftIdentityErrors(values: Record<string, unknown>): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const [key, label] of [['project_code', '项目编号'], ['project_name', '项目名称']] as const) {
    if (typeof values[key] !== 'string' || !values[key].trim()) errors[key] = `请填写${label}`
  }
  if (typeof values.product_line_id !== 'number' || !Number.isSafeInteger(values.product_line_id) || values.product_line_id <= 0) {
    errors.product_line_id = '请选择产品线'
  }
  if (typeof values.archive_category !== 'number' || !Number.isSafeInteger(values.archive_category) || values.archive_category <= 0) {
    errors.archive_category = '请选择档案类别'
  }
  return errors
}

/** Parse only the shared archive identity error contract, never business payload. */
export function archiveIdentityFailure(error: unknown): { field_key: string; message: string; allowCorrection: boolean } | null {
  const detail = (error as { response?: { data?: { detail?: Record<string, unknown> } } })?.response?.data?.detail
  if (!detail || !['ARCHIVE_UNIQUE_CONFLICT', 'ARCHIVE_FIELD_REQUIRED', 'ARCHIVE_CODE_BUSY', 'ARCHIVE_SERIAL_BUSY', 'ARCHIVE_SERIAL_UNAVAILABLE'].includes(String(detail.code)) || !detail.field_key) return null
  return {field_key: String(detail.field_key), message: String(detail.message || '字段值无法保存，请核对后重试'), allowCorrection: detail.code === 'ARCHIVE_UNIQUE_CONFLICT'}
}
