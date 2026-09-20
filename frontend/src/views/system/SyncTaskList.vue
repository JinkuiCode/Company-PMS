<template>
  <PmsDataList class="pms-system-page" :show-scrollbar="false">
    <template #toolbar-left>
      <el-button size="small" @click="fetchTasks">刷新</el-button>
      <el-button v-if="canRetry" size="small" :disabled="busy || !selected.length" @click="retry(selected)">批量重试</el-button>
    </template>
    <template #toolbar-right><span v-if="!workerEnabled" class="pms-status warning">后台执行器未启用</span></template>
    <template #filters>
      <PmsListFilters :filters="[]" :fields="[]" :active-count="0">
        <div class="sync-filter"><PmsTextControl v-model="filters.keyword" size="compact" placeholder="项目编号 / 名称" aria-label="同步项目搜索" clearable /></div>
        <div class="sync-filter"><PmsSelectControl v-model="filters.status" size="compact" :options="syncStatusOptions" placeholder="全部同步状态" aria-label="同步状态筛选" clearable /></div>
        <div class="sync-filter"><PmsTextControl v-model="filters.operator" size="compact" placeholder="保存人姓名 / 工号" aria-label="保存人筛选" clearable /></div>
        <div class="sync-filter sync-filter--date"><PmsDateControl v-model="dates" size="compact" type="daterange" value-format="YYYY-MM-DD" start-placeholder="任务开始日期" end-placeholder="任务结束日期" aria-label="任务时间范围" /></div>
      </PmsListFilters>
    </template>
    <template #grid>
      <el-table v-loading="loading" :data="items" class="pms-dense-table" height="100%" border stripe @selection-change="selected = $event">
        <el-table-column v-if="canRetry" type="selection" width="42" :selectable="(row: any) => row.status === 'failed'" />
        <el-table-column prop="project_code" label="项目编号" width="145" fixed />
        <el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status_label" label="同步状态" width="145"><template #default="{ row }"><span class="pms-status" :class="statusTone(row.status)">{{ row.status_label }}</span></template></el-table-column>
        <el-table-column prop="operator_name" label="保存人" width="110" />
        <el-table-column prop="created_at" label="任务时间" width="170"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
        <el-table-column prop="attempts" label="尝试次数" width="90" />
        <el-table-column prop="started_at" label="最后执行时间" width="170"><template #default="{ row }">{{ formatTime(row.started_at) }}</template></el-table-column>
        <el-table-column prop="message" label="执行结果 / 异常原因" min-width="260" show-overflow-tooltip />
        <el-table-column label="操作" :width="PMS_ACTION_COLUMN.width" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openLogs(row)">日志</el-button>
            <el-button v-if="canRetry && row.status === 'failed'" size="small" link type="primary" :disabled="busy" @click="retry([row])">重试</el-button>
            <el-button v-if="canRetry && row.status === 'review'" size="small" link type="warning" :disabled="busy" @click="inspect(row)">核查</el-button>
          </template>
        </el-table-column>
        <template #empty>{{ error || '暂无同步任务' }}</template>
      </el-table>
    </template>
    <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" /></template>
  </PmsDataList>
  <SyncLogDrawer v-model="logVisible" :archive-id="archiveId" />
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import SyncLogDrawer from '@/components/SyncLogDrawer.vue'
import { PmsDateControl, PmsSelectControl, PmsTextControl } from '@/form-system'
import { DEFAULT_PAGE_SIZE, PMS_ACTION_COLUMN } from '@/config/listUi'
import { syncStatusOptions } from '@/config/syncUi'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'
const auth = useAuthStore()
const canRetry = computed(() => auth.hasPermission('system:sync:retry'))
const filters = reactive({ keyword: '', status: '', operator: '' })
const dates = ref<string[]>([]), page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
const items = ref<any[]>([]), selected = ref<any[]>([]), loading = ref(false), busy = ref(false), error = ref('')
const logVisible = ref(false), archiveId = ref<number | null>(null)
const workerEnabled = ref(true)
let serial = 0, timer: ReturnType<typeof setTimeout> | undefined, poll: ReturnType<typeof setInterval> | undefined
const formatTime = (value?: string) => value?.replace('T', ' ').slice(0, 19) || '-'
const statusTone = (status: string) => status === 'success' ? 'success' : status === 'failed' ? 'danger' : status === 'review' ? 'warning' : 'info'
function openLogs(row: any) { archiveId.value = row.archive_id; logVisible.value = true }
async function fetchTasks() {
  const current = ++serial
  loading.value = true
  error.value = ''
  try {
    const data: any = await request.get('/sync-tasks', { params: { ...filters, page: page.value, page_size: pageSize.value,
      start: dates.value?.[0] ? `${dates.value[0]}T00:00:00` : undefined,
      end: dates.value?.[1] ? `${dates.value[1]}T23:59:59.999999` : undefined } })
    if (current !== serial) return
    items.value = data.items; total.value = data.total; selected.value = []; workerEnabled.value = data.worker_enabled !== false
  } catch { if (current === serial) { items.value = []; total.value = 0; error.value = '任务加载失败，请刷新重试' } }
  finally { if (current === serial) loading.value = false }
}
async function retry(rows: any[]) {
  if (!canRetry.value || busy.value) return
  try { await ElMessageBox.confirm(`重新安排 ${rows.length} 条已确认失败的任务？系统仅处理档案最新版本。`, '重试同步') } catch { return }
  busy.value = true
  try {
    const data: any = await request.post('/sync-tasks/retry', { task_ids: rows.map(row => row.id) })
    const failures = data.items.filter((item: any) => !item.success)
    if (failures.length) ElMessage.warning(`${failures.length} 条未安排：${String(failures[0].message)}`)
    else ElMessage.success('已安排后台重试')
    await fetchTasks()
  } catch { /* The shared request handler displays the server error. */ }
  finally { busy.value = false }
}
async function inspect(row: any) {
  if (!canRetry.value || busy.value) return
  try { await ElMessageBox.confirm('请先在金蝶端确认原请求已处理完毕，而不是仅关闭 PMS 页面。确认后只读核查资料；结果不一致将转为失败并允许重试。无法确认时请取消。', '确认原请求结束并核查', { confirmButtonText: '已确认，开始核查' }) } catch { return }
  busy.value = true
  try { const data: any = await request.post(`/sync-tasks/${row.id}/inspect`, null, { params: { external_request_finished: true } }); ElMessage.info(data.message); await fetchTasks() }
  catch { /* The shared request handler displays the server error. */ }
  finally { busy.value = false }
}
watch([filters, dates, pageSize], () => { page.value = 1 }, { deep: true, flush: 'sync' })
watch([filters, dates, page, pageSize], () => { ++serial; clearTimeout(timer); timer = setTimeout(fetchTasks, 200) }, { deep: true })
onMounted(() => { void fetchTasks(); poll = setInterval(() => { if (!busy.value && !loading.value && !selected.value.length && !logVisible.value) void fetchTasks() }, 15000) })
onUnmounted(() => { ++serial; clearTimeout(timer); clearInterval(poll) })
</script>

<style scoped>
.sync-filter { width: 190px; max-width: 100%; }
.sync-filter--date { width: 280px; }
</style>
