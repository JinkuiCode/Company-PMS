<template>
  <PmsDataList
    ref="progressListRef"
    class="project-progress-page"
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
      <el-button type="primary" size="small" @click="addTask">新增任务</el-button>
    </template>
    <template #toolbar-right>
      <span class="filter-count" v-if="filteredRowData.length !== rowData.length">
        已筛选 {{ filteredRowData.length }} / {{ rowData.length }} 条
      </span>
      <span class="hint">双击进度、负责人、日期列可直接修改，修改后自动保存</span>
    </template>

    <template #filters>
      <PmsListFilters
        v-model:filters="customFilters"
        :fields="taskFilterFields"
        :active-count="activeCustomFilterCount"
      >
        <el-input
          v-model="filterKeyword"
          placeholder="搜索任务名称"
          size="small"
          clearable
          style="width: 200px;"
          :prefix-icon="Search"
        />
        <el-select
          v-model="filterAssignee"
          placeholder="全部负责人"
          size="small"
          clearable
          filterable
          style="width: 150px;"
        >
          <el-option v-for="name in userOptions" :key="name" :label="name" :value="name" />
        </el-select>
        <el-select
          v-model="filterStatus"
          placeholder="全部状态"
          size="small"
          clearable
          style="width: 130px;"
        >
          <el-option v-for="item in taskStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </PmsListFilters>
    </template>

    <template #grid>
      <ag-grid-vue
        class="ag-theme-alpine wechat-table pms-ag-grid"
        :rowData="filteredRowData"
        :columnDefs="columnDefs"
        :defaultColDef="defaultColDef"
        :localeText="localeText"
        :theme="'legacy'"
        :domLayout="'autoHeight'"
        :enableCellTextSelection="true"
        :alwaysShowHorizontalScroll="true"
        @cell-value-changed="onCellValueChanged"
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
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Search } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef, type CellValueChangedEvent } from 'ag-grid-community'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import { type ListFilterField, type ListFilterOption, useListFilters } from '@/composables/useListFilters'
import { chineseLocaleText } from '@/utils/agGridLocale'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'

const route = useRoute()
const projectId = Number(route.params.id)
const projectName = route.query.name as string || '项目'
const localeText = chineseLocaleText

const rowData = ref<any[]>([])
const userOptions = ref<string[]>([])  // 负责人姓名列表
const userMap = ref<Record<string, number>>({})  // 姓名 -> ID 映射
const progressListRef = ref<InstanceType<typeof PmsDataList>>()
const filterKeyword = ref('')
const filterAssignee = ref<string | null>(null)
const filterStatus = ref<number | null>(null)

const taskStatusOptions: ListFilterOption[] = [
  { label: '未开始', value: 1 },
  { label: '进行中', value: 2 },
  { label: '已完成', value: 3 },
]

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

const assigneeFilterOptions = computed(() => userOptions.value.map(name => ({
  label: name,
  value: name,
})))

const taskFilterFields = computed<ListFilterField<any>[]>(() => [
  { field: 'task_name', label: '任务名称', type: 'text' },
  { field: 'assignee_name', label: '负责人', type: 'select', options: () => assigneeFilterOptions.value },
  { field: 'status', label: '状态', type: 'select', options: () => taskStatusOptions },
  { field: 'progress', label: '进度', type: 'number' },
  { field: 'sort', label: '排序', type: 'number' },
  { field: 'start_date', label: '开始日期', type: 'date' },
  { field: 'due_date', label: '截止日期', type: 'date' },
])

const { customFilters, activeCustomFilterCount, applyCustomFilters } = useListFilters(taskFilterFields)

const filteredRowData = computed(() => {
  let result = rowData.value
  if (filterKeyword.value) {
    const kw = filterKeyword.value.toLowerCase()
    result = result.filter(row => String(row.task_name ?? '').toLowerCase().includes(kw))
  }
  if (filterAssignee.value) {
    result = result.filter(row => row.assignee_name === filterAssignee.value)
  }
  if (filterStatus.value != null) {
    result = result.filter(row => row.status === filterStatus.value)
  }
  return applyCustomFilters(result)
})

const columnDefs: ColDef[] = [
  { field: 'sort', headerName: '排序', width: 70, editable: true, type: 'numericColumn' },
  { field: 'task_name', headerName: '任务名称', width: 260, editable: true, pinned: 'left' },
  {
    field: 'assignee_name', headerName: '负责人', width: 120, editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({ values: userOptions.value }),
  },
  {
    field: 'progress', headerName: '进度%', width: 140, editable: true,
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
    field: 'status', headerName: '状态', width: 100, editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: { values: ['未开始', '进行中', '已完成'] },
    cellRenderer: (params: any) => {
      const map: Record<number, string> = { 1: '未开始', 2: '进行中', 3: '已完成' }
      const tones: Record<number, string> = { 1: 'neutral', 2: 'info', 3: 'success' }
      const tone = tones[params.value] || 'neutral'
      return `<span class="pms-status pms-status-${tone}"><span class="pms-status-dot"></span>${map[params.value] || '-'}</span>`
    },
  },
  {
    field: 'start_date', headerName: '开始日期', width: 130, editable: true,
    cellEditor: 'agTextCellEditor',
  },
  {
    field: 'due_date', headerName: '截止日期', width: 130, editable: true,
    cellEditor: 'agTextCellEditor',
  },
  {
    headerName: '操作', width: 80, pinned: 'right',
    cellRenderer: (params: any) => `<button class="pms-table-action pms-link-danger del-btn" data-id="${params.data.id}">删除</button>`,
    onCellClicked: (params: any) => {
      if (params.event.target.classList.contains('del-btn')) {
        handleDeleteTask(params.data.id)
      }
    },
  },
]

const defaultColDef = {
  sortable: true, resizable: true,
  cellStyle: { display: 'flex', alignItems: 'center' },
}

async function fetchTasks() {
  rowData.value = (await request.get(`/projects/${projectId}/tasks`)) as any
  refreshProgressScrollbar()
}

async function fetchUsers() {
  const res: any = await request.get('/users', { params: { page: 1, page_size: 999 } })
  userOptions.value = res.items.map((u: any) => u.real_name)
  userMap.value = {}
  res.items.forEach((u: any) => { userMap.value[u.real_name] = u.id })
}

async function onCellValueChanged(event: CellValueChangedEvent) {
  const field = event.colDef.field!
  const value = event.newValue
  const taskId = event.data.id

  // 状态：中文 → 数字映射
  if (field === 'status') {
    const map: Record<string, number> = { '未开始': 1, '进行中': 2, '已完成': 3 }
    await request.put(`/projects/${projectId}/tasks/${taskId}`, { status: map[value] || 1 })
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
  const sort = rowData.value.length + 1
  await request.post(`/projects/${projectId}/tasks`, {
    project_id: projectId, task_name: '新任务', progress: 0, status: 1, sort,
  })
  ElMessage.success('任务已添加')
  fetchTasks()
}

async function handleDeleteTask(taskId: number) {
  await request.delete(`/projects/${projectId}/tasks/${taskId}`)
  ElMessage.success('已删除')
  fetchTasks()
}

function refreshProgressScrollbar() {
  progressListRef.value?.refreshScrollbar()
}

onMounted(() => { fetchTasks(); fetchUsers() })
</script>

<style scoped>
.project-progress-page {
  min-height: 100%;
}

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
