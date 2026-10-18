/** Draft identity and product-line scope; formal creation keeps all effective rules. */
export function archiveDraftIdentityErrors(values: Record<string, unknown>): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const [key, label] of [['project_code', '项目编号'], ['project_name', '项目名称']] as const) {
    if (typeof values[key] !== 'string' || !values[key].trim()) errors[key] = `请填写${label}`
  }
  if (typeof values.product_line_id !== 'number' || !Number.isSafeInteger(values.product_line_id) || values.product_line_id <= 0) {
    errors.product_line_id = '请选择产品线'
  }
  return errors
}
