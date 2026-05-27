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
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索编号或名称"
          size="small"
          clearable
          style="width: 180px;"
          @input="onSearch"
        />
      </div>
    </div>

    <!-- AG Grid 表格 -->
    <ag-grid-vue
      ref="agGridRef"
      class="ag-theme-alpine wechat-table"
      :rowData="rowData"
      :columnDefs="columnDefs"
      :defaultColDef="defaultColDef"
      :domLayout="'autoHeight'"
      :pagination="false"
      :rowSelection="'multiple'"
      :enableCellTextSelection="true"
      @row-double-clicked="onRowDoubleClicked"
      @selection-changed="onSelectionChanged"
      style="width: 100%;"
    />

    <!-- 自定义分页 -->
    <div class="custom-pagination" v-if="total > 0">
      <div class="pagination-left">
        <span class="pagination-total">{{ total }} total</span>
      </div>
      <div class="pagination-center">
        <button class="page-btn nav-btn" :disabled="page === 1" @click="goPage(page - 1)">‹</button>
        <template v-for="p in visiblePages" :key="p">
          <button v-if="p === -1" class="page-btn ellipsis" disabled>···</button>
          <button v-else class="page-btn" :class="{ active: p === page }" @click="goPage(p)">{{ p }}</button>
        </template>
        <button class="page-btn nav-btn" :disabled="page === totalPages" @click="goPage(page + 1)">›</button>
      </div>
      <div class="pagination-right">
        <select class="page-size-select" v-model="pageSize" @change="onPageSizeChange">
          <option :value="15">15 条/页</option>
          <option :value="20">20 条/页</option>
          <option :value="50">50 条/页</option>
          <option :value="100">100 条/页</option>
        </select>
      </div>
    </div>

    <!-- 新增 / 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑项目档案' : '新增项目档案'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="项目编号" prop="project_code">
          <el-input v-model="form.project_code" placeholder="请输入项目编号" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="项目名称" prop="project_name">
          <el-input v-model="form.project_name" placeholder="请输入项目名称" />
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
import { Plus, Delete } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef } from 'ag-grid-community'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'

// ========== 数据状态 ==========
const rowData = ref<any[]>([])
const userList = ref<any[]>([])
const total = ref(0)
const searchKeyword = ref('')
const selectedRows = ref<any[]>([])
const agGridRef = ref()
const page = ref(1)
const pageSize = ref(15)

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
})

const rules: FormRules = {
  project_code: [{ required: true, message: '请输入项目编号' }],
  project_name: [{ required: true, message: '请输入项目名称' }],
}

// ========== 分页计算 ==========
const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

const visiblePages = computed(() => {
  const pages: number[] = []
  pages.push(1)
  let start = Math.max(2, page.value - 1)
  let end = Math.min(totalPages.value - 1, page.value + 1)
  if (page.value <= 3) { start = 2; end = Math.min(5, totalPages.value - 1) }
  else if (page.value >= totalPages.value - 2) { start = Math.max(totalPages.value - 4, 2); end = totalPages.value - 1 }
  if (start > 2) pages.push(-1)
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < totalPages.value - 1) pages.push(-1)
  if (totalPages.value > 1) pages.push(totalPages.value)
  return [...new Set(pages)]
})

function goPage(p: number) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  fetchList()
}

function onPageSizeChange() {
  page.value = 1
  fetchList()
}

// ========== AG Grid 列定义 ==========
const statusMap: Record<number, string> = { 1: '未启动', 2: '进行中', 3: '已完结', 4: '暂停' }
const statusColors: Record<number, string> = { 1: '#909399', 2: '#409EFF', 3: '#67C23A', 4: '#E6A23C' }

const columnDefs: ColDef[] = [
  { headerCheckboxSelection: true, checkboxSelection: true, width: 42, pinned: 'left', filter: false, sortable: false, resizable: false },
  { field: 'project_code', headerName: '项目编号', width: 150, pinned: 'left' },
  { field: 'project_name', headerName: '项目名称', width: 240 },
  {
    field: 'status', headerName: '状态', width: 100,
    cellRenderer: (params: any) => {
      const v = params.value
      const c = statusColors[v] || '#909399'
      return `<span style="display:inline-block;padding:2px 10px;border-radius:12px;
        background:${c}1a;color:${c};font-size:13px;font-weight:500;">
        ${statusMap[v] || '-'}</span>`
    },
  },
  { field: 'manager_name', headerName: '负责人', width: 110 },
  { field: 'product_type', headerName: '产品类型', width: 120 },
  {
    field: 'created_at', headerName: '创建时间', width: 170,
    valueFormatter: (params: any) => params.value ? new Date(params.value).toLocaleString('zh-CN') : '-',
  },
  {
    headerName: '操作', width: 120, pinned: 'right', filter: false, sortable: false, resizable: false,
    cellRenderer: (params: any) => {
      return `<button class="edit-btn" data-id="${params.data.id}">编辑</button>
              <button class="del-btn" data-id="${params.data.id}">删除</button>`
    },
    onCellClicked: (params: any) => {
      if (params.event.target.classList.contains('edit-btn')) {
        openEditDialog(params.data)
      } else if (params.event.target.classList.contains('del-btn')) {
        handleDeleteSingle(params.data.id)
      }
    },
  },
]

const defaultColDef = {
  sortable: true,
  resizable: true,
  filter: true,
}

// ========== 数据加载 ==========
let searchTimer: ReturnType<typeof setTimeout> | null = null

async function fetchList() {
  const res: any = await request.get('/projects/archives/list', {
    params: { page: 1, page_size: 1000, keyword: searchKeyword.value || undefined },
  })
  rowData.value = res.items
  total.value = res.total
}

async function fetchUsers() {
  const res: any = await request.get('/users', { params: { page: 1, page_size: 1000 } })
  userList.value = res.items
}

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; fetchList() }, 300)
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
  Object.assign(form, { id: 0, project_code: '', project_name: '', status: 1, manager_id: null, product_type: '' })
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
  })
  isEdit.value = true
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (isEdit.value) {
    await request.put(`/projects/archives/${form.id}`, {
      project_name: form.project_name,
      status: form.status,
      manager_id: form.manager_id,
      product_type: form.product_type || null,
    })
    ElMessage.success('更新成功')
  } else {
    await request.post('/projects/archives', {
      project_code: form.project_code,
      project_name: form.project_name,
      status: form.status,
      manager_id: form.manager_id,
      product_type: form.product_type || null,
    })
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

/* ===== 自定义分页 ===== */
.custom-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  margin-top: 16px;
  border-top: 1px solid #F3F4F6;
}
.pagination-left { display: flex; align-items: center; }
.pagination-total { font-size: 14px; color: #374151; font-weight: 500; }
.pagination-center { display: flex; align-items: center; gap: 4px; }
.pagination-right { display: flex; align-items: center; }
.page-btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 32px; height: 32px; padding: 0 8px;
  border: 1px solid #E5E7EB; border-radius: 6px;
  background: #fff; color: #374151; font-size: 14px; font-weight: 400;
  cursor: pointer; transition: all 0.15s; line-height: 1;
}
.page-btn:hover:not(:disabled):not(.active) { background: #F3F4F6; border-color: #D1D5DB; }
.page-btn.active { background: #6366F1; color: #fff; border-color: #6366F1; font-weight: 500; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-btn.ellipsis { border: none; background: transparent; color: #9CA3AF; cursor: default; min-width: 24px; }
.page-btn.nav-btn { font-size: 16px; font-weight: 500; min-width: 28px; }
.page-size-select {
  padding: 6px 28px 6px 12px; border: 1px solid #E5E7EB; border-radius: 6px;
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%236B7280' d='M6 8.825L1.175 4 2.238 2.938 6 6.7l3.763-3.763L10.825 4z'/%3E%3C/svg%3E") no-repeat right 8px center;
  color: #374151; font-size: 14px; cursor: pointer; outline: none; appearance: none;
}
.page-size-select:hover { border-color: #D1D5DB; }

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
:deep(.del-btn) {
  background: none; border: none; cursor: pointer; color: #F56C6C;
  font-size: 13px; padding: 2px 6px;
}
:deep(.del-btn:hover) { text-decoration: underline; }
</style>
