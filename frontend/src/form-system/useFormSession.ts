import { computed, readonly, shallowRef, toRaw } from 'vue'

export type PmsFormPhase = 'idle' | 'validating' | 'saving' | 'error' | 'conflict'
export type PmsFormSubmitResult<R> =
  | { status: 'success'; value: R }
  | { status: 'invalid' | 'busy' }
  | { status: 'failed'; error: unknown; presentationError?: unknown }

/** One form's in-memory draft lifecycle. Business validation, version checks and feedback stay in its adapter. */
export function useFormSession<T extends Record<string, unknown>>(options: {
  draft: T
  clone?: (value: T) => T
  equals?: (left: T, right: T) => boolean
  isConflict?: (error: unknown) => boolean
}) {
  const clone = options.clone ?? ((value: T): T => structuredClone(toRaw(value)))
  const equals = options.equals ?? ((left: T, right: T) => JSON.stringify(left) === JSON.stringify(right))
  const original = shallowRef<T>(clone(options.draft))
  const phase = shallowRef<PmsFormPhase>('idle')
  const error = shallowRef<unknown>(null)
  let confirmingClose = false
  const busy = computed(() => phase.value === 'validating' || phase.value === 'saving')
  const dirty = computed(() => !equals(options.draft, original.value))
  const locked = () => busy.value || confirmingClose

  function capture() {
    if (locked()) return false
    original.value = clone(options.draft)
    phase.value = 'idle'
    error.value = null
    return true
  }

  function restore() {
    if (locked()) return false
    const baseline = clone(original.value)
    for (const key of Object.keys(options.draft)) delete options.draft[key]
    Object.assign(options.draft, baseline)
    phase.value = 'idle'
    error.value = null
    return true
  }

  async function submit<R>(operation: {
    validate: () => boolean | Promise<boolean>
    save: (snapshot: T) => R | Promise<R>
    onError?: (error: unknown) => void | Promise<void>
  }): Promise<PmsFormSubmitResult<R>> {
    if (locked()) return { status: 'busy' }
    // Acquire before validation: async validators can otherwise allow several saves through.
    phase.value = 'validating'
    error.value = null
    try {
      if (!await operation.validate()) {
        phase.value = 'idle'
        return { status: 'invalid' }
      }
      const submitted = clone(options.draft)
      phase.value = 'saving'
      const value = await operation.save(clone(submitted))
      original.value = submitted
      phase.value = 'idle'
      return { status: 'success', value }
    } catch (cause) {
      error.value = cause
      let presentationError: unknown
      try { await operation.onError?.(cause) } catch (feedbackFailure) { presentationError = feedbackFailure }
      phase.value = options.isConflict?.(cause) ? 'conflict' : 'error'
      return { status: 'failed', error: cause, ...(presentationError === undefined ? {} : { presentationError }) }
    }
  }

  async function requestClose(confirmDiscard: () => boolean | Promise<boolean>) {
    if (locked()) return false
    if (!dirty.value) return true
    confirmingClose = true
    try {
      return await confirmDiscard()
    } catch {
      return false
    } finally {
      confirmingClose = false
    }
  }

  return { original: readonly(original), phase: readonly(phase), error: readonly(error), busy, dirty, capture, restore, submit, requestClose }
}
