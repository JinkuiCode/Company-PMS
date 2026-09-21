export interface PurchaseDetailState<T> {
  open: boolean
  requestId: string | null
  orderId: string | null
  loading: boolean
  data: T | null
  error: string | null
}

/** Scoped to one procurement drawer; no global state or persisted business data. */
export function createPurchaseDetailState<T>(
  load: (requestId: string, signal: AbortSignal) => Promise<T>,
  changed: (state: Readonly<PurchaseDetailState<T>>) => void = () => {},
) {
  let state: PurchaseDetailState<T> = {
    open: false, requestId: null, orderId: null, loading: false, data: null, error: null,
  }
  let revision = 0
  let pending: AbortController | null = null
  function update(patch: Partial<PurchaseDetailState<T>>) {
    state = { ...state, ...patch }
    changed(state)
  }
  async function open(requestId: string) {
    const current = ++revision
    pending?.abort()
    pending = new AbortController()
    update({ open: true, requestId, orderId: null, loading: true, data: null, error: null })
    try {
      const data = await load(requestId, pending.signal)
      if (current === revision) update({ data })
    } catch {
      if (current === revision) update({ error: '明细加载失败，请重试' })
    } finally {
      if (current === revision) {
        pending = null
        update({ loading: false })
      }
    }
  }
  function close() {
    ++revision
    pending?.abort()
    pending = null
    update({ open: false, requestId: null, orderId: null, loading: false, data: null, error: null })
  }
  return {
    get state(): Readonly<PurchaseDetailState<T>> { return state },
    open,
    close,
    async selectRow(requestId: string) {
      if (state.open && state.requestId !== requestId) await open(requestId)
    },
    selectOrder(orderId: string | null) {
      if (state.open) update({ orderId })
    },
    async retry() {
      if (state.open && state.requestId) await open(state.requestId)
    },
    reconcileRows(requestIds: readonly string[]) {
      if (state.open && state.requestId && !requestIds.includes(state.requestId)) close()
    },
  }
}
