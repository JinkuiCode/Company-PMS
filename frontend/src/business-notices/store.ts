import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

export const useBusinessNoticeStore = defineStore('business-notices', () => {
  const unread = ref(0), known = ref(false), failed = ref(false)
  let serial = 0
  async function refresh() {
    const current = ++serial, auth = useAuthStore()
    if (!auth.token || !auth.hasPermission('project:archive:view')) { unread.value = 0; known.value = true; failed.value = false; return }
    try {
      const data = await request.get<never, { unread: number }>('/business-notices', { params: { page_size: 1 } })
      if (current !== serial) return
      unread.value = data.unread; known.value = true; failed.value = false
    } catch { if (current === serial) failed.value = true }
  }
  function reset() { ++serial; unread.value = 0; known.value = false; failed.value = false }
  return { unread, known, failed, refresh, reset }
})
