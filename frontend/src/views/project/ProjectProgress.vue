<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="page-header">
          <div class="header-left">
            <el-button @click="$router.back()" :icon="Back" size="small">返回</el-button>
            <span class="proj-name">{{ projectName }}</span>
          </div>
          <div class="header-right">
            <span style="color: #606266; margin-right: 8px;">总进度:</span>
            <el-progress :percentage="totalProgress" :color="progressColor(totalProgress)" style="width: 200px;" />
          </div>
        </div>
      </template>

      <div class="toolbar">
        <el-button type="primary" size="small" @click="addTask">新增任务</el-button>
        <span class="hint">双击进度、负责人、日期列可直接修改，修改后自动保存</span>
      </div>

      <ag-grid-vue
        class="ag-theme-alpine wechat-table"
        :rowData="rowData"
        :columnDefs="columnDefs"
        :defaultColDef="defaultColDef"
        :domLayout="'autoHeight'"
        @cell-value-changed="onCellValueChanged"
        style="width: 100%;"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef, type CellValueChangedEvent } from 'ag-grid-community'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'

const route = useRoute()
const projectId = Number(route.params.id)
const projectName = route.query.name as string || '项目'

const rowData = ref<any[]>([])
const userOptions = ref<string[]>([])  // 负责人姓名列表
const userMap = ref<Record<string, number>>({})  // 姓名 -> ID 映射

const totalProgress = computed(() => {
  if (rowData.value.length === 0) return 0
  const sum = rowData.value.reduce((acc, row) => acc + (row.progress || 0), 0)
  return Math.round(sum / rowData.value.length)
})

function progressColor(v: number) { return v < 30 ? '#F56C6C' : v < 80 ? '#E6A23C' : '#67C23A' }

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
      const c = progressColor(v)
      return `<div style="display:flex;align-items:center;gap:8px;">
        <div style="flex:1;height:8px;background:#ebeef5;border-radius:4px;overflow:hidden;">
          <div style="height:100%;width:${v}%;background:${c};border-radius:4px;"></div>
        </div>
        <span>${v}%</span></div>`
    },
    cellEditor: 'agLargeTextCellEditor',
  },
  {
    field: 'status', headerName: '状态', width: 100, editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: { values: ['未开始', '进行中', '已完成'] },
    cellRenderer: (params: any) => {
      const map: Record<number, string> = { 1: '未开始', 2: '进行中', 3: '已完成' }
      const tags: Record<number, string> = { 1: '#909399', 2: '#409EFF', 3: '#67C23A' }
      return `<span style="color:${tags[params.value] || '#909399'};font-weight:500;">${map[params.value] || '-'}</span>`
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
    cellRenderer: (params: any) => `<button class="del-btn" data-id="${params.data.id}">删除</button>`,
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

onMounted(() => { fetchTasks(); fetchUsers() })
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; }
.header-left { display: flex; align-items: center; gap: 12px; }
.proj-name { font-size: 18px; font-weight: bold; color: #303133; }
.toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.hint { color: #909399; font-size: 13px; }
:deep(.del-btn) { background: none; border: none; color: #F56C6C; cursor: pointer; }
:deep(.del-btn:hover) { text-decoration: underline; }

/* ===== AG Grid 企微风格覆盖 ===== */
:deep(.ag-root-wrapper) { border: none; }
:deep(.ag-cell) { border-right: none; border-bottom: none; font-size: 14px; color: #303133; }
:deep(.ag-row) { border-bottom: none; }
:deep(.ag-header) { background-color: #f5f6f7; border-bottom: 1px solid #e8e8e8; }
:deep(.ag-header-cell) { background-color: #f5f6f7; border-right: none; padding: 0 12px; }
:deep(.ag-header-cell-text) { font-weight: 600; font-size: 14px; color: #303133; }
:deep(.ag-row-even) { background-color: #fafbfc; }
:deep(.ag-row-odd) { background-color: #ffffff; }
:deep(.ag-row:hover) { background-color: #e8f4fd; }
:deep(.ag-row-selected) { background-color: inherit; }
</style>
