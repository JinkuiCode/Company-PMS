<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import ReportExportControl from '@/components/ReportExportControl.vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColumnState, type GridApi, type GridReadyEvent, type ColumnResizedEvent } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import { PmsTextControl, PmsSelectControl } from '@/form-system'
import { DEFAULT_PAGE_SIZE, PMS_GRID_OPTIONS } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { hasListFilterValue, type ListCustomFilter, type ListFilterField } from '@/composables/useListFilters'
import { useAuthStore } from '@/stores/auth'
import { getInventoryMetadata, getInventoryRows, getInventoryStocks, type InventoryField, type InventoryMetadata, type InventoryRow } from '@/api/inventoryReport'

ModuleRegistry.registerModules([AllCommunityModule])
const auth = useAuthStore()
const metadata = ref<InventoryMetadata | null>(null), rows = ref<InventoryRow[]>([])
const filters = reactive({ keyword: '', organization_id: null as number | null, stock: '' })
const custom = ref<ListCustomFilter[]>([]), visible = ref<string[]>([])
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
const loading = ref(false), error = ref(''), stamp = ref('')
const stocks = ref<{ value: string; label: string }[]>([]), stockLoading = ref(false)
const sort = reactive({ sort: 'FID', direction: 'asc' })
const listRef = ref<InstanceType<typeof PmsDataList>>()
let grid: GridApi<InventoryRow> | null = null
let savedColumns: ColumnState[] = [], restoring = false, stockRevision = 0
let revision = 0, controller: AbortController | null = null, timer: ReturnType<typeof setTimeout> | undefined
const storageKey = computed(() => `pms:inventory-report:v1:${auth.user?.id || 'anonymous'}`)
const defaultKeys = computed(() => metadata.value?.fields.map(field => field.key) || [])
const groups = computed(() => [{ key: 'inventory', label: '即时库存', fields: (metadata.value?.fields || []).map(field => ({...field, quick_addable: true})) }])
const filterFields = computed<ListFilterField[]>(() => (metadata.value?.fields || []).map(field => ({
  field: field.key, label: field.label, type: field.value_type === 'number' ? 'number' : 'text',
})))
const activeFilters = computed(() => custom.value.filter(hasListFilterValue))
function readPreferences() {
  visible.value = [...defaultKeys.value]
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey.value) || '{}')
    const keys = new Set(defaultKeys.value)
    if (Array.isArray(saved.visible)) {
      const clean = saved.visible.filter((key: unknown) => typeof key === 'string' && keys.has(key))
      if (clean.length) visible.value = [...new Set(clean)] as string[]
    }
    savedColumns = Array.isArray(saved.columns) ? saved.columns.filter((c: ColumnState) => c && keys.has(c.colId)).map((c: ColumnState) => ({
      colId: c.colId, width: Math.max(80, Math.min(800, Number(c.width) || 140)), pinned: c.pinned === 'left' || c.pinned === 'right' ? c.pinned : null,
      hide: !visible.value.includes(c.colId), sort: c.sort === 'asc' || c.sort === 'desc' ? c.sort : null,
    })) : []
    const sorted = savedColumns.find(c => c.sort)
    if (sorted) { sort.sort = sorted.colId; sort.direction = sorted.sort! }
  } catch { savedColumns = [] }
}
function savePreferences() {
  if (restoring) return
  try { localStorage.setItem(storageKey.value, JSON.stringify({ visible: visible.value, columns: grid?.getColumnState() || savedColumns })) }
  catch { ElMessage.warning('列设置保存失败，请检查浏览器存储空间') }
  void nextTick(() => listRef.value?.refreshScrollbar())
}
function display(row: InventoryRow | undefined, field: InventoryField) {
  const value = row?.[field.key]
  if (value === null || value === undefined || value === '') return '-'
  return field.value_type === 'number' ? new Intl.NumberFormat('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(Number(value)) : String(value)
}
const columns = computed<ColDef<InventoryRow>[]>(() => (metadata.value?.fields || []).map(field => ({
  field: field.key, colId: field.key, headerName: field.label, headerTooltip: `${field.key} · ${field.description}`,
  initialWidth: field.width, minWidth: 80, maxWidth: 800, hide: !visible.value.includes(field.key),
  cellClass: field.value_type === 'number' ? 'inventory-number' : undefined,
  cellClassRules: field.value_type === 'number' ? {'inventory-negative': p => Number(p.value) < 0} : undefined,
  valueFormatter: params => display(params.data, field), tooltipValueGetter: params => display(params.data, field),
})))
// Sorting is performed before pagination by SQL; never reorder just the current page.
const defaultColDef: ColDef = {resizable: true, sortable: true, comparator: () => 0, editable: false, cellStyle: {overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}
function onGridReady(event: GridReadyEvent<InventoryRow>) {
  grid = event.api; restoring = true
  grid.applyColumnState({state: savedColumns.length ? savedColumns : [{colId: sort.sort, sort: sort.direction as 'asc' | 'desc'}], applyOrder: true})
  restoring = false; listRef.value?.refreshScrollbar()
}
function onColumnResized(event: ColumnResizedEvent) { if (event.finished) savePreferences() }
function onSortChanged() {
  if (restoring) return
  const column = grid?.getColumnState().find(c => c.sort)
  sort.sort = column?.colId || 'FID'; sort.direction = column?.sort || 'asc'; page.value = 1; savePreferences()
}
const params = () => ({...filters, organization_id: filters.organization_id || undefined, ...sort, page: page.value, page_size: pageSize.value,
  filters: JSON.stringify(activeFilters.value.map(({field, operator, value, valueEnd}) => ({field, operator, value, valueEnd}))),
})
async function fetchRows() {
  clearTimeout(timer)
  const current = ++revision
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try {
    const data = await getInventoryRows(params(), controller.signal)
    if (current !== revision) return
    rows.value = data.items; total.value = data.total; stamp.value = data.queried_at
    if (page.value > 1 && !rows.value.length && total.value) page.value = Math.ceil(total.value / pageSize.value)
    await nextTick(); listRef.value?.refreshScrollbar()
  } catch { if (current === revision) { rows.value = []; total.value = 0; stamp.value = ''; error.value = '库存数据加载失败，请重试' } }
  finally { if (current === revision) loading.value = false }
}
function scheduleFetch() {
  if (!metadata.value || restoring) return
  ++revision; controller?.abort(); clearTimeout(timer); timer = setTimeout(fetchRows, 300)
}
async function initialize() {
  loading.value = true; error.value = ''
  try { metadata.value = await getInventoryMetadata(); readPreferences(); await nextTick(); await fetchRows() }
  catch { loading.value = false; error.value = '库存报表初始化失败，请重试' }
}
async function findStocks(keyword = '') {
  const current = ++stockRevision; stockLoading.value = true
  try { const data = await getInventoryStocks(keyword, filters.organization_id || undefined); if (current === stockRevision) stocks.value = data.items }
  catch { if (current === stockRevision) stocks.value = [] }
  finally { if (current === stockRevision) stockLoading.value = false }
}
function reset() { Object.assign(filters, {keyword: '', organization_id: null, stock: ''}); custom.value = []; page.value = 1; scheduleFetch() }
const exportColumns = () => grid?.getAllDisplayedColumns().map(column => column.getColId()).filter(key => visible.value.includes(key)) || visible.value
watch(() => filters.organization_id, () => { ++stockRevision; stocks.value = []; stockLoading.value = false; filters.stock = '' })
watch([filters, custom, pageSize], () => { page.value = 1 }, {deep: true, flush: 'sync'})
watch([filters, custom, page, pageSize, sort], scheduleFetch, {deep: true})
onMounted(initialize)
onUnmounted(() => { ++revision; ++stockRevision; controller?.abort(); clearTimeout(timer); grid = null })
</script>

<template>
  <PmsDataList ref="listRef" class="inventory-page" scrollbar-label="即时库存横向滚动条">
    <template #toolbar-left>
      <el-button type="primary" size="small" :icon="Refresh" :disabled="loading" @click="metadata ? fetchRows() : initialize()">刷新</el-button>
      <ReportExportControl v-if="auth.hasPermission('report:inventory:export')" report="inventory" :parameters="params" :columns="exportColumns" :disabled="loading || !total" />
    </template>
    <template #toolbar-right>
      <PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="即时库存列设置" @layout-changed="savePreferences" />
    </template>
    <template #filters>
      <PmsListFilters v-model:filters="custom" :fields="filterFields" :active-count="activeFilters.length">
        <div class="inventory-filter inventory-filter--search"><PmsTextControl v-model="filters.keyword" :prefix-icon="Search" size="compact" clearable placeholder="搜索物料编码、名称、规格型号" aria-label="搜索库存物料" /></div>
        <div class="inventory-filter"><PmsSelectControl v-model="filters.organization_id" :options="metadata?.organizations || []" size="compact" clearable filterable placeholder="全部组织" aria-label="库存组织筛选" /></div>
        <div class="inventory-filter"><PmsSelectControl v-model="filters.stock" :options="stocks" size="compact" clearable filterable remote :remote-method="findStocks" :loading="stockLoading" placeholder="全部仓库" aria-label="库存仓库筛选" @visible-change="(open: boolean) => open && findStocks()" /></div>
        <el-button size="small" @click="reset">重置</el-button>
      </PmsListFilters>
      <div class="inventory-status"><span>共 {{ total }} 条库存明细 · 已显示 {{ visible.length }} / {{ metadata?.fields.length || 10 }} 个字段</span><span>金蝶ERP · YD_JIN_INVENTORY <template v-if="stamp"> · {{ new Date(stamp).toLocaleTimeString('zh-CN', {hour12: false}) }}</template></span></div>
    </template>
    <template #grid>
      <div v-if="error" class="pms-list-load-error" role="alert">{{ error }} <el-button size="small" @click="metadata ? fetchRows() : initialize()">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy"
        :row-data="rows" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS"
        :locale-text="chineseLocaleText" :loading="loading" :pagination="false" :row-height="36" :suppress-multi-sort="true"
        :enable-cell-text-selection="true" @grid-ready="onGridReady" @column-resized="onColumnResized"
        @column-moved="savePreferences" @column-pinned="savePreferences" @sort-changed="onSortChanged"
        @first-data-rendered="listRef?.refreshScrollbar()" @grid-size-changed="listRef?.refreshScrollbar()" />
      <div v-else-if="loading" class="inventory-loading" role="status">正在加载报表…</div>
    </template>
    <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" /></template>
  </PmsDataList>
</template>

<style scoped>
.inventory-filter { width: 160px; }
.inventory-filter--search { width: 260px; }
.inventory-status { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; color: var(--pms-text-secondary); font-size: 12px; padding-bottom: 10px; }
.inventory-loading { padding: 24px; text-align: center; color: var(--pms-text-secondary); }
:deep(.inventory-number) { text-align: right; font-variant-numeric: tabular-nums; }
:deep(.inventory-negative) { color: var(--pms-danger); }
@media (max-width: 600px) { .inventory-filter--search { width: 100%; } }
</style>
