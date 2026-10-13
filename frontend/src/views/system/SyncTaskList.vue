<template>
  <PmsDataList class="pms-system-page" :show-scrollbar="false">
    <template #toolbar-left>
      <el-button size="small" @click="fetchTasks">刷新</el-button>
      <el-button v-if="canRetry" size="small" :disabled="busy || !selected.length" @click="retry(selected)">批量重试</el-button>
    </template>
    <template #toolbar-right><span v-if="!workerEnabled" class="pms-status warning">后台执行器未启用</span></template>
    <template #filters>
      <PmsQueryWorkspace entry-mode="document" v-model="queryDraft" list-key="system-sync-task" :fields="queryFields" :defaults="queryDefaults" :ready="querySupported" :loading="loading" :snapshot="() => ({pageSize})" @query="runQuery" @clear-columns="clearQueryColumns" />
      <p v-if="!querySupported" role="status">同步任务接口尚未声明查询 v2 支持，统一查询暂不可用；未执行当前页过滤。</p>
    </template>
    <template #grid>
      <el-table v-loading="loading" :data="visibleItems" class="pms-dense-table" height="100%" border stripe @selection-change="selected = $event">
        <el-table-column v-if="canRetry" type="selection" width="42" :selectable="(row: any) => row.status === 'failed'" />
        <el-table-column prop="project_code" label="项目编号" width="145" fixed :class-name="queryColumnClass('project_code')" :label-class-name="queryColumnClass('project_code')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'project_code',displayName:'项目编号'}" /><span v-else>项目编号</span></template></el-table-column>
        <el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip :class-name="queryColumnClass('project_name')" :label-class-name="queryColumnClass('project_name')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'project_name',displayName:'项目名称'}" /><span v-else>项目名称</span></template></el-table-column>
        <el-table-column prop="status_label" label="同步状态" width="145" :class-name="queryColumnClass('status')" :label-class-name="queryColumnClass('status')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'status',displayName:'同步状态'}" /><span v-else>同步状态</span></template><template #default="{ row }"><span class="pms-status" :class="statusTone(row.status)">{{ row.status_label }}</span></template></el-table-column>
        <el-table-column prop="operator_name" label="保存人" width="110" :class-name="queryColumnClass('operator_name')" :label-class-name="queryColumnClass('operator_name')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'operator_name',displayName:'保存人'}" /><span v-else>保存人</span></template></el-table-column>
        <el-table-column prop="created_at" label="任务时间" width="170" :class-name="queryColumnClass('created_at')" :label-class-name="queryColumnClass('created_at')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'created_at',displayName:'任务时间'}" /><span v-else>任务时间</span></template><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
        <el-table-column prop="attempts" label="尝试次数" width="90" :class-name="queryColumnClass('attempts')" :label-class-name="queryColumnClass('attempts')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'attempts',displayName:'尝试次数'}" /><span v-else>尝试次数</span></template></el-table-column>
        <el-table-column prop="started_at" label="最后执行时间" width="170" :class-name="queryColumnClass('started_at')" :label-class-name="queryColumnClass('started_at')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'started_at',displayName:'最后执行时间'}" /><span v-else>最后执行时间</span></template><template #default="{ row }">{{ formatTime(row.started_at) }}</template></el-table-column>
        <el-table-column prop="message" label="执行结果 / 异常原因" min-width="260" show-overflow-tooltip :class-name="queryColumnClass('message')" :label-class-name="queryColumnClass('message')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'message',displayName:'执行结果 / 异常原因'}" /><span v-else>执行结果 / 异常原因</span></template></el-table-column>
        <el-table-column label="操作" :width="pmsActionColumn(canRetry ? 2 : 1).width" fixed="right">
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
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import PmsQueryColumnHeader from '@/query-system/PmsQueryColumnHeader.vue'
import { useSystemQuery, serverQueryParams, requireServerQueryVersion } from '@/query-system/system-adapter'
import { usePageColumnFilter } from '@/query-system/page-column-filter'
import type { QueryCondition } from '@/query-system/core'
import type { ColumnQueryContext } from '@/query-system/column-filters'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PmsDataList from '@/components/PmsDataList.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import SyncLogDrawer from '@/components/SyncLogDrawer.vue'
import { PmsDateControl, PmsSelectControl, PmsTextControl } from '@/form-system'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, pmsActionColumn } from '@/config/listUi'
import { syncStatusOptions } from '@/config/syncUi'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'
const auth = useAuthStore()
const canRetry = computed(() => auth.hasPermission('system:sync:retry'))
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
const { fields: queryFields, defaults: queryDefaults, draft: queryDraft, applied: queryApplied, submit: submitQuery, clearColumns, columnContext: clientContext, columnFilters, columnClass: queryColumnClass } = useSystemQuery(() => [
  {field:'project_code',label:'项目编号',type:'text'},
  {field:'project_name',label:'项目名称',type:'text'},
  {field:'status',label:'同步状态',type:'enum',options:syncStatusOptions.map(o => ({value:String(o.value),label:o.label}))},
  {field:'operator_name',label:'保存人',type:'text'},
  {field:'created_at',label:'任务时间',type:'date'},
  {field:'attempts',label:'尝试次数',type:'number'},
  {field:'started_at',label:'最后执行时间',type:'date'},
  {field:'message',label:'执行结果 / 异常原因',type:'text'},
], ['project_code','status','operator_name','created_at'], {requireQuery:true,ready:()=>querySupported.value && !loading.value && !error.value})
const querySupported = ref(false)
function clearQueryColumns() { clearColumns() }
function runQuery(conditions: QueryCondition[], preferences: object) {
  if (!querySupported.value) return
  submitQuery(conditions)
  const size = (preferences as {pageSize?:number}).pageSize
  if (size && PAGE_SIZE_OPTIONS.includes(size)) pageSize.value = size
  page.value = 1
}
const items = ref<any[]>([]), selected = ref<any[]>([]), loading = ref(false), busy = ref(false), error = ref('')
const pageColumns = usePageColumnFilter(items, () => queryFields.value, columnFilters, () => [page.value,pageSize.value], undefined, () => clientContext.ready?.() !== false)
const columnContext: ColumnQueryContext = pageColumns.context
const visibleItems = pageColumns.visibleRows
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
    const data: any = await request.get('/sync-tasks', { params: { ...serverQueryParams(queryApplied.value,[]), page: page.value, page_size: pageSize.value } })
    if (current !== serial) return
    querySupported.value = requireServerQueryVersion(data, !!queryApplied.value.length || !!columnFilters.value.length)
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
watch([queryApplied, pageSize], () => { page.value = 1; pageColumns.clear(); loading.value = true }, { deep: true, flush: 'sync' })
watch([queryApplied, page, pageSize], () => { ++serial; clearTimeout(timer); timer = setTimeout(fetchTasks, 200) }, { deep: true })
onMounted(() => { void fetchTasks(); poll = setInterval(() => { if (!busy.value && !loading.value && !selected.value.length && !logVisible.value) void fetchTasks() }, 15000) })
onUnmounted(() => { ++serial; clearTimeout(timer); clearInterval(poll) })
</script>

<style scoped>
.sync-filter { width: 190px; max-width: 100%; }
.sync-filter--date { width: 280px; }
</style>
