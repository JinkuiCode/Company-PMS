<template>
  <PmsDataList
    ref="progressListRef"
    class="project-progress-page"
    :class="{ 'is-history-open': historyTask }"
    scrollbar-label="项目进度任务表横向滚动条"
  >
    <template #header>
      <div class="page-header">
        <div class="header-left">
          <el-button @click="$router.back()" :icon="Back" size="small">返回</el-button>
          <span class="proj-name">{{ projectName }}</span>
        </div>
        <div class="header-right progress-summary">
          <span class="progress-label">总进度</span>
          <el-progress class="header-progress" :percentage="totalProgress" :color="progressColor(totalProgress)" />
        </div>
      </div>
    </template>

    <template #toolbar-left>
      <el-button v-if="hasPermission('project:list:add')" type="primary" size="small" @click="addTask">新增任务</el-button>
    </template>
    <template #toolbar-right>
      <PmsPageGuide page="tasks" />
      <BusinessExportControl :resource="{kind:'tasks',projectId}" :snapshot="exportSnapshot" :disabled="!columnContext.ready?.()" />
      <span class="filter-count" v-if="filteredRowData.length !== rowData.length">
        已筛选 {{ filteredRowData.length }} / {{ rowData.length }} 条
      </span>
      <span class="hint">双击进度、负责人、日期列可直接修改，修改后自动保存</span>
    </template>

    <template #filters>
      <PmsQueryWorkspace entry-mode="document" v-model="queryDraft" :list-key="`project-tasks-${projectId}`" :fields="queryFields" :defaults="queryDefaults" :loading="tasksLoading" @query="submitQuery" @clear-columns="clearQueryColumns" />
    </template>

    <template #grid>
      <ag-grid-vue
        class="ag-theme-alpine wechat-table pms-ag-grid"
        :class="PMS_AG_GRID_FORM_CLASS"
        :rowData="filteredRowData"
        :columnDefs="queryColumnDefs"
        @grid-ready="gridApi = $event.api"
        :defaultColDef="defaultColDef"
        :localeText="localeText"
        :theme="'legacy'"
        :domLayout="'normal'"
        :enableCellTextSelection="true"
        :alwaysShowHorizontalScroll="true"
        @cell-value-changed="onCellValueChanged"
        @row-clicked="onTaskRowClicked"
        @first-data-rendered="refreshProgressScrollbar"
        @grid-size-changed="refreshProgressScrollbar"
        @column-resized="refreshProgressScrollbar"
        @column-moved="refreshProgressScrollbar"
        @column-pinned="refreshProgressScrollbar"
        @displayed-columns-changed="refreshProgressScrollbar"
        style="width: 100%;"
      />
    </template>
  </PmsDataList>
  <PmsFormDrawer v-if="historyTask" :model-value="true" :title="`${historyTask.task_name} · 操作记录`" penetrable @update:model-value="closeTaskHistory"><PmsDocumentHistory resource="task" :entity-id="historyTask.id" :revision="taskHistoryRevision" /><template #footer><el-button class="pms-button-reset" @click="closeTaskHistory">关闭</el-button></template></PmsFormDrawer>
</template>

<script setup lang="ts">
import BusinessExportControl from '@/business-export/BusinessExportControl.vue'
import { businessExportSnapshot } from '@/business-export/snapshot'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import { useSystemQuery } from '@/query-system/system-adapter'
import { toQueryFields } from '@/query-system/list-adapter'
import { decorateQueryColumns } from '@/query-system/column-grid'
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { createDetailSwitch } from '@/utils/detailSwitch'
import { pmsActionColumn } from '@/config/listUi'
import { PmsFormDrawer } from '@/form-system'
import PmsDocumentHistory from '@/document-history/PmsDocumentHistory.vue'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Search } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef, type CellValueChangedEvent } from 'ag-grid-community'
import PmsDataList from '@/components/PmsDataList.vue'
import {
  PMS_AG_GRID_FORM_CLASS,
  PmsSelectControl,
  PmsTextControl,
  mergePmsAgCellClass,
} from '@/form-system'
import { type ListFilterField, type ListFilterOption } from '@/composables/useListFilters'
import { loadEnumOptions } from '@/composables/useEnumOptions'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'

const route = useRoute()
const historyTask = ref<{ id: number; task_name: string } | null>(null)
const taskHistoryRevision = ref(0)
const taskHistorySwitch = createDetailSwitch<{ id: number; task_name: string }>(async () => true, async (row, current) => {
  if (current()) historyTask.value = row
})
function closeTaskHistory() { taskHistorySwitch.invalidate(); historyTask.value = null }
function onTaskRowClicked(event: any) { if (historyTask.value && event.data) void taskHistorySwitch.select(event.data) }
const projectId = Number(route.params.id)
const projectName = route.query.name as string || '项目'
const localeText = chineseLocaleText
const authStore = useAuthStore()
const hasPermission = authStore.hasPermission

const rowData = ref<any[]>([])
const userOptions = ref<string[]>([])  // 负责人姓名列表
const userMap = ref<Record<string, number>>({})  // 姓名 -> ID 映射
const progressListRef = ref<InstanceType<typeof PmsDataList>>()
const filterKeyword = ref('')
const filterAssignee = ref<string | null>(null)
const filterStatus = ref<number | null>(null)

const taskStatusOptions = ref<ListFilterOption[]>([])
const taskStatusLabelMap = ref<Record<string, string>>({})

const totalProgress = computed(() => {
  if (rowData.value.length === 0) return 0
  const sum = rowData.value.reduce((acc, row) => acc + (row.progress || 0), 0)
  return Math.round(sum / rowData.value.length)
})

function progressColor(v: number) { return v < 30 ? '#dc2626' : v < 80 ? '#d97706' : '#0f9f7a' }
function progressToneClass(v: number) {
  if (v < 30) return 'is-danger'
  if (v < 80) return 'is-warning'
  return 'is-success'
}
function escapeHtml(value: unknown) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const assigneeFilterOptions = computed(() => userOptions.value.map(name => ({
  label: name,
  value: name,
})))

const taskFilterFields = computed<ListFilterField<any>[]>(() => [
  { field: 'task_name', label: '任务名称', type: 'text' },
  { field: 'assignee_name', label: '负责人', type: 'select', options: () => assigneeFilterOptions.value },
  { field: 'status', label: '状态', type: 'select', options: () => Object.entries(taskStatusLabelMap.value).map(([value,label]) => ({value:Number(value),label})) },
  { field: 'progress', label: '进度', type: 'number' },
  { field: 'sort', label: '排序', type: 'number' },
  { field: 'start_date', label: '开始日期', type: 'date' },
  { field: 'due_date', label: '截止日期', type: 'date' },
])

const gridApi = ref<any>(null)
const tasksLoading = ref(true), tasksAccepted = ref(false)
const { fields: queryFields, defaults: queryDefaults, draft: queryDraft, applied: queryApplied, columnFilters, submit: submitQuery, filterRows, clearColumns, columnContext } = useSystemQuery(() => toQueryFields(taskFilterFields.value), ['task_name', 'assignee_name', 'status'], {requireQuery:true,ready:()=>tasksAccepted.value && !tasksLoading.value})
const filteredRowData = computed(() => filterRows(rowData.value))
const queryColumnDefs = computed(() => decorateQueryColumns(columnDefs.value, () => columnContext))
columnContext.sort = (field, direction) => gridApi.value?.applyColumnState({state:[{colId:field,sort:direction}],defaultState:{sort:null}})
function clearQueryColumns() { clearColumns(); gridApi.value?.setFilterModel(null); gridApi.value?.refreshCells({force:true}) }
function exportSnapshot() { return businessExportSnapshot(queryApplied.value, [], gridApi.value) }

const columnDefs = computed<ColDef[]>(() => ([
  { field: 'sort', headerName: '排序', width: 70, editable: () => hasPermission('project:list:edit'), type: 'numericColumn' },
  { field: 'task_name', headerName: '任务名称', width: 260, editable: () => hasPermission('project:list:edit'), pinned: 'left' },
  {
    field: 'assignee_name', headerName: '负责人', width: 120, editable: () => hasPermission('project:list:edit'),
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({ values: userOptions.value }),
  },
  {
    field: 'progress', headerName: '进度%', width: 140, editable: () => hasPermission('project:list:edit'),
    cellRenderer: (params: any) => {
      const v = params.value || 0
      const tone = progressToneClass(v)
      return `<div class="pms-progress-cell">
        <div class="pms-progress-track">
          <div class="pms-progress-bar ${tone}" style="width:${v}%;"></div>
        </div>
        <span class="pms-progress-value">${v}%</span></div>`
    },
    cellEditor: 'agLargeTextCellEditor',
  },
  {
    field: 'status', headerName: '状态', width: 100, editable: () => hasPermission('project:list:edit'),
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({ values: taskStatusOptions.value.map(item => item.value) }),
    valueFormatter: (params: any) => taskStatusLabelMap.value[String(params.value)] || '-',
    cellRenderer: (params: any) => {
      const tones: Record<number, string> = { 1: 'neutral', 2: 'info', 3: 'success' }
      const tone = tones[params.value] || 'neutral'
      const label = escapeHtml(taskStatusLabelMap.value[String(params.value)] || '-')
      return `<span class="pms-status pms-status-${tone}"><span class="pms-status-dot"></span>${label}</span>`
    },
  },
  {
    field: 'start_date', headerName: '开始日期', width: 130, editable: () => hasPermission('project:list:edit'),
    cellEditor: 'agTextCellEditor',
  },
  {
    field: 'due_date', headerName: '截止日期', width: 130, editable: () => hasPermission('project:list:edit'),
    cellEditor: 'agTextCellEditor',
  },
  {
    headerName: '操作', ...pmsActionColumn(hasPermission('project:list:delete') ? 2 : 1), pinned: 'right',
    cellRenderer: () => `<button class="pms-table-action pms-link-navigation history-btn">记录</button>` + (hasPermission('project:list:delete')
      ? `<button class="pms-table-action pms-link-danger del-btn">删除</button>` : ''),
    onCellClicked: (params: any) => {
      if (params.event.target.classList.contains('del-btn')) {
        handleDeleteTask(params.data.id)
      }
      if (params.event.target.classList.contains('history-btn')) void taskHistorySwitch.select(params.data)
    },
  },
] as ColDef[]).map(definition => definition.editable ? mergePmsAgCellClass(definition) : definition))

const defaultColDef = {
  sortable: true, resizable: true,
  cellStyle: { display: 'flex', alignItems: 'center' },
}

let taskRequestSerial = 0
async function fetchTasks() {
  const current = ++taskRequestSerial
  tasksLoading.value = true
  try {
    const rows = (await request.get(`/projects/${projectId}/tasks`)) as any[]
    if (current !== taskRequestSerial) return
    rowData.value = rows
    if (historyTask.value) {
      const latest = rows.find(row => row.id === historyTask.value?.id)
      if (latest) { await taskHistorySwitch.select(latest); ++taskHistoryRevision.value }
      else closeTaskHistory()
    }
    tasksAccepted.value = true
    refreshProgressScrollbar()
  } catch (error) {
    if (current !== taskRequestSerial) return
    rowData.value = []; closeTaskHistory()
    tasksAccepted.value = false
    ElMessage.error(error instanceof Error ? error.message : '任务读取失败，请重试')
  } finally { if (current === taskRequestSerial) tasksLoading.value = false }
}

async function fetchUsers() {
  const users: any = await request.get('/users/options')
  userOptions.value = users.map((u: any) => u.real_name)
  userMap.value = {}
  users.forEach((u: any) => { userMap.value[u.real_name] = u.id })
}

async function onCellValueChanged(event: CellValueChangedEvent) {
  if (!hasPermission('project:list:edit')) return
  const field = event.colDef.field!
  const value = event.newValue
  const taskId = event.data.id

  // 状态：中文 → 数字映射
  if (field === 'status') {
    const selected = taskStatusOptions.value.find(item => item.label === value || item.value === value)
    await request.put(`/projects/${projectId}/tasks/${taskId}`, { status: Number(selected?.value ?? value) })
    ElMessage.success('已自动保存')
    fetchTasks()
    return
  }

  // 负责人：姓名 → ID 映射
  if (field === 'assignee_name') {
    const assigneeId = userMap.value[value] || null
    await request.put(`/projects/${projectId}/tasks/${taskId}`, { assignee_id: assigneeId })
    ElMessage.success('已自动保存')
    fetchTasks()
    return
  }

  await request.put(`/projects/${projectId}/tasks/${taskId}`, { [field]: value })
  ElMessage.success('已自动保存')
  fetchTasks()
}

async function addTask() {
  if (!hasPermission('project:list:add')) return
  const sort = rowData.value.length + 1
  await request.post(`/projects/${projectId}/tasks`, {
    project_id: projectId, task_name: '新任务', progress: 0, status: 1, sort,
  })
  ElMessage.success('任务已添加')
  fetchTasks()
}

async function handleDeleteTask(taskId: number) {
  if (!hasPermission('project:list:delete')) return
  await request.delete(`/projects/${projectId}/tasks/${taskId}`)
  if (historyTask.value?.id === taskId) closeTaskHistory()
  ElMessage.success('已删除')
  fetchTasks()
}

function refreshProgressScrollbar() {
  progressListRef.value?.refreshScrollbar()
}

async function loadTaskStatusOptions() {
  const definition = await loadEnumOptions('task_status')
  taskStatusOptions.value = definition.items.map(item => ({ label: item.label, value: Number(item.value) }))
  taskStatusLabelMap.value = definition.label_map
}

onMounted(() => { fetchTasks(); fetchUsers(); loadTaskStatusOptions() })
onBeforeUnmount(() => { ++taskRequestSerial; taskHistorySwitch.invalidate() })
</script>

<style scoped>
.project-progress-page {
  min-height: 100%;
  width: 100%;
}
.project-progress-page.is-history-open { width:calc(100% - var(--pms-drawer-width) - var(--pms-query-gap)); }
@media(max-width:760px){.project-progress-page.is-history-open{width:100%}}

.task-base-filter {
  flex: 0 0 auto;
}

.task-base-filter--keyword { width: 200px; }
.task-base-filter--assignee { width: 150px; }
.task-base-filter--status { width: 130px; }

.page-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.header-left { display: flex; align-items: center; gap: 12px; }
.proj-name { font-size: 17px; font-weight: 700; color: var(--pms-text); }
.progress-summary { display: flex; align-items: center; gap: 10px; min-width: 260px; }
.progress-label { color: var(--pms-text-secondary); font-size: 13px; }
.header-progress { width: 200px; }
.hint { color: var(--pms-text-secondary); font-size: 13px; }

@media (max-width: 900px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .progress-summary {
    width: 100%;
    min-width: 0;
  }

  .header-progress {
    flex: 1;
    width: auto;
  }
}
</style>
