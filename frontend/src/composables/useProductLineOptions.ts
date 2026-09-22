import { computed, ref } from 'vue'
import { getProductLineOptions, type LineOption } from '@/api/productLine'

export function useProductLineOptions() {
  const options = ref<LineOption[]>([])
  const labels = ref<Record<string, string>>({})
  const loading = ref(false), failed = ref(false)
  let version = 0
  const filterOptions = computed(() => Object.entries(labels.value).map(([value, label]) => ({ value: Number(value), label })))
  function label(value: unknown) {
    return value == null || value === '' ? '-' : labels.value[String(value)] || String(value)
  }
  async function load() {
    const current = ++version
    loading.value = true; failed.value = false
    try {
      const data = await getProductLineOptions()
      if (current !== version) return
      options.value = data.options; labels.value = data.label_map
    } catch {
      if (current === version) { options.value = []; failed.value = true }
    } finally { if (current === version) loading.value = false }
  }
  return { options, labels, filterOptions, label, load, loading, failed }
}
