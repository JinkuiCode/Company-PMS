<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Download, Refresh } from '@element-plus/icons-vue'
import { createReportExport, listReportExports, downloadReportExport, type ReportExportJob, type ReportName } from '@/api/reportExport'

const props = defineProps<{ report: ReportName; parameters: () => object; columns: () => string[]; disabled?: boolean }>()
const jobs = ref<ReportExportJob[]>([]), submitting = ref(false), downloading = ref(''), opened = ref(false)
const pollFailed = ref(false)
const busy = computed(() => jobs.value.some(job => ['queued', 'running'].includes(job.status)))
const labels = { queued: '排队中', running: '生成中', success: '已完成', failed: '失败', expired: '已过期' }
let timer: ReturnType<typeof setTimeout> | undefined, disposed = false
async function refresh() {
  clearTimeout(timer)
  try { jobs.value = await listReportExports(props.report); pollFailed.value = false }
  catch { pollFailed.value = true }
  if (!disposed && !pollFailed.value && busy.value) timer = setTimeout(refresh, 3000)
}
async function submit() {
  submitting.value = true
  try {
    const job = await createReportExport(props.report, props.parameters(), props.columns())
    jobs.value = [job, ...jobs.value].slice(0, 20)
    opened.value = true
    await refresh()
  } catch { /* The shared request handler displays the error. */ }
  finally { submitting.value = false }
}
async function download(job: ReportExportJob) {
  downloading.value = job.id
  try {
    const blob = await downloadReportExport(job.id)
    const url = URL.createObjectURL(blob), link = document.createElement('a')
    link.href = url
    link.download = `${props.report === 'purchase' ? '采购进度' : '即时库存'}-${job.id.slice(0, 8)}.xlsx`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch { /* The shared request handler displays the error. */ }
  finally { downloading.value = '' }
}
onMounted(refresh)
onUnmounted(() => { disposed = true; clearTimeout(timer) })
</script>

<template>
  <div class="report-export-control">
    <el-button size="small" :icon="Download" :loading="submitting" :disabled="disabled || busy" @click="submit">导出当前筛选</el-button>
    <el-popover v-model:visible="opened" trigger="click" placement="bottom-end" :width="380" @show="refresh">
      <template #reference><el-button size="small">导出任务{{ busy ? ' · 处理中' : '' }}</el-button></template>
      <div class="report-export-heading"><strong>导出任务</strong><el-button :icon="Refresh" link aria-label="刷新导出任务" @click="refresh" /></div>
      <p v-if="pollFailed" role="alert">状态获取失败，请刷新重试。</p>
      <p v-else-if="!jobs.length">暂无导出任务</p>
      <div class="report-export-jobs" aria-live="polite">
        <div v-for="job in jobs" :key="job.id" class="report-export-job">
          <div><strong>{{ labels[job.status] }}</strong><span>{{ job.processed.toLocaleString() }} 条主表数据</span></div>
          <div><time>{{ job.created_at.replace('T', ' ').slice(0, 19) }}</time><el-button v-if="job.status === 'success'" size="small" link type="primary" :loading="downloading === job.id" @click="download(job)">下载</el-button></div>
          <p v-if="job.message">{{ job.message }}</p>
        </div>
      </div>
    </el-popover>
  </div>
</template>

<style scoped>
.report-export-control { display: inline-flex; align-items: center; gap: 8px; }
.report-export-control :deep(.el-button + .el-button) { margin-left: 0; }
.report-export-heading, .report-export-job > div { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.report-export-jobs { max-height: 360px; overflow-y: auto; }
.report-export-job { padding: 12px 0; border-bottom: 1px solid var(--pms-border); font-family: var(--pms-font); }
.report-export-job p { margin: 4px 0 0; overflow-wrap: anywhere; }
.report-export-job time { font-size: 12px; color: var(--pms-text-secondary); }
</style>
