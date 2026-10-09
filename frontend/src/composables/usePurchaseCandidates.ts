import { onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getPurchaseOptions } from '@/api/purchaseReport'

export function usePurchaseCandidates(organizations: () => number[], project: () => string, setProject: (value: string) => void) {
  const candidates = reactive({ project: [] as { value: string; label: string }[], supplier: [] as { value: string; label: string }[] })
  const optionLoading = reactive({ project: false, supplier: false })
  const validationError = ref(''), validating = ref(false)
  const revisions = { project: 0, supplier: 0 }
  let validationRevision = 0
  function invalidate() {
    ++validationRevision
    ++revisions.project; ++revisions.supplier
    candidates.project = []; candidates.supplier = []
    optionLoading.project = false; optionLoading.supplier = false
    validationError.value = ''; validating.value = false
  }
  async function findOptions(field: 'project' | 'supplier', keyword = '') {
    const revision = ++revisions[field], ids = [...organizations()]
    optionLoading[field] = true
    try {
      const data = await getPurchaseOptions(field, keyword, ids)
      if (revision === revisions[field]) candidates[field] = data.items
    } catch { if (revision === revisions[field]) candidates[field] = [] }
    finally { if (revision === revisions[field]) optionLoading[field] = false }
  }
  function organizationsChanged() {
    invalidate(); setProject(''); void findOptions('project')
  }
  async function restoreProject(preserveInvalidProject = false) {
    invalidate()
    const code = project()
    if (!code) return
    const revision = validationRevision, optionRevision = revisions.project, ids = [...organizations()]
    validating.value = true
    try {
      const data = await getPurchaseOptions('project', '', ids, code)
      if (revision !== validationRevision || project() !== code) return
      if (data.items.some(item => item.value === code)) {
        if (optionRevision === revisions.project) candidates.project = data.items
      }
      else if (preserveInvalidProject) validationError.value = '方案限定项目已不可查询，请清除项目限定或重新选择方案'
      else { setProject(''); ElMessage.warning('原项目不属于所选产品线或已不可查询，请重新选择项目') }
    } catch {
      if (revision === validationRevision) validationError.value = '项目范围核验失败，请重新选择产品线或项目'
    } finally { if (revision === validationRevision) validating.value = false }
  }
  function projectChanged() { ++validationRevision; validationError.value = ''; validating.value = false }
  onUnmounted(invalidate)
  return { candidates, optionLoading, findOptions, organizationsChanged, restoreProject, invalidate, projectChanged,
    validationError, validating }
}
