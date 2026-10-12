export function createColumnPopupGroup() {
  let active: { owner: symbol; close: () => void } | null = null
  return {
    close() {
      const previous = active
      active = null
      previous?.close()
    },
    open(owner: symbol, close: () => void) {
      if (active?.owner === owner) return
      const previous = active
      active = null
      previous?.close()
      active = { owner, close }
    },
    release(owner: symbol) {
      if (active?.owner === owner) active = null
    },
  }
}

export const columnPopupGroup = createColumnPopupGroup()
