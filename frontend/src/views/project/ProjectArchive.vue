<template>
  <PmsDataList
    ref="archiveListRef"
    class="project-archive-page"
    scrollbar-label="项目档案表格横向滚动条"
  >
    <template #toolbar-left>
        <el-button v-if="hasPermission('project:archive:add')" type="primary" size="small" @click="openCreateDialog">
          <el-icon style="margin-right:4px;"><Plus /></el-icon>
          新增档案
        </el-button>
        <el-button v-if="hasPermission('project:archive:delete')" type="danger" size="small" plain :disabled="selectedRows.length === 0" @click="handleBatchDelete">
          <el-icon style="margin-right:4px;"><Delete /></el-icon>
          批量删除
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
        <el-button v-if="hasPermission('project:archive:sync')" type="success" size="small" :disabled="selectedRows.length === 0" @click="handleBatchSync">
          <el-icon style="margin-right:4px;"><Connection /></el-icon>
          批量同步 ERP
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
    </template>
    <template #toolbar-right>
        <span class="filter-count" v-if="filteredRowData.length !== rowData.length">
          已筛选 {{ filteredRowData.length }} / {{ total }} 条
        </span>
        <PmsListColumnPicker
          :model-value="selectedArchiveColumnKeys"
          :groups="archiveColumnGroups"
          :default-keys="defaultArchiveColumnKeys"
          aria-label="项目档案列设置"
          @update:model-value="handleArchiveColumnSelection"
          @restore-defaults="restoreArchiveColumnDefaults"
        />
    </template>

    <template #filters>
      <PmsListFilters
        v-model:filters="customFilters"
        :fields="archiveFilterFields"
        :active-count="activeCustomFilterCount"
      >
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
          <el-option v-for="item in filteredProductLineOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-model="filterStatus"
          placeholder="全部状态"
          size="small"
          clearable
          style="width: 120px;"
        >
          <el-option v-for="item in dictOptions.archive_status" :key="item.value" :label="item.label" :value="Number(item.value)" />
        </el-select>
      </PmsListFilters>
    </template>

    <template #grid>
      <ag-grid-vue
        ref="agGridRef"
        class="ag-theme-alpine wechat-table pms-ag-grid"
        :style="archiveGridStyle"
        :rowData="filteredRowData"
        :columnDefs="columnDefs"
        :defaultColDef="defaultColDef"
        :localeText="localeText"
        :theme="'legacy'"
        :pagination="false"
        :rowSelection="'multiple'"
        :enableCellTextSelection="true"
        :alwaysShowHorizontalScroll="true"
        @grid-ready="onGridReady"
        @first-data-rendered="scheduleArchiveScrollbarMetrics"
        @grid-size-changed="scheduleArchiveScrollbarMetrics"
        @column-resized="handleArchiveColumnResized"
        @column-moved="handleArchiveGridStructureChanged"
        @column-pinned="handleArchiveGridStructureChanged"
        @displayed-columns-changed="handleArchiveGridStructureChanged"
        @row-double-clicked="onRowDoubleClicked"
        @selection-changed="onSelectionChanged"
      />
    </template>

    <template #pagination>
      <CustomPagination
        v-if="total > 0"
        v-model="page"
        v-model:page-size="pageSize"
        :total="total"
        @update:model-value="fetchList"
        @update:page-size="() => { page = 1; fetchList() }"
      />
    </template>

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
            <el-option v-for="item in filteredProductLineOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" style="width: 100%;">
            <el-option v-for="item in dictOptions.archive_status" :key="item.value" :label="item.label" :value="Number(item.value)" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.manager_id" placeholder="请选择负责人" clearable style="width: 100%;">
            <el-option
              v-for="u in userList"
              :key="u.id"
              :label="u.real_name"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="产品类型">
          <el-select v-model="form.product_type" placeholder="请选择产品类型" clearable style="width: 100%;">
            <el-option v-for="item in dictOptions.product_type" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
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
        <el-button v-if="isEdit ? hasPermission('project:archive:edit') : hasPermission('project:archive:add')" type="primary" @click="handleSubmit">保存</el-button>
        <el-button v-if="isEdit && hasPermission('project:archive:edit') && hasPermission('project:archive:sync')" type="success" @click="handleSubmitAndSync">保存并同步</el-button>
      </template>
    </el-dialog>
  </PmsDataList>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Delete, Search, Connection } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef, type ColumnState } from 'ag-grid-community'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import { type ListFilterField, type ListFilterOption, useListFilters } from '@/composables/useListFilters'
import { loadEnumOptions } from '@/composables/useEnumOptions'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'

const localeText = chineseLocaleText
const authStore = useAuthStore()
const hasPermission = authStore.hasPermission

type ArchiveColumnPreferenceState = {
  selected_column_keys: string[]
  columnState: ColumnState[]
}

const ARCHIVE_COLUMN_STORAGE_KEY = 'pms_project_archive_list_columns_v1'
const LEGACY_ARCHIVE_LAYOUT_KEY = 'pms_archive_grid_layout_v2'

const archiveColumnGroups = [
  {
    key: 'business',
    label: '业务信息',
    fields: [
      { key: 'product_line', label: '产品线', value_type: 'select', list_available: true, quick_addable: false },
      { key: 'status', label: '状态', value_type: 'select', list_available: true, quick_addable: false },
      { key: 'manager_name', label: '负责人', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'product_type', label: '产品类型', value_type: 'select', list_available: true, quick_addable: false },
    ],
  },
  {
    key: 'plan',
    label: '计划信息',
    fields: [
      { key: 'plan_start_date', label: '计划开始', value_type: 'date', list_available: true, quick_addable: false },
      { key: 'plan_end_date', label: '计划结束', value_type: 'date', list_available: true, quick_addable: false },
    ],
  },
  {
    key: 'audit',
    label: '维护信息',
    fields: [
      { key: 'created_by_name', label: '创建人', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'updated_by_name', label: '最后编辑人', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'updated_at', label: '最后编辑时间', value_type: 'datetime', list_available: true, quick_addable: false },
    ],
  },
  {
    key: 'erp',
    label: 'ERP 同步',
    fields: [
      { key: 'erp_sync_time', label: '最后同步时间', value_type: 'datetime', list_available: true, quick_addable: false },
      { key: 'erp_sync_by_name', label: '最后同步人', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'erp_sync_status', label: '同步状态', value_type: 'select', list_available: true, quick_addable: false },
    ],
  },
]

const defaultArchiveColumnKeys = archiveColumnGroups.flatMap(group => group.fields.map(field => field.key))
const availableArchiveColumnKeys = new Set(defaultArchiveColumnKeys)
const fixedArchiveColumnKeys = new Set(['archive_selection', 'project_code', 'project_name', 'archive_actions'])
const selectedArchiveColumnKeys = ref<string[]>([...defaultArchiveColumnKeys])
const archiveColumnPreferenceOwnerId = ref<number | null>(null)
const archiveColumnPreferencesReady = ref(false)
const archiveColumnPreferenceWritesEnabled = ref(false)
const archiveColumnStateRestored = ref(false)
const restoringArchiveColumnState = ref(false)
let gridApi: any = null

function onGridReady(params: any) {
  gridApi = params.api
  completeArchiveColumnPreferenceRestore()
  scheduleArchiveScrollbarMetrics()
}

function archiveColumnPreferenceStorageKey() {
  if (archiveColumnPreferenceOwnerId.value == null) return null
  return `${ARCHIVE_COLUMN_STORAGE_KEY}:${archiveColumnPreferenceOwnerId.value}`
}

async function resolveArchiveColumnPreferenceOwner() {
  if (!authStore.user) {
    try {
      await authStore.fetchUser()
    } catch {
      return
    }
  }
  archiveColumnPreferenceOwnerId.value = authStore.user?.id ?? null
}

function normalizeArchiveColumnKeys(keys: unknown) {
  if (!Array.isArray(keys)) return [...defaultArchiveColumnKeys]
  return keys.filter((key): key is string => typeof key === 'string' && availableArchiveColumnKeys.has(key))
}

function readArchiveColumnPreferences(): ArchiveColumnPreferenceState | null {
  const storageKey = archiveColumnPreferenceStorageKey()
  if (!storageKey) return null

  const raw = localStorage.getItem(storageKey)
  if (raw) {
    try {
      const parsed = JSON.parse(raw)
      return {
        selected_column_keys: normalizeArchiveColumnKeys(parsed?.selected_column_keys),
        columnState: Array.isArray(parsed?.columnState) ? parsed.columnState : [],
      }
    } catch { /* 忽略损坏的当前版本缓存 */ }
  }

  const legacyRaw = localStorage.getItem(LEGACY_ARCHIVE_LAYOUT_KEY)
  if (!legacyRaw) return null
  try {
    const legacyState = JSON.parse(legacyRaw)
    if (!Array.isArray(legacyState)) return null
    const visibleKeys = defaultArchiveColumnKeys.filter((key) => {
      const state = legacyState.find((item: ColumnState) => item.colId === key)
      return state?.hide !== true
    })
    return { selected_column_keys: visibleKeys, columnState: legacyState }
  } catch {
    return null
  }
}

function persistArchiveColumnPreferences() {
  if (!archiveColumnPreferencesReady.value || !archiveColumnPreferenceWritesEnabled.value) return
  const storageKey = archiveColumnPreferenceStorageKey()
  if (!storageKey) return
  const state: ArchiveColumnPreferenceState = {
    selected_column_keys: [...selectedArchiveColumnKeys.value],
    columnState: gridApi?.getColumnState?.() || [],
  }
  localStorage.setItem(storageKey, JSON.stringify(state))
  localStorage.removeItem(LEGACY_ARCHIVE_LAYOUT_KEY)
}

function restoreSelectedArchiveColumnKeys() {
  const saved = readArchiveColumnPreferences()
  selectedArchiveColumnKeys.value = saved
    ? normalizeArchiveColumnKeys(saved.selected_column_keys)
    : [...defaultArchiveColumnKeys]
}

function restoreArchiveColumnState() {
  if (!archiveColumnPreferencesReady.value || !gridApi || archiveColumnStateRestored.value) return
  archiveColumnStateRestored.value = true
  const saved = readArchiveColumnPreferences()
  if (!saved?.columnState.length) return
  restoringArchiveColumnState.value = true
  try {
    const selectedKeys = new Set(selectedArchiveColumnKeys.value)
    const reconciledState = saved.columnState.map((state) => {
      if (fixedArchiveColumnKeys.has(state.colId)) return { ...state, hide: false }
      if (availableArchiveColumnKeys.has(state.colId)) return { ...state, hide: !selectedKeys.has(state.colId) }
      return state
    })
    gridApi.applyColumnState({ state: reconciledState, applyOrder: true })
  } finally {
    restoringArchiveColumnState.value = false
  }
  scheduleArchiveScrollbarMetrics()
}

function completeArchiveColumnPreferenceRestore() {
  if (!archiveColumnPreferencesReady.value || !gridApi) return
  restoreArchiveColumnState()
  archiveColumnPreferenceWritesEnabled.value = true
}

function handleArchiveColumnSelection(keys: string[]) {
  selectedArchiveColumnKeys.value = normalizeArchiveColumnKeys(keys)
  nextTick(() => {
    scheduleArchiveScrollbarMetrics()
    persistArchiveColumnPreferences()
  })
}

function handleArchiveGridStructureChanged() {
  scheduleArchiveScrollbarMetrics()
  if (!archiveColumnPreferenceWritesEnabled.value || restoringArchiveColumnState.value) return
  persistArchiveColumnPreferences()
}

function handleArchiveColumnResized(event: any) {
  scheduleArchiveScrollbarMetrics()
  if (!event?.finished || !archiveColumnPreferenceWritesEnabled.value || restoringArchiveColumnState.value) return
  persistArchiveColumnPreferences()
}

function restoreArchiveColumnDefaults() {
  const storageKey = archiveColumnPreferenceStorageKey()
  if (storageKey) localStorage.removeItem(storageKey)
  localStorage.removeItem(LEGACY_ARCHIVE_LAYOUT_KEY)
  selectedArchiveColumnKeys.value = [...defaultArchiveColumnKeys]
  nextTick(() => {
    gridApi?.resetColumnState?.()
    scheduleArchiveScrollbarMetrics()
    persistArchiveColumnPreferences()
  })
}

// ========== 数据状态 ==========
const rowData = ref<any[]>([])
const userList = ref<any[]>([])
const total = ref(0)
const searchKeyword = ref('')
const selectedRows = ref<any[]>([])
const agGridRef = ref()
const archiveListRef = ref<InstanceType<typeof PmsDataList>>()
const page = ref(1)
const pageSize = ref(15)
const filterStatus = ref<number | null>(null)
const filterProductLine = ref<string | null>(null)

// 字典选项
const dictOptions = reactive<Record<string, any[]>>({
  product_line: [],
  product_type: [],
  archive_status: [],
})
const dictLabelMaps = reactive<Record<string, Record<string, string>>>({})

function enumLabel(code: string, value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  return dictLabelMaps[code]?.[String(value)] || String(value)
}

// 用户允许的产品线
const allowedProductLines = ref<string[] | null>(null)

async function fetchAllowedProductLines() {
  try {
    const res: any = await request.get('/auth/product-lines')
    if (res.unrestricted) {
      allowedProductLines.value = null // null = 不限制
    } else {
      allowedProductLines.value = res.items || []
    }
  } catch { /* ignore */ }
}

// 筛选栏可用的产品线选项（取字典与权限的交集）
const filteredProductLineOptions = computed(() => {
  const all = dictOptions.product_line || []
  if (allowedProductLines.value === null) return all
  return all.filter(item => allowedProductLines.value!.includes(item.value))
})

const erpSyncStatusOptions: ListFilterOption[] = [
  { label: '待同步', value: 'pending' },
  { label: '已同步', value: 'success' },
  { label: '失败', value: 'failed' },
]

function dictFilterOptions(code: string, numeric = false): ListFilterOption[] {
  return (dictOptions[code] || []).map(item => ({
    label: String(item.label),
    value: numeric ? Number(item.value) : item.value,
  }))
}

function uniqueValueOptions(values: Array<string | number | null | undefined>): ListFilterOption[] {
  const optionMap = new Map<string, ListFilterOption>()
  values.forEach(value => {
    if (value === null || value === undefined || value === '') return
    const label = String(value)
    if (!optionMap.has(label)) {
      optionMap.set(label, { label, value })
    }
  })
  return Array.from(optionMap.values())
}

const archiveUserNameOptions = computed(() => uniqueValueOptions([
  ...userList.value.map(user => user.real_name || user.username),
  ...rowData.value.flatMap(row => [
    row.manager_name,
    row.created_by_name,
    row.updated_by_name,
    row.erp_sync_by_name,
  ]),
]))

const archiveFilterFields = computed<ListFilterField<any>[]>(() => [
  { field: 'project_code', label: '项目编号', type: 'text' },
  { field: 'project_name', label: '项目名称', type: 'text' },
  { field: 'product_line', label: '产品线', type: 'select', options: () => filteredProductLineOptions.value },
  { field: 'status', label: '状态', type: 'select', options: () => dictFilterOptions('archive_status', true) },
  { field: 'manager_name', label: '负责人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'product_type', label: '产品类型', type: 'select', options: () => dictFilterOptions('product_type') },
  { field: 'plan_start_date', label: '计划开始', type: 'date' },
  { field: 'plan_end_date', label: '计划结束', type: 'date' },
  { field: 'created_by_name', label: '创建人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'updated_by_name', label: '最后编辑人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'erp_sync_by_name', label: '最后同步人', type: 'select', options: () => archiveUserNameOptions.value },
  {
    field: 'erp_sync_status',
    label: '同步状态',
    type: 'select',
    options: () => erpSyncStatusOptions,
    getValue: row => row.erp_sync_status || 'pending',
  },
])

const { customFilters, activeCustomFilterCount, applyCustomFilters } = useListFilters(archiveFilterFields)

async function fetchDictOptions(code: string) {
  try {
    const definition = await loadEnumOptions(code)
    dictOptions[code] = definition.items
    dictLabelMaps[code] = definition.label_map
  } catch { /* ignore */ }
}

// 客户端筛选
const filteredRowData = computed(() => {
  let result = rowData.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(r =>
      String(r.project_code ?? '').toLowerCase().includes(kw) ||
      String(r.project_name ?? '').toLowerCase().includes(kw)
    )
  }
  if (filterStatus.value != null) {
    result = result.filter(r => r.status === filterStatus.value)
  }
  if (filterProductLine.value) {
    result = result.filter(r => r.product_line === filterProductLine.value)
  }
  return applyCustomFilters(result)
})

const archiveGridStyle = computed(() => {
  const visibleRows = Math.max(filteredRowData.value.length, 1)
  const height = Math.min(430, Math.max(176, 74 + visibleRows * 38))
  return { width: '100%', height: `${height}px` }
})

function scheduleArchiveScrollbarMetrics() {
  archiveListRef.value?.refreshScrollbar()
}

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
const statusMap = computed(() => {
  const map: Record<number, string> = {}
  Object.entries(dictLabelMaps.archive_status || {}).forEach(([value, label]) => {
    map[Number(value)] = label
  })
  return map
})
const archiveStatusTone: Record<number, string> = { 1: 'neutral', 2: 'info', 3: 'success', 4: 'warning' }

function escapeHtml(value: any) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function archiveColumnVisibility(key: string): Pick<ColDef, 'colId' | 'hide'> {
  return {
    colId: key,
    hide: !selectedArchiveColumnKeys.value.includes(key),
  }
}

const columnDefs = computed<ColDef[]>(() => [
  ...(hasPermission('project:archive:delete') || hasPermission('project:archive:sync')
    ? [{ colId: 'archive_selection', headerClass: 'archive-list-header-center', headerCheckboxSelection: true, checkboxSelection: true, width: 44, pinned: 'left', filter: false, sortable: false, resizable: false } as ColDef]
    : []),
  { colId: 'project_code', field: 'project_code', headerName: '项目编号', width: 130, minWidth: 110, pinned: 'left' },
  { colId: 'project_name', field: 'project_name', headerName: '项目名称', width: 190, minWidth: 160 },
  {
    ...archiveColumnVisibility('product_line'), field: 'product_line', headerName: '产品线', width: 110, minWidth: 100,
    valueFormatter: (params: any) => enumLabel('product_line', params.value),
  },
  {
    ...archiveColumnVisibility('status'), field: 'status', headerName: '状态', width: 100, minWidth: 96,
    cellRenderer: (params: any) => {
      const v = params.value
      const tone = archiveStatusTone[v] || 'neutral'
      const label = escapeHtml(statusMap.value[v] || '-')
      return `<span class="pms-status pms-status-${tone}"><span class="pms-status-dot"></span>${label}</span>`
    },
  },
  { ...archiveColumnVisibility('manager_name'), field: 'manager_name', headerName: '负责人', width: 110, minWidth: 96 },
  {
    ...archiveColumnVisibility('product_type'), field: 'product_type', headerName: '产品类型', width: 110, minWidth: 96,
    valueFormatter: (params: any) => enumLabel('product_type', params.value),
  },
  {
    ...archiveColumnVisibility('plan_start_date'), field: 'plan_start_date', headerName: '计划开始', width: 118, minWidth: 112,
    valueFormatter: (params: any) => params.value ? params.value.substring(0, 10) : '-',
  },
  {
    ...archiveColumnVisibility('plan_end_date'), field: 'plan_end_date', headerName: '计划结束', width: 118, minWidth: 112,
    valueFormatter: (params: any) => params.value ? params.value.substring(0, 10) : '-',
  },
  { ...archiveColumnVisibility('created_by_name'), field: 'created_by_name', headerName: '创建人', width: 110, minWidth: 96 },
  { ...archiveColumnVisibility('updated_by_name'), field: 'updated_by_name', headerName: '最后编辑人', width: 120, minWidth: 110 },
  {
    ...archiveColumnVisibility('updated_at'), field: 'updated_at', headerName: '最后编辑时间', width: 170, minWidth: 160,
    valueFormatter: (params: any) => params.value ? new Date(params.value).toLocaleString('zh-CN') : '-',
  },
  {
    ...archiveColumnVisibility('erp_sync_time'), field: 'erp_sync_time', headerName: '最后同步时间', width: 170, minWidth: 160,
    valueFormatter: (params: any) => {
      if (!params.value) return '-'
      const d = new Date(params.value)
      const pad = (n: number) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    },
  },
  { ...archiveColumnVisibility('erp_sync_by_name'), field: 'erp_sync_by_name', headerName: '最后同步人', width: 120, minWidth: 110 },
  {
    ...archiveColumnVisibility('erp_sync_status'), field: 'erp_sync_status', headerName: '同步', width: 100, minWidth: 96,
    cellRenderer: (params: any) => {
      const v = params.value
      if (!v || v === 'pending') return '<span class="pms-status pms-status-warning"><span class="pms-status-dot"></span>待同步</span>'
      if (v === 'success') return '<span class="pms-status pms-status-success"><span class="pms-status-dot"></span>已同步</span>'
      if (v === 'failed') {
        const title = escapeHtml(params.data.erp_error_msg || '')
        return `<span class="pms-status pms-status-danger" title="${title}"><span class="pms-status-dot"></span>失败</span>`
      }
      return '<span class="pms-status pms-status-neutral"><span class="pms-status-dot"></span>-</span>'
    },
  },
  {
    colId: 'archive_actions', headerName: '操作', width: 146, minWidth: 136, pinned: 'right', filter: false, sortable: false, resizable: false,
    cellRenderer: (params: any) => {
      return `${hasPermission('project:archive:edit') ? `<button class="pms-table-action edit-btn" data-id="${params.data.id}">编辑</button>` : ''}
              ${hasPermission('project:archive:sync') ? `<button class="pms-table-action pms-link-success sync-btn" data-id="${params.data.id}">同步</button>` : ''}
              ${hasPermission('project:archive:delete') ? `<button class="pms-table-action pms-link-danger del-btn" data-id="${params.data.id}">删除</button>` : ''}`
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
])

const defaultColDef = {
  sortable: true,
  resizable: true,
  filter: false,
  suppressSizeToFit: true,
  headerClass: 'archive-list-header-center',
}

// ========== 数据加载 ==========
async function fetchList() {
  const res: any = await request.get('/projects/archives/list', {
    params: { page: 1, page_size: 1000 },
  })
  rowData.value = res.items
  total.value = res.total
  scheduleArchiveScrollbarMetrics()
}

async function fetchUsers() {
  userList.value = (await request.get('/users/options')) as any
}

// ========== 选择事件 ==========
function onSelectionChanged() {
  selectedRows.value = agGridRef.value?.api?.getSelectedRows?.() || []
}

// ========== 双击编辑 ==========
function onRowDoubleClicked(event: any) {
  if (!hasPermission('project:archive:edit')) return
  if (event.data) openEditDialog(event.data)
}

// ========== 弹窗操作 ==========
function openCreateDialog() {
  if (!hasPermission('project:archive:add')) return
  formRef.value?.resetFields()
  Object.assign(form, { id: 0, project_code: '', project_name: '', status: 1, manager_id: null, product_type: '', product_line: '', plan_start_date: '', plan_end_date: '' })
  isEdit.value = false
  dialogVisible.value = true
}

function openEditDialog(row: any) {
  if (!hasPermission('project:archive:edit')) return
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
  if (isEdit.value ? !hasPermission('project:archive:edit') : !hasPermission('project:archive:add')) return
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

async function handleSubmitAndSync() {
  if (!hasPermission('project:archive:edit') || !hasPermission('project:archive:sync')) return
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
  } else {
    const createRes: any = await request.post('/projects/archives', { ...payload, project_code: form.project_code })
    form.id = createRes.id
  }
  dialogVisible.value = false

  // 保存完成后同步到金蝶ERP
  try {
    const syncRes: any = await request.post('/erp/sync', { archive_id: form.id })
    if (syncRes.success) {
      ElMessage.success('保存并同步成功')
    } else {
      ElMessage.warning(`保存成功，但同步失败：${syncRes.message}`)
    }
  } catch (e: any) {
    ElMessage.warning('保存成功，但同步异常：' + (e?.response?.data?.message || e?.message))
  }
  fetchList()
}

// ========== 删除 ==========
async function handleDeleteSingle(id: number) {
  if (!hasPermission('project:archive:delete')) return
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
  if (!hasPermission('project:archive:delete')) return
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
  if (!hasPermission('project:archive:sync')) return
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
  if (!hasPermission('project:archive:sync')) return
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

onMounted(async () => {
  fetchList(); fetchUsers(); fetchAllowedProductLines()
  fetchDictOptions('product_line')
  fetchDictOptions('product_type')
  fetchDictOptions('archive_status')
  await resolveArchiveColumnPreferenceOwner()
  restoreSelectedArchiveColumnKeys()
  archiveColumnPreferencesReady.value = true
  await nextTick()
  completeArchiveColumnPreferenceRestore()
  scheduleArchiveScrollbarMetrics()
})
</script>

<style scoped>
.project-archive-page {
  min-height: 100%;
}

:deep(.pms-table-action + .pms-table-action) {
  margin-left: 2px;
}

:deep(.archive-list-header-center .ag-header-cell-label) {
  justify-content: center;
}
</style>
