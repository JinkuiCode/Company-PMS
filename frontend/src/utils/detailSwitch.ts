/** One confirmation per pending transition; only the latest selection may apply. */
export function createDetailSwitch<T>(guard: () => Promise<boolean>, apply: (row: T, current: () => boolean) => Promise<unknown>) {
  let revision = 0
  let confirmation: Promise<boolean> | null = null
  return {
    invalidate() { revision++ },
    async select(row: T) {
      const ticket = ++revision
      if (!confirmation) confirmation = guard().finally(() => { confirmation = null })
      const allowed = await confirmation
      if (!allowed || ticket !== revision) return
      await apply(row, () => ticket === revision)
    },
  }
}
