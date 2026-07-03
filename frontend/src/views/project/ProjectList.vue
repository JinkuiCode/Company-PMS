<template>
  <div class="project-list-page pms-page">
    <!-- 工具栏 -->
    <div class="toolbar pms-toolbar">
      <div class="toolbar-left pms-toolbar-left">
        <el-button type="primary" size="small" @click="openCreateDialog">
          <el-icon style="margin-right:4px;"><Plus /></el-icon>
          新增项目
        </el-button>
      </div>
      <div class="toolbar-right pms-toolbar-right">
        <span class="filter-count" v-if="filteredRowData.length !== rowData.length">
          已筛选 {{ filteredRowData.length }} / {{ total }} 条
        </span>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar pms-filter-bar">
      <el-input
        v-model="filterKeyword"
        placeholder="搜索编号或名称"
        size="small"
        clearable
        style="width: 200px;"
        :prefix-icon="Search"
      />
      <el-tree-select
        v-model="filterDeptId"
        :data="deptList"
        :props="{ label: 'dept_name', value: 'id', children: 'children' }"
        check-strictly
        clearable
        placeholder="全部部门"
        size="small"
        style="width: 160px;"
      />
      <el-select
        v-model="filterStatus"
        placeholder="全部状态"
        size="small"
        clearable
        style="width: 140px;"
      >
        <el-option label="进行中" :value="1" />
        <el-option label="已完结" :value="2" />
        <el-option label="暂停" :value="3" />
      </el-select>
      <el-select
        v-model="filterProductLine"
        placeholder="全部产品线"
        size="small"
        clearable
        style="width: 140px;"
      >
        <el-option v-for="item in filteredProductLineOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </div>

    <!-- AG Grid 表格 -->
    <div class="project-list-grid-shell">
      <ag-grid-vue
        class="ag-theme-alpine wechat-table pms-ag-grid"
        :rowData="filteredRowData"
        :columnDefs="columnDefs"
        :defaultColDef="defaultColDef"
        :localeText="localeText"
        :theme="'legacy'"
        :domLayout="'autoHeight'"
        :pagination="false"
        :enableCellTextSelection="true"
        :suppressRowClickSelection="true"
        :alwaysShowHorizontalScroll="true"
        @cell-value-changed="onCellValueChanged"
        @first-data-rendered="refreshListScrollbar"
        @grid-size-changed="refreshListScrollbar"
        @column-resized="refreshListScrollbar"
        @column-moved="refreshListScrollbar"
        @column-pinned="refreshListScrollbar"
        @displayed-columns-changed="refreshListScrollbar"
        style="width: 100%;"
      />
      <GridHorizontalScrollbar ref="listScrollbarRef" label="项目进度列表横向滚动条" />
    </div>

    <!-- 自定义分页 -->
    <CustomPagination
      v-if="total > 0"
      v-model="page"
      v-model:page-size="pageSize"
      :total="total"
      @update:model-value="fetchList"
      @update:page-size="() => { page = 1; fetchList() }"
    />

    <!-- 新增项目弹窗 -->
    <el-dialog v-model="dialogVisible" title="新增项目" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="项目档案" prop="archive_id">
          <el-select
            v-model="form.archive_id"
            filterable
            placeholder="请选择项目档案（自动带出编号和名称）"
            style="width: 100%;"
            @change="onArchiveChange"
          >
            <el-option
              v-for="a in archiveList"
              :key="a.id"
              :label="`${a.project_code} - ${a.project_name}`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目编号">
          <el-input v-model="form.project_code" disabled placeholder="由档案自动带出" />
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="form.project_name" disabled placeholder="由档案自动带出" />
        </el-form-item>
        <el-form-item label="所属部门" prop="dept_id">
          <el-tree-select
            v-model="form.dept_id" style="width: 100%;"
            :data="deptList" :props="{ label: 'dept_name', value: 'id', children: 'children' }"
            check-strictly
          />
        </el-form-item>
        <el-form-item label="项目经理" prop="pm_id">
          <el-select v-model="form.pm_id" style="width: 100%;">
            <el-option v-for="u in userList" :key="u.id" :label="u.real_name + ' (' + u.username + ')'" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="开始日期">
              <el-date-picker v-model="form.start_date" type="date" style="width: 100%;" value-format="YYYY-MM-DD" placeholder="选择日期" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期">
              <el-date-picker v-model="form.end_date" type="date" style="width: 100%;" value-format="YYYY-MM-DD" placeholder="选择日期" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="预算(万)">
          <el-input-number v-model="form.budget" :min="0" :precision="2" style="width: 100%;" placeholder="请输入预算" />
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef, type CellValueChangedEvent } from 'ag-grid-community'
import CustomPagination from '@/components/CustomPagination.vue'
import GridHorizontalScrollbar from '@/components/GridHorizontalScrollbar.vue'
import { chineseLocaleText } from '@/utils/agGridLocale'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'

const router = useRouter()
const localeText = chineseLocaleText

// ========== 数据状态 ==========
const rowData = ref<any[]>([])
const archiveList = ref<any[]>([])  // 项目档案下拉列表
const deptList = ref<any[]>([])       // 部门树（弹窗用）
const deptNames = ref<string[]>([])   // 部门名称列表（下拉编辑器用）
const deptFlatList = ref<any[]>([])   // 扁平部门（名称→ID 映射）
const userList = ref<any[]>([])       // 用户列表
const userNames = ref<string[]>([])   // 用户姓名列表（下拉编辑器用）
const total = ref(0)
const listScrollbarRef = ref<InstanceType<typeof GridHorizontalScrollbar>>()
const page = ref(1)
const pageSize = ref(15)
const filterKeyword = ref('')
const filterStatus = ref<number | null>(null)
const filterDeptId = ref<number | null>(null)
const filterProductLine = ref<string | null>(null)

// 字典选项
const productLineOptions = ref<any[]>([])
const allowedProductLines = ref<string[] | null>(null)

const filteredProductLineOptions = computed(() => {
  const all = productLineOptions.value
  if (allowedProductLines.value === null) return all
  return all.filter((item: any) => allowedProductLines.value!.includes(item.value))
})

// 客户端筛选
const filteredRowData = computed(() => {
  let result = rowData.value
  if (filterKeyword.value) {
    const kw = filterKeyword.value.toLowerCase()
    result = result.filter(r =>
      r.project_code?.toLowerCase().includes(kw) ||
      r.project_name?.toLowerCase().includes(kw)
    )
  }
  if (filterStatus.value != null) {
    result = result.filter(r => r.status === filterStatus.value)
  }
  if (filterDeptId.value != null) {
    result = result.filter(r => r.dept_id === filterDeptId.value)
  }
  if (filterProductLine.value) {
    result = result.filter(r => r.product_line === filterProductLine.value)
  }
  return result
})

// ========== 弹窗 ==========
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  id: 0,
  archive_id: null as number | null,
  project_code: '',
  project_name: '',
  dept_id: 0,
  pm_id: 0,
  status: 1,
  start_date: '',
  end_date: '',
  budget: null as number | null,
})

const rules: FormRules = {
  archive_id: [{ required: true, message: '请选择项目档案' }],
  dept_id: [{ required: true, message: '请选择部门' }],
  pm_id: [{ required: true, message: '请选择项目经理' }],
}

// ========== AG Grid 列定义 ==========
function progressToneClass(v: number) {
  if (v < 30) return 'is-danger'
  if (v < 80) return 'is-warning'
  return 'is-success'
}

function escapeHtml(value: any) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const columnDefs: ColDef[] = [
  { field: 'id', headerName: 'ID', width: 70, filter: false },
  { field: 'project_code', headerName: '项目编号', width: 140, editable: true },
  {
    field: 'project_name', headerName: '项目名称', width: 220, editable: true, pinned: 'left',
    cellRenderer: (params: any) => {
      return `<a class="proj-link" data-id="${params.data.id}" data-name="${escapeHtml(params.data.project_name)}">${escapeHtml(params.value || '-')}</a>`
    },
    onCellClicked: (params: any) => {
      if (params.event.target.classList.contains('proj-link')) {
        goProgress(params.data)
      }
    },
  },
  {
    field: 'dept_name', headerName: '所属部门', width: 130, editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({ values: deptNames.value }),
  },
  {
    field: 'pm_name', headerName: '项目经理', width: 120, editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({ values: userNames.value }),
  },
  {
    field: 'total_progress', headerName: '总进度', width: 160, filter: false,
    cellRenderer: (params: any) => {
      const v = params.value || 0
      const tone = progressToneClass(v)
      return `<div class="pms-progress-cell">
        <div class="pms-progress-track">
          <div class="pms-progress-bar ${tone}" style="width:${v}%;"></div>
        </div>
        <span class="pms-progress-value">${v}%</span></div>`
    },
  },
  {
    field: 'status', headerName: '状态', width: 100, editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: { values: ['进行中', '已完结', '暂停'] },
    cellRenderer: (params: any) => {
      const map: Record<number, string> = { 1: '进行中', 2: '已完结', 3: '暂停' }
      const tones: Record<number, string> = { 1: 'info', 2: 'success', 3: 'warning' }
      const v = params.value
      const tone = tones[v] || 'neutral'
      return `<span class="pms-status pms-status-${tone}"><span class="pms-status-dot"></span>${map[v] || '-'}</span>`
    },
  },
  { field: 'task_count', headerName: '任务数', width: 90 },
  {
    field: 'budget', headerName: '预算(万)', width: 110, editable: true, type: 'numericColumn',
  },
  { field: 'start_date', headerName: '开始日期', width: 120, editable: true },
  { field: 'end_date', headerName: '结束日期', width: 120, editable: true },
  {
    headerName: '', width: 55, pinned: 'right', filter: false, sortable: false, resizable: false,
    cellRenderer: () => `<button class="pms-more-btn more-btn" title="更多操作"></button>`,
    onCellClicked: (params: any) => {
      if (params.event.target.classList.contains('more-btn')) {
        handleRowMenu(params.data)
      }
    },
  },
]

const defaultColDef = {
  sortable: true,
  resizable: true,
  filter: false,
}

function refreshListScrollbar() {
  listScrollbarRef.value?.refresh()
}

// ========== 数据加载 ==========
async function fetchList() {
  const res: any = await request.get('/projects', { params: { page: 1, page_size: 1000 } })
  rowData.value = res.items
  total.value = res.total
  refreshListScrollbar()
}

async function fetchOptions() {
  // 加载项目档案列表
  archiveList.value = (await request.get('/projects/archives/options')) as any

  // 加载产品线字典
  try {
    const dictRes: any = await request.get('/dicts/code/product_line')
    productLineOptions.value = dictRes?.items || []
  } catch { /* ignore */ }

  // 加载用户允许的产品线
  try {
    const plRes: any = await request.get('/auth/product-lines')
    allowedProductLines.value = plRes.unrestricted ? null : (plRes.items || [])
  } catch { /* ignore */ }

  deptList.value = (await request.get('/depts/tree')) as any
  // 扁平化部门树
  const flat: any[] = []
  function walk(nodes: any[]) {
    for (const node of nodes) {
      flat.push(node)
      if (node.children?.length) walk(node.children)
    }
  }
  walk(deptList.value)
  deptFlatList.value = flat
  deptNames.value = flat.map((d: any) => d.dept_name)

  const res: any = await request.get('/users', { params: { page: 1, page_size: 1000 } })
  userList.value = res.items
  userNames.value = res.items.map((u: any) => u.real_name)
}

// ========== 内联编辑自动保存 ==========
async function onCellValueChanged(event: CellValueChangedEvent) {
  const field = event.colDef.field!
  const value = event.newValue
  const projectId = event.data.id

  if (field === 'status') {
    const map: Record<string, number> = { '进行中': 1, '已完结': 2, '暂停': 3 }
    await request.put(`/projects/${projectId}`, { status: map[value] || 1 })
    ElMessage.success('已自动保存')
    return
  }

  if (field === 'dept_name') {
    const dept = deptFlatList.value.find((d: any) => d.dept_name === value)
    await request.put(`/projects/${projectId}`, { dept_id: dept?.id })
    ElMessage.success('已自动保存')
    return
  }

  if (field === 'pm_name') {
    const user = userList.value.find((u: any) => u.real_name === value)
    await request.put(`/projects/${projectId}`, { pm_id: user?.id })
    ElMessage.success('已自动保存')
    return
  }

  await request.put(`/projects/${projectId}`, { [field]: value })
  ElMessage.success('已自动保存')
}

// ========== 右键菜单 / 更多操作 ==========
async function handleRowMenu(row: any) {
  // 用 MessageBox 模拟菜单
  try {
    await ElMessageBox.confirm(
      `对项目「${row.project_name}」的操作`,
      '更多操作',
      {
        confirmButtonText: '删除项目',
        cancelButtonText: '查看详情',
        distinguishCancelAndClose: true,
        type: 'warning',
      }
    )
    // 点了确认 = 删除
    await handleDelete(row.id)
  } catch (action: any) {
    // 点了取消 = 查看详情
    if (action === 'cancel') {
      goProgress(row)
    }
  }
}

async function handleDelete(id: number) {
  await ElMessageBox.confirm('确定删除该项目吗？任务数据也将被删除', '提示', { type: 'warning' })
  await request.delete(`/projects/${id}`)
  ElMessage.success('删除成功')
  fetchList()
}

// ========== 档案选择带出编号和名称 ==========
function onArchiveChange(archiveId: number) {
  const archive = archiveList.value.find((a: any) => a.id === archiveId)
  if (archive) {
    form.project_code = archive.project_code
    form.project_name = archive.project_name
  }
}

// ========== 新增项目 ==========
function openCreateDialog() {
  formRef.value?.resetFields()
  Object.assign(form, {
    id: 0, archive_id: null, project_code: '', project_name: '', dept_id: 0, pm_id: 0,
    status: 1, start_date: '', end_date: '', budget: null,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  // 通过档案带出编号和名称，提交 archive_id
  await request.post('/projects', {
    archive_id: form.archive_id,
    project_code: form.project_code,
    project_name: form.project_name,
    dept_id: form.dept_id,
    pm_id: form.pm_id,
    status: form.status,
    start_date: form.start_date || null,
    end_date: form.end_date || null,
    budget: form.budget,
  })
  ElMessage.success('创建成功')
  dialogVisible.value = false
  fetchList()
}

// ========== 导航 ==========
function goProgress(row: any) {
  router.push({ name: 'ProjectProgress', params: { id: row.id }, query: { name: row.project_name } })
}

onMounted(() => { fetchList(); fetchOptions() })
</script>

<style scoped>
.project-list-page {
  min-height: 100%;
}

.project-list-grid-shell {
  width: 100%;
  min-width: 0;
}

.project-list-grid-shell :deep(.ag-body-horizontal-scroll) {
  height: 0 !important;
  min-height: 0 !important;
  opacity: 0;
  pointer-events: none;
  overflow: hidden;
}

/* 项目名称链接 */
:deep(.proj-link) {
  color: var(--pms-primary);
  cursor: pointer;
  font-weight: 600;
  text-decoration: none;
}
:deep(.proj-link:hover) { text-decoration: underline; }
</style>
