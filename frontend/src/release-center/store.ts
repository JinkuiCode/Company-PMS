import { defineStore } from 'pinia'
import { ref } from 'vue'
import request from '@/utils/request'
export interface RuntimeInfo { product: string; version: string; environment: string; published_at?: string | null;
  technical?: { commit: string | null; build_id: string | null; database_revision: string };
  page_updates: Record<string, { version: string; published_at?: string }> }
export const useReleaseStore = defineStore('release-center', () => {
  const runtime = ref<RuntimeInfo | null>(null), unread = ref(0)
  let serial = 0
  async function refresh() {
    const current = ++serial
    const results = await Promise.allSettled([
      request.get<never, RuntimeInfo>('/releases/runtime'),
      request.get<never, { unread: number }>('/releases/notices', { params: { page_size: 1 } }),
    ])
    if (current !== serial) return
    if (results[0].status === 'fulfilled') runtime.value = results[0].value
    else runtime.value = null
    if (results[1].status === 'fulfilled') unread.value = results[1].value.unread
  }
  function reset() { ++serial; runtime.value = null; unread.value = 0 }
  return { runtime, unread, refresh, reset }
})
