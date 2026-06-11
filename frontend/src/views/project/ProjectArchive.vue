<template>
  <div class="project-archive-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" size="small" @click="openCreateDialog">
          <el-icon style="margin-right:4px;"><Plus /></el-icon>
          新增档案
        </el-button>
        <el-button type="danger" size="small" plain :disabled="selectedRows.length === 0" @click="handleBatchDelete">
          <el-icon style="margin-right:4px;"><Delete /></el-icon>
          批量删除
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
        <el-button type="success" size="small" :disabled="selectedRows.length === 0" @click="handleBatchSync">
          <el-icon style="margin-right:4px;"><Connection /></el-icon>
          批量同步 ERP
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
      </div>
      <div class="toolbar-right">
        <span class="filter-count" v-if="filteredRowData.length !== rowData.length">
          已筛选 {{ filteredRowData.length }} / {{ total }} 条
        </span>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索编号或名称"
        size="small"
        clearable
        style="width: 200px;"
        :prefix-icon="Search"
      />
      <el-select
        v-model="filterProductLine"
        placeholder="全部产品线"
        size="small"
        clearable
        style="width: 140px;"
      >
        <el-option label="Bench" value="Bench" />
        <el-option label="光伏" value="光伏" />
        <el-option label="Single" value="Single" />
        <el-option label="HOTSPM" value="HOTSPM" />
      </el-select>
      <el-select
        v-model="filterStatus"
        placeholder="全部状态"
        size="small"
        clearable
        style="width: 120px;"
      >
        <el-option label="未启动" :value="1" />
        <el-option label="进行中" :value="2" />
        <el-option label="已完结" :value="3" />
        <el-option label="暂停" :value="4" />
      </el-select>
    </div>

    <!-- AG Grid 表格 -->
    <ag-grid-vue
      ref="agGridRef"
      class="ag-theme-alpine wechat-table"
      :rowData="filteredRowData"
      :columnDefs="columnDefs"
      :defaultColDef="defaultColDef"
      :localeText="localeText"
      :domLayout="'autoHeight'"
      :pagination="false"
      :rowSelection="'multiple'"
      :enableCellTextSelection="true"
      @row-double-clicked="onRowDoubleClicked"
      @selection-changed="onSelectionChanged"
      style="width: 100%;"
    />

    <!-- 自定义分页 -->
    <CustomPagination
      v-if="total > 0"
      v-model="page"
      v-model:page-size="pageSize"
      :total="total"
      @update:model-value="fetchList"
      @update:page-size="() => { page = 1; fetchList() }"
    />


    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑项目档案' : '新增项目档案'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="项目编号" prop="project_code">
          <el-input v-model="form.project_code" placeholder="请输入项目编号" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="项目名称" prop="project_name">
          <el-input v-model="form.project_name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="产品线" prop="product_line">
          <el-select v-model="form.product_line" placeholder="请选择产品线" style="width: 100%;">
            <el-option label="Bench" value="Bench" />
            <el-option label="光伏" value="光伏" />
            <el-option label="Single" value="Single" />
            <el-option label="HOTSPM" value="HOTSPM" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" style="width: 100%;">
            <el-option label="未启动" :value="1" />
            <el-option label="进行中" :value="2" />
            <el-option label="已完结" :value="3" />
            <el-option label="暂停" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.manager_id" placeholder="请选择负责人" clearable style="width: 100%;">
            <el-option
              v-for="u in userList"
              :key="u.id"
              :label="u.real_name + ' (' + u.username + ')'"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="产品类型">
          <el-input v-model="form.product_type" placeholder="如：软件、硬件、服务、咨询" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="计划开始" prop="plan_start_date">
              <el-date-picker v-model="form.plan_start_date" type="date" style="width: 100%;" value-format="YYYY-MM-DD" placeholder="选择日期" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划结束" prop="plan_end_date">
              <el-date-picker v-model="form.plan_end_date" type="date" style="width: 100%;" value-format="YYYY-MM-DD" placeholder="选择日期" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Delete, Search, Connection } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef } from 'ag-grid-community'
import CustomPagination from '@/components/CustomPagination.vue'
import { chineseLocaleText } from '@/utils/agGridLocale'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'

const localeText = chineseLocaleText

// ========== 数据状态 ==========
const rowData = ref<any[]>([])
const userList = ref<any[]>([])
const total = ref(0)
const searchKeyword = ref('')
const selectedRows = ref<any[]>([])
const agGridRef = ref()
const page = ref(1)
const pageSize = ref(15)
const filterStatus = ref<number | null>(null)
const filterProductLine = ref<string | null>(null)

// 客户端筛选
const filteredRowData = computed(() => {
  let result = rowData.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(r =>
      r.project_code?.toLowerCase().includes(kw) ||
      r.project_name?.toLowerCase().includes(kw)
    )
  }
  if (filterStatus.value != null) {
    result = result.filter(r => r.status === filterStatus.value)
  }
  if (filterProductLine.value) {
    result = result.filter(r => r.product_line === filterProductLine.value)
  }
  return result
})

// ========== 弹窗 ==========
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  id: 0,
  project_code: '',
  project_name: '',
  status: 1,
  manager_id: null as number | null,
  product_type: '',
  product_line: '',
  plan_start_date: '',
  plan_end_date: '',
})

const rules: FormRules = {
  project_code: [{ required: true, message: '请输入项目编号' }],
  project_name: [{ required: true, message: '请输入项目名称' }],
  product_line: [{ required: true, message: '请选择产品线' }],
  plan_start_date: [{ required: true, message: '请选择计划开始日期' }],
  plan_end_date: [{ required: true, message: '请选择计划结束日期' }],
}

// ========== AG Grid 列定义 ==========
const statusMap: Record<number, string> = { 1: '未启动', 2: '进行中', 3: '已完结', 4: '暂停' }
const statusColors: Record<number, string> = { 1: '#909399', 2: '#409EFF', 3: '#67C23A', 4: '#E6A23C' }

const columnDefs: ColDef[] = [
  { headerCheckboxSelection: true, checkboxSelection: true, width: 42, pinned: 'left', filter: false, sortable: false, resizable: false },
  { field: 'project_code', headerName: '项目编号', width: 130, pinned: 'left' },
  { field: 'project_name', headerName: '项目名称', width: 180 },
  { field: 'product_line', headerName: '产品线', width: 100 },
  {
    field: 'status', headerName: '状态', width: 90,
    cellRenderer: (params: any) => {
      const v = params.value
      const c = statusColors[v] || '#909399'
      return `<span style="display:inline-block;padding:2px 10px;border-radius:12px;
        background:${c}1a;color:${c};font-size:13px;font-weight:500;">
        ${statusMap[v] || '-'}</span>`
    },
  },
  { field: 'manager_name', headerName: '负责人', width: 90 },
  { field: 'product_type', headerName: '产品类型', width: 100 },
  {
    field: 'plan_start_date', headerName: '计划开始', width: 110,
    valueFormatter: (params: any) => params.value ? params.value.substring(0, 10) : '-',
  },
  {
    field: 'plan_end_date', headerName: '计划结束', width: 110,
    valueFormatter: (params: any) => params.value ? params.value.substring(0, 10) : '-',
  },
  { field: 'created_by_name', headerName: '创建人', width: 80 },
  { field: 'updated_by_name', headerName: '最后编辑人', width: 100 },
  {
    field: 'updated_at', headerName: '最后编辑时间', width: 160,
    valueFormatter: (params: any) => params.value ? new Date(params.value).toLocaleString('zh-CN') : '-',
  },
  {
    field: 'erp_sync_status', headerName: '同步', width: 80,
    cellRenderer: (params: any) => {
      const v = params.value
      if (!v || v === 'pending') return `<span style="color:#E6A23C;">⏳</span>`
      if (v === 'success') return `<span style="color:#67C23A;">✅</span>`
      if (v === 'failed') return `<span style="color:#F56C6C;" title="${params.data.erp_error_msg || ''}">❌</span>`
      return '-'
    },
  },
  {
    headerName: '操作', width: 140, pinned: 'right', filter: false, sortable: false, resizable: false,
    cellRenderer: (params: any) => {
      return `<button class="edit-btn" data-id="${params.data.id}">编辑</button>
              <button class="sync-btn" data-id="${params.data.id}">同步</button>
              <button class="del-btn" data-id="${params.data.id}">删除</button>`
    },
    onCellClicked: (params: any) => {
      if (params.event.target.classList.contains('edit-btn')) {
        openEditDialog(params.data)
      } else if (params.event.target.classList.contains('sync-btn')) {
        handleSyncSingle(params.data.id)
      } else if (params.event.target.classList.contains('del-btn')) {
        handleDeleteSingle(params.data.id)
      }
    },
  },
]

const defaultColDef = {
  sortable: true,
  resizable: true,
  filter: false,
}

// ========== 数据加载 ==========
async function fetchList() {
  const res: any = await request.get('/projects/archives/list', {
    params: { page: 1, page_size: 1000 },
  })
  rowData.value = res.items
  total.value = res.total
}

async function fetchUsers() {
  const res: any = await request.get('/users', { params: { page: 1, page_size: 1000 } })
  userList.value = res.items
}

// ========== 选择事件 ==========
function onSelectionChanged() {
  selectedRows.value = agGridRef.value?.api?.getSelectedRows?.() || []
}

// ========== 双击编辑 ==========
function onRowDoubleClicked(event: any) {
  if (event.data) openEditDialog(event.data)
}

// ========== 弹窗操作 ==========
function openCreateDialog() {
  formRef.value?.resetFields()
  Object.assign(form, { id: 0, project_code: '', project_name: '', status: 1, manager_id: null, product_type: '', product_line: '', plan_start_date: '', plan_end_date: '' })
  isEdit.value = false
  dialogVisible.value = true
}

function openEditDialog(row: any) {
  formRef.value?.resetFields()
  Object.assign(form, {
    id: row.id,
    project_code: row.project_code,
    project_name: row.project_name,
    status: row.status,
    manager_id: row.manager_id,
    product_type: row.product_type || '',
    product_line: row.product_line || '',
    plan_start_date: row.plan_start_date ? row.plan_start_date.substring(0, 10) : '',
    plan_end_date: row.plan_end_date ? row.plan_end_date.substring(0, 10) : '',
  })
  isEdit.value = true
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const payload = {
    project_name: form.project_name,
    status: form.status,
    manager_id: form.manager_id,
    product_type: form.product_type || null,
    product_line: form.product_line || null,
    plan_start_date: form.plan_start_date || null,
    plan_end_date: form.plan_end_date || null,
  }

  if (isEdit.value) {
    await request.put(`/projects/archives/${form.id}`, payload)
    ElMessage.success('更新成功')
  } else {
    await request.post('/projects/archives', { ...payload, project_code: form.project_code })
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}

// ========== 删除 ==========
async function handleDeleteSingle(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该项目档案吗？', '提示', { type: 'warning' })
  } catch {
    return
  }
  await request.delete(`/projects/archives/${id}`)
  ElMessage.success('删除成功')
  fetchList()
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedRows.value.length} 条档案吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  for (const row of selectedRows.value) {
    await request.delete(`/projects/archives/${row.id}`)
  }
  ElMessage.success('批量删除成功')
  selectedRows.value = []
  fetchList()
}

// ========== ERP 同步 ==========
async function handleSyncSingle(id: number) {
  try {
    const res: any = await request.post('/erp/sync', { archive_id: id })
    if (res.success) {
      ElMessage.success(res.message)
    } else {
      ElMessage.error(res.message)
    }
    fetchList()
  } catch (e: any) {
    ElMessage.error('同步失败: ' + (e?.response?.data?.message || e?.message))
  }
}

async function handleBatchSync() {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定同步选中的 ${selectedRows.value.length} 条档案到金蝶 ERP 吗？`, '同步确认', { type: 'warning' })
  } catch {
    return
  }
  const ids = selectedRows.value.map((r: any) => r.id)
  try {
    const res: any = await request.post('/erp/sync/batch', { archive_ids: ids })
    if (res.success) {
      ElMessage.success(res.message)
    } else {
      ElMessage.error(res.message)
    }
    selectedRows.value = []
    fetchList()
  } catch (e: any) {
    ElMessage.error('批量同步失败: ' + (e?.response?.data?.message || e?.message))
  }
}

onMounted(() => { fetchList(); fetchUsers() })
</script>

<style scoped>
.project-archive-page {
  background: #fff;
  border-radius: 4px;
  padding: 16px;
}

/* 工具栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 0 12px 0;
}
.toolbar-left { display: flex; align-items: center; gap: 8px; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.filter-count { font-size: 13px; color: #909399; }

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #F3F4F6;
  margin-bottom: 12px;
}

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

/* 操作按钮 */
:deep(.edit-btn) {
  background: none; border: none; cursor: pointer; color: #409EFF;
  font-size: 13px; padding: 2px 6px; margin-right: 4px;
}
:deep(.edit-btn:hover) { text-decoration: underline; }
:deep(.sync-btn) {
  background: none; border: none; cursor: pointer; color: #67C23A;
  font-size: 13px; padding: 2px 6px; margin-right: 4px;
}
:deep(.sync-btn:hover) { text-decoration: underline; }
:deep(.del-btn) {
  background: none; border: none; cursor: pointer; color: #F56C6C;
  font-size: 13px; padding: 2px 6px;
}
:deep(.del-btn:hover) { text-decoration: underline; }
</style>
