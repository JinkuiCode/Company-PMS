// Match each top-level selector; commas inside :is()/attributes belong to the selector itself.
export function isFormSystemSelector(line) {
  const source = line.split('{', 1)[0].trim()
  const selectors = []
  let current = '', depth = 0, quote = '', escaped = false
  for (const char of source) {
    if (quote) {
      current += char
      if (escaped) escaped = false
      else if (char === '\\') escaped = true
      else if (char === quote) quote = ''
      continue
    }
    if (char === '"' || char === "'") quote = char
    if (char === '(' || char === '[') depth++
    if (char === ')' || char === ']') depth--
    if (char === ',' && depth === 0) { selectors.push(current.trim()); current = '' }
    else current += char
  }
  if (current.trim()) selectors.push(current.trim())
  const shared = /^\.pms-(form-control|form-grid)(?=\s|[.#:]|\[|[>+~]|$)/
  const query = /^\.pms-query-density\s+\.pms-form-control(?=\s|[.#:]|\[|[>+~]|$)/
  return selectors.length > 0 && selectors.every(selector => shared.test(selector) || query.test(selector))
}
