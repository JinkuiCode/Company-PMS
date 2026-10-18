import { computed, readonly, shallowRef } from 'vue'

export type PmsPagePhase = 'idle' | 'loading' | 'ready' | 'empty' | 'error'

/** Request lifecycle only. Adapters check isCurrent before applying business rows or totals. */
export function usePageLoad() {
  let serial = 0
  const phase = shallowRef<PmsPagePhase>('idle')
  const hasQueried = shallowRef(false)
  const error = shallowRef<unknown>(null)
  const loading = computed(() => phase.value === 'loading')
  const failed = computed(() => phase.value === 'error')
  const isCurrent = (ticket: number) => ticket === serial

  function begin() {
    serial++
    phase.value = 'loading'
    error.value = null
    return serial
  }

  function succeed(ticket: number, empty = false) {
    if (!isCurrent(ticket)) return false
    hasQueried.value = true
    error.value = null
    phase.value = empty ? 'empty' : 'ready'
    return true
  }

  function fail(ticket: number, cause: unknown) {
    if (!isCurrent(ticket)) return false
    error.value = cause
    phase.value = 'error'
    return true
  }

  function invalidate(pending = false) {
    serial++
    phase.value = pending ? 'loading' : 'idle'
    error.value = null
  }

  return { phase: readonly(phase), hasQueried: readonly(hasQueried), error: readonly(error), loading, failed, begin, isCurrent, succeed, fail, invalidate }
}
