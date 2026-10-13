<template>
  <PmsDataList
    ref="dataListRef"
    class="pms-system-page field-catalog-page"
    scrollbar-label="数据字典横向滚动条"
  >
    <template #toolbar-left>
      <div class="catalog-title">
        <strong>系统字段目录</strong>
        <span>由模型、接口 Schema 与项目总表注册表自动生成</span>
      </div>
    </template>
    <template #toolbar-right>
      <el-button size="small" @click="fetchCatalog">刷新</el-button>
    </template>

    <template #filters>
      <PmsQueryWorkspace entry-mode="document" v-model="queryDraft" list-key="system-data-dictionary" :fields="queryFields" :defaults="queryDefaults" :loading="loading" :snapshot="() => ({ pageSize })" @query="runQuery" @clear-columns="clearQueryColumns" />
      <p v-if="queryError" role="alert">{{ queryError }}</p>
    </template>

    <template #grid>
      <ag-grid-vue
        v-loading="loading"
        class="ag-theme-alpine pms-ag-grid field-catalog-grid"
        style="width: 100%"
        :row-data="pagedRows"
        :column-defs="queryColumnDefs"
        @grid-ready="gridApi = $event.api"
        :default-col-def="defaultColDef"
        :locale-text="localeText"
        :theme="'legacy'"
        :pagination="false"
        :always-show-horizontal-scroll="true"
        :enable-cell-text-selection="true"
        @first-data-rendered="refreshScrollbar"
        @grid-size-changed="refreshScrollbar"
        @column-resized="refreshScrollbar"
      />
    </template>

    <template #pagination>
      <CustomPagination
        v-model="page"
        v-model:page-size="pageSize"
        :total="total"
        @update:model-value="refreshScrollbar"
        @update:page-size="handlePageSizeChange"
      />
    </template>
  </PmsDataList>
</template>

<script setup lang="ts">
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import { useSystemQuery, loadCompleteDataset } from '@/query-system/system-adapter'
import type { QueryCondition } from '@/query-system/core'
import { decorateQueryColumns } from '@/query-system/column-grid'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsDataList from '@/components/PmsDataList.vue'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '@/config/listUi'
import { PmsCheckboxControl, PmsSelectControl, PmsTextControl, type PmsOption } from '@/form-system'
import { chineseLocaleText } from '@/utils/agGridLocale'
import request from '@/utils/request'

ModuleRegistry.registerModules([AllCommunityModule])

type FieldCatalogRow = {
  module: string
  module_name: string
  group: string
  field_name: string
  field_code: string
  value_type: string
  source_type: string
  storage_table?: string | null
  storage_column?: string | null
  editable: boolean
  computed: boolean
  enum_code?: string | null
  description: string
}

type ModuleOption = { value: string; label: string; count: number }

const localeText = chineseLocaleText
const dataListRef = ref<InstanceType<typeof PmsDataList>>()
const loading = ref(false)
const rows = ref<FieldCatalogRow[]>([])
const queryError = ref('')
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const moduleOptions = ref<ModuleOption[]>([])
const moduleSelectOptions = computed<PmsOption[]>(() => moduleOptions.value.map(item => ({
  label: `${item.label} (${item.count})`,
  value: item.value,
})))

const valueTypeOptions = [
  { label: '文本', value: 'text' },
  { label: '整数', value: 'integer' },
  { label: '数值', value: 'number' },
  { label: '日期', value: 'date' },
  { label: '日期时间', value: 'datetime' },
  { label: '选择', value: 'select' },
  { label: '进度', value: 'progress' },
  { label: 'JSON', value: 'json' },
  { label: '列表', value: 'list' },
]

const sourceTypeOptions = [
  { label: '数据库字段', value: 'database' },
  { label: '业务枚举', value: 'enum' },
  { label: '引用字段', value: 'archive' },
  { label: '项目主表', value: 'project' },
  { label: '人工维护', value: 'detail' },
  { label: '自动计算', value: 'computed' },
  { label: '接口展示', value: 'relation' },
  { label: '系统固定', value: 'system_fixed' },
  { label: '系统字段', value: 'system' },
]

const sourceLabels = Object.fromEntries(sourceTypeOptions.map(item => [item.value, item.label]))
const gridApi = ref<any>(null)
const { fields: queryFields, defaults: queryDefaults, draft: queryDraft, submit: submitQuery, topRows, pageRows, clearColumns, columnContext, columnFilters } = useSystemQuery(() => [
  { field: 'field_name', label: '字段名称', type: 'text' },
  { field: 'field_code', label: '字段编码', type: 'text' },
  { field: 'module', label: '模块', type: 'enum', options: moduleSelectOptions.value.map(o => ({value:String(o.value),label:o.label})) },
  { field: 'group', label: '分组', type: 'text' },
  { field: 'value_type', label: '类型', type: 'enum', options: valueTypeOptions },
  { field: 'source_type', label: '来源', type: 'enum', options: sourceTypeOptions },
  { field: 'storage_table', label: '存储表', type: 'text' },
  { field: 'storage_column', label: '存储列', type: 'text' },
  { field: 'enum_code', label: '枚举编码', type: 'text' },
  { field: 'description', label: '说明', type: 'text' },
  { field: 'editable', label: '可编辑', type: 'enum', options:[{value:1,label:'是'},{value:0,label:'否'}] },
], ['field_name', 'module', 'value_type', 'source_type'], {ready:()=>!loading.value,pagination:{page,size:pageSize}})
const catalogQueryRecord = (row:FieldCatalogRow) => ({...row,editable:Number(row.editable)})
const filteredRows = computed(() => topRows(rows.value, catalogQueryRecord))
const total = computed(() => filteredRows.value.length)
const pagedRows = computed(() => pageRows(rows.value, catalogQueryRecord))
function runQuery(conditions: QueryCondition[], preferences: object) {
  submitQuery(conditions)
  const size = (preferences as {pageSize?:number}).pageSize
  if (size && PAGE_SIZE_OPTIONS.includes(size)) pageSize.value = size
  page.value = 1
  refreshScrollbar()
}
function clearQueryColumns() { clearColumns(); gridApi.value?.setFilterModel(null); gridApi.value?.refreshCells({force:true}) }
columnContext.sort = (field, direction) => gridApi.value?.applyColumnState({state:[{colId:field,sort:direction}],defaultState:{sort:null}})
watch(rows, clearColumns, {flush:'sync'})
const typeLabels = Object.fromEntries(valueTypeOptions.map(item => [item.value, item.label]))
const columnDefs: ColDef<FieldCatalogRow>[] = [
  { field: 'module', headerName: '模块', width: 112, valueFormatter: params => params.data?.module_name || params.value },
  { field: 'group', headerName: '分组', width: 120 },
  { field: 'field_name', headerName: '字段名称', width: 156, pinned: 'left' },
  { field: 'field_code', headerName: '字段编码', width: 206, pinned: 'left', cellClass: 'catalog-code' },
  { field: 'value_type', headerName: '类型', width: 92, valueFormatter: params => typeLabels[params.value] || params.value },
  { field: 'source_type', headerName: '来源', width: 112, valueFormatter: params => sourceLabels[params.value] || params.value },
  { field: 'storage_table', headerName: '存储表', width: 174, valueFormatter: params => params.value || '-' },
  { field: 'storage_column', headerName: '存储列', width: 208, valueFormatter: params => params.value || '-' },
  { field: 'editable', headerName: '可编辑', width: 82, valueFormatter: params => params.value ? '是' : '否' },
  { field: 'enum_code', headerName: '枚举编码', width: 152, valueFormatter: params => params.value || '-' },
  { field: 'description', headerName: '说明', minWidth: 260, flex: 1, tooltipField: 'description' },
]

const defaultColDef: ColDef = {
  sortable: true,
  resizable: true,
  suppressMovable: false,
  cellStyle: { display: 'flex', alignItems: 'center' },
}
const queryColumnDefs = computed(() => decorateQueryColumns(columnDefs, () => columnContext))

let listRequestSerial = 0
async function fetchCatalog() {
  const requestSerial = ++listRequestSerial
  loading.value = true
  queryError.value = ''
  try {
    const response = await loadCompleteDataset(async (page, pageSize) => await request.get('/field-catalog', { params: { page, page_size: pageSize } }) as any, 200, () => requestSerial === listRequestSerial, (row:any) => `${row.module}:${row.field_code}`)
    if (requestSerial !== listRequestSerial) return
    rows.value = response.items || []
    page.value = Math.min(page.value, Math.max(1, Math.ceil(total.value / pageSize.value)))
    moduleOptions.value = response.modules || []
    await nextTick()
    refreshScrollbar()
  } catch {
    if (requestSerial === listRequestSerial) { rows.value = []; queryError.value = '字段目录未完整读取，请刷新重试' }
  } finally {
    if (requestSerial === listRequestSerial) loading.value = false
  }
}

function handlePageSizeChange() {
  page.value = 1
  refreshScrollbar()
}

function refreshScrollbar() {
  requestAnimationFrame(() => dataListRef.value?.refreshScrollbar())
}

onMounted(fetchCatalog)
</script>

<style scoped>
.field-catalog-page {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
}

.field-catalog-page :deep(.pms-data-list-grid-shell) {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
}

.field-catalog-page :deep(.field-catalog-grid) {
  height: auto;
  min-height: 0;
  flex: 1;
}

.catalog-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.catalog-title strong {
  color: var(--pms-text);
  font-size: 14px;
}

.catalog-title span {
  color: var(--pms-text-secondary);
  font-size: 12px;
}

.catalog-filters {
  display: flex;
  align-items: center;
  gap: var(--pms-query-gap);
  flex-wrap: wrap;
  padding-bottom: var(--pms-query-inset);
}

.catalog-filter {
  flex: 0 0 auto;
}

.catalog-filter--keyword { width: 244px; }
.catalog-filter--module { width: 156px; }
.catalog-filter--type { width: 126px; }
.catalog-filter--source { width: 142px; }

:deep(.catalog-code) {
  color: var(--pms-text-secondary);
  font-family: var(--pms-font-mono);
  font-size: 12px;
}

:deep(.field-catalog-grid .ag-header-cell-label) {
  justify-content: center;
}
</style>
