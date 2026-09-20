<template>
  <PmsFormDrawer :model-value="modelValue" title="档案同步记录" @update:model-value="$emit('update:modelValue', $event)">
    <div v-loading="loading" class="sync-log-content">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-empty v-else-if="!loading && !items.length" description="暂无后台同步记录" />
      <section v-for="task in items" :key="task.id" class="sync-log-entry">
        <h3 class="pms-form-drawer__section">{{ task.project_code }} · {{ task.status_label }}</h3>
        <p>{{ task.created_at?.replace('T', ' ') }} · {{ task.operator_name }}</p>
        <p>{{ task.message }}</p>
        <ol>
          <li v-for="(entry, index) in task.history" :key="index">
            <time>{{ entry.time?.replace('T', ' ').slice(0, 19) }}</time>
            <div>{{ entry.message }}</div>
          </li>
        </ol>
      </section>
    </div>
    <template #footer>
      <span>第 {{ page }} 页 · 共 {{ total }} 条</span>
      <el-button :disabled="page <= 1 || loading" @click="page--">上一页</el-button>
      <el-button :disabled="page * 50 >= total || loading" @click="page++">下一页</el-button>
      <el-button @click="fetchLogs">刷新</el-button>
    </template>
  </PmsFormDrawer>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { PmsFormDrawer } from '@/form-system'
import request from '@/utils/request'
const props = defineProps<{ modelValue: boolean; archiveId: number | null }>()
defineEmits<{ 'update:modelValue': [value: boolean] }>()
const loading = ref(false), error = ref(''), items = ref<any[]>([]), page = ref(1), total = ref(0)
let serial = 0
async function fetchLogs() {
  if (!props.modelValue || !props.archiveId) return
  const current = ++serial
  loading.value = true
  error.value = ''
  try {
    const response: any = await request.get(`/sync-tasks/archive/${props.archiveId}`, { params: { page: page.value, page_size: 50 } })
    if (current !== serial) return
    items.value = response.items
    total.value = response.total
  } catch { if (current === serial) { items.value = []; total.value = 0; error.value = '同步记录加载失败，请刷新重试' } }
  finally { if (current === serial) loading.value = false }
}
watch(() => [props.modelValue, props.archiveId], () => { ++serial; items.value = []; page.value = 1; void fetchLogs() })
watch(page, fetchLogs)
onUnmounted(() => { ++serial })
</script>

<style scoped>
.sync-log-content { min-height: 100px; }
.sync-log-entry p, .sync-log-entry li { font-size: var(--pms-font-size-sm); line-height: 1.6; overflow-wrap: anywhere; }
.sync-log-entry time { color: var(--pms-text-muted); }
.sync-log-entry ol { padding-left: 18px; }
</style>
