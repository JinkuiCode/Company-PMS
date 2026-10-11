import type { ReferenceRecord } from './reference'

export function referenceSummary(values: (string | number)[], records: ReferenceRecord[] = [], codes = false) {
  const unique = [...new Set(values)]
  const labels = new Map(records.map(r => [r.value, (codes ? r.code : r.name) || r.code]))
  const texts = unique.map(value => labels.get(value) || String(value))
  return {
    text: texts.length ? texts.slice(0, 3).join('、') : '选择引用记录',
    title: texts.length ? texts.join('、') : '选择引用记录',
    count: texts.length,
  }
}
