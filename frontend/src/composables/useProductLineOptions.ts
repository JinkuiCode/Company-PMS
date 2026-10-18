import { computed, ref } from 'vue'
import { getProductLineLabels, getProductLineOptions, type LineOption } from '@/api/productLine'

export function useProductLineOptions(fetchOptions = getProductLineOptions) {
  const options = ref<LineOption[]>([])
  const labels = ref<Record<string, string>>({})
  const loading = ref(false), failed = ref(false)
  const labelsLoading = ref(false), labelsFailed = ref(false)
  let version = 0, labelsVersion = 0
  const filterOptions = computed(() => Object.entries(labels.value).map(([value, label]) => ({ value: Number(value), label })))
  function label(value: unknown) {
    return value == null || value === '' ? '-' : labels.value[String(value)] || '名称暂不可用'
  }
  function currentOptions(value: unknown): LineOption[] {
    if (value == null || value === '' || options.value.some(option => String(option.value) === String(value))) return options.value
    return [...options.value, { value: Number(value), label: label(value), disabled: true }]
  }
  async function loadLabels() {
    const current = ++labelsVersion
    labelsLoading.value = true; labelsFailed.value = false
    labels.value = {}
    try {
      const data = await getProductLineLabels()
      if (current === labelsVersion) labels.value = data.label_map || {}
    } catch {
      if (current === labelsVersion) labelsFailed.value = true
    } finally { if (current === labelsVersion) labelsLoading.value = false }
  }
  async function loadOptions() {
    const current = ++version
    loading.value = true; failed.value = false
    try {
      const data = await fetchOptions()
      if (current !== version) return
      options.value = data.options
    } catch {
      if (current === version) { options.value = []; failed.value = true }
    } finally { if (current === version) loading.value = false }
  }
  async function load() { await Promise.all([loadLabels(), loadOptions()]) }
  return { options, labels, filterOptions, label, currentOptions, load, loadLabels, loadOptions,
    loading, failed, labelsLoading, labelsFailed }
}
