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
      <el-button size="small" @click="resetFilters">重置筛选</el-button>
      <el-button size="small" @click="fetchCatalog">刷新</el-button>
    </template>

    <template #filters>
      <div class="pms-filter-bar catalog-filters">
        <el-input
          v-model="filters.keyword"
          clearable
          size="small"
          placeholder="搜索字段名称、编码或说明"
          style="width: 244px"
          @change="handleFilterChange"
          @clear="handleFilterChange"
          @keyup.enter="handleFilterChange"
        />
        <el-select
          v-model="filters.module"
          clearable
          size="small"
          placeholder="全部模块"
          style="width: 156px"
          @change="handleFilterChange"
        >
          <el-option
            v-for="item in moduleOptions"
            :key="item.value"
            :label="`${item.label} (${item.count})`"
            :value="item.value"
          />
        </el-select>
        <el-select
          v-model="filters.valueType"
          clearable
          size="small"
          placeholder="全部类型"
          style="width: 126px"
          @change="handleFilterChange"
        >
          <el-option v-for="item in valueTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-model="filters.sourceType"
          clearable
          size="small"
          placeholder="全部来源"
          style="width: 142px"
          @change="handleFilterChange"
        >
          <el-option v-for="item in sourceTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-checkbox v-model="filters.enumOnly" size="small" @change="handleFilterChange">
          仅枚举字段
        </el-checkbox>
      </div>
    </template>

    <template #grid>
      <ag-grid-vue
        v-loading="loading"
        class="ag-theme-alpine pms-ag-grid field-catalog-grid"
        style="width: 100%"
        :row-data="rows"
        :column-defs="columnDefs"
        :default-col-def="defaultColDef"
        :locale-text="localeText"
        :theme="'legacy'"
        :row-height="36"
        :header-height="38"
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
        @update:model-value="fetchCatalog"
        @update:page-size="handlePageSizeChange"
      />
    </template>
  </PmsDataList>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsDataList from '@/components/PmsDataList.vue'
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
const total = ref(0)
const page = ref(1)
const pageSize = ref(30)
const moduleOptions = ref<ModuleOption[]>([])
const filters = reactive({ keyword: '', module: '', valueType: '', sourceType: '', enumOnly: false })

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
const typeLabels = Object.fromEntries(valueTypeOptions.map(item => [item.value, item.label]))
const columnDefs: ColDef<FieldCatalogRow>[] = [
  { field: 'module_name', headerName: '模块', width: 112 },
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

async function fetchCatalog() {
  loading.value = true
  try {
    const response: any = await request.get('/field-catalog', {
      params: {
        keyword: filters.keyword || undefined,
        module: filters.module || undefined,
        value_type: filters.valueType || undefined,
        source_type: filters.sourceType || undefined,
        enum_only: filters.enumOnly || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    rows.value = response.items || []
    total.value = response.total || 0
    moduleOptions.value = response.modules || []
    await nextTick()
    refreshScrollbar()
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  page.value = 1
  fetchCatalog()
}

function handlePageSizeChange() {
  page.value = 1
  fetchCatalog()
}

function resetFilters() {
  Object.assign(filters, { keyword: '', module: '', valueType: '', sourceType: '', enumOnly: false })
  handleFilterChange()
}

function refreshScrollbar() {
  requestAnimationFrame(() => dataListRef.value?.refreshScrollbar())
}

onMounted(fetchCatalog)
</script>

<style scoped>
.field-catalog-page {
  display: flex;
  height: calc(100vh - 88px);
  min-height: 520px;
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
  min-height: 300px;
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
  gap: 8px;
  padding-bottom: 10px;
}

:deep(.catalog-code) {
  color: var(--pms-text-secondary);
  font-family: var(--pms-font-mono);
  font-size: 12px;
}

:deep(.field-catalog-grid .ag-header-cell-label) {
  justify-content: center;
}
</style>
