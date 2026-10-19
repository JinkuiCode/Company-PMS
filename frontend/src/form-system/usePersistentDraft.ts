import { ref } from 'vue'

export type PersistentDraft = {
  id: string; version: number; status: 'active' | 'used'; archive_id?: number | null
  payload: Record<string, unknown>; warnings?: string[]; value_labels?: Record<string,string>
}
type DraftTransport = {
  get: (id: string) => Promise<PersistentDraft>
  save: (body: { id: string; expected_version: number | null; payload: Record<string, unknown> }) => Promise<PersistentDraft>
  submit: (id: string, version: number) => Promise<{ id: number }>
}
export function createDraftId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6]! & 15) | 64; bytes[8] = (bytes[8]! & 63) | 128
  const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`
}
const uncertain = (e: any) => !e?.response || e.response.status >= 500
const equal = (a: Record<string,unknown>, b: Record<string,unknown>) => {
  const keys = Object.keys(a).sort()
  return keys.join() === Object.keys(b).sort().join() && keys.every(key => key === 'quantity' && a[key] != null && b[key] != null
    ? Number(a[key]) === Number(b[key]) : key === 'project_code' && typeof a[key] === 'string' && typeof b[key] === 'string'
      ? a[key].trim() === b[key].trim() : JSON.stringify(a[key]) === JSON.stringify(b[key]))
}

/** Persistence only; the form session owns validation, input and interaction locks. */
export function usePersistentDraft(api: DraftTransport, newId = createDraftId) {
  const id = ref<string | null>(null), version = ref<number | null>(null)
  const conflict = ref(false), unknown = ref<'save' | 'submit' | null>(null)
  let pendingPayload: Record<string, unknown> | null = null
  function startNew() {
    if (unknown.value) throw new Error('请先核对上次保存结果')
    id.value = null; version.value = null; conflict.value = false; pendingPayload = null
  }
  function attach(row: PersistentDraft) {
    id.value = row.id; version.value = row.version; conflict.value = false; unknown.value = null
  }
  async function save(payload: Record<string, unknown>) {
    if (unknown.value) throw new Error('请先核对上次保存结果')
    if (conflict.value) throw new Error('请先加载最新草稿或另存为新草稿')
    id.value ??= newId()
    pendingPayload = structuredClone(payload)
    try {
      const row = await api.save({ id: id.value, expected_version: version.value, payload })
      attach(row)
      return row
    } catch (error: any) {
      conflict.value = error?.response?.status === 409 && error?.response?.data?.detail?.code === 'DRAFT_VERSION_CONFLICT'
      if (uncertain(error)) unknown.value = 'save'
      throw error
    }
  }
  async function submit() {
    if (unknown.value) throw new Error('请先核对上次保存结果')
    if (!id.value || !version.value || conflict.value) throw new Error('请先保存当前草稿')
    try { return await api.submit(id.value, version.value) }
    catch (error: any) {
      conflict.value = error?.response?.status === 409 && error?.response?.data?.detail?.code === 'DRAFT_VERSION_CONFLICT'
      if (uncertain(error)) unknown.value = 'submit'
      throw error
    }
  }
  async function reconcile() {
    if (!id.value) throw new Error('没有待核对的草稿')
    try {
      const row = await api.get(id.value)
      if (unknown.value === 'save' && row.status === 'active' && pendingPayload && !equal(pendingPayload, row.payload)) {
        unknown.value = null; conflict.value = true
      } else attach(row)
      return row
    } catch (error: any) {
      if (unknown.value === 'save' && error?.response?.status === 404) {
        unknown.value = null
        return null // Initial save did not arrive. Retry the same UUID, never a second record.
      }
      throw error
    }
  }
  return { id, version, conflict, unknown, startNew, attach, save, submit, reconcile }
}
