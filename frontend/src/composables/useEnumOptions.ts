import { reactive } from 'vue'
import request from '@/utils/request'

export type EnumOption = {
  value: string
  label: string
  status?: number
}

export type EnumDefinition = {
  dict_code: string
  dict_name: string
  items: EnumOption[]
  all_items: EnumOption[]
  label_map: Record<string, string>
}

const cache = reactive<Record<string, EnumDefinition>>({})
const pending = new Map<string, Promise<EnumDefinition>>()

function normalizeDefinition(code: string, value: Partial<EnumDefinition> | null | undefined): EnumDefinition {
  const allItems = Array.isArray(value?.all_items) ? value!.all_items! : (value?.items || [])
  return {
    dict_code: value?.dict_code || code,
    dict_name: value?.dict_name || '',
    items: value?.items || [],
    all_items: allItems,
    label_map: value?.label_map || Object.fromEntries(allItems.map(item => [String(item.value), item.label])),
  }
}

export async function loadEnumOptions(code: string, force = false): Promise<EnumDefinition> {
  if (!force && cache[code]) return cache[code]
  if (!force && pending.has(code)) return pending.get(code)!

  const promise = request.get(`/dicts/code/${code}`)
    .then(response => {
      const definition = normalizeDefinition(code, response as Partial<EnumDefinition>)
      cache[code] = definition
      return definition
    })
    .finally(() => pending.delete(code))

  pending.set(code, promise)
  return promise
}

export function useEnumOptions(codes: readonly string[]) {
  const definitions = reactive<Record<string, EnumDefinition>>({})

  async function load(force = false) {
    const results = await Promise.all(codes.map(code => loadEnumOptions(code, force)))
    results.forEach(definition => {
      definitions[definition.dict_code] = definition
    })
    return definitions
  }

  function options(code: string, numeric = false) {
    return (definitions[code]?.items || []).map(item => ({
      label: item.label,
      value: numeric ? Number(item.value) : item.value,
    }))
  }

  function label(code: string, value: unknown, fallback = '-') {
    if (value === null || value === undefined || value === '') return fallback
    return definitions[code]?.label_map?.[String(value)] || String(value)
  }

  return { definitions, load, options, label }
}
