<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { businessExportFilename, businessExportPermission, businessViewPermission, downloadBusinessExport, type BusinessExportResource } from '@/api/businessExport'
import type { BusinessExportSnapshot } from './snapshot'

const props = defineProps<{ resource: BusinessExportResource; snapshot: () => BusinessExportSnapshot; disabled?: boolean }>()
const auth = useAuthStore()
const allowed = computed(() => auth.hasPermission(businessViewPermission(props.resource)) && auth.hasPermission(businessExportPermission(props.resource)))
const submitting = ref(false)
let run = 0, disposed = false
watch(() => [auth.user?.id, props.resource.kind, props.resource.kind === 'tasks' ? props.resource.projectId : null], () => {
  run++
  submitting.value = false
}, { flush: 'sync' })
onBeforeUnmount(() => { disposed = true; run++; submitting.value = false })

async function submit() {
  if (disposed || props.disabled || !allowed.value || submitting.value) return
  let snapshot: BusinessExportSnapshot
  try { snapshot = props.snapshot() }
  catch (error) { ElMessage.warning(error instanceof Error ? error.message : '导出条件无效，请重新查询'); return }
  const resource = { ...props.resource }, currentRun = ++run
  submitting.value = true
  try {
    const blob = await downloadBusinessExport(resource, snapshot)
    if (disposed || currentRun !== run || !allowed.value) return
    const url = URL.createObjectURL(blob)
    try {
      const link = document.createElement('a')
      link.href = url
      link.download = businessExportFilename(resource)
      link.click()
    } finally { setTimeout(() => URL.revokeObjectURL(url), 1000) }
  } catch { /* The shared request handler displays API errors. */ }
  finally { if (currentRun === run) submitting.value = false }
}
</script>

<template>
  <el-button v-if="allowed" class="pms-button-export" size="small" :icon="Download" :loading="submitting" :disabled="disabled" @click="submit">导出数据</el-button>
</template>
