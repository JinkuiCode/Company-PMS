<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import ReportExportControl from '@/components/ReportExportControl.vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColumnState, type GridApi, type GridReadyEvent, type ColumnResizedEvent, type SortChangedEvent } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsReportQueryBar from '@/report-query/PmsReportQueryBar.vue'
import PmsReportPlans from '@/report-query/PmsReportPlans.vue'
import { createReportSession, cloneQuery, validateConditions, type ReportCondition, type ReportField } from '@/report-query/state'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import { PmsTextControl, PmsSelectControl } from '@/form-system'
import { DEFAULT_PAGE_SIZE, PMS_GRID_OPTIONS } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'
import { getInventoryMetadata, getInventoryRows, getInventoryStocks, type InventoryField, type InventoryMetadata, type InventoryRow } from '@/api/inventoryReport'

ModuleRegistry.registerModules([AllCommunityModule])
const auth = useAuthStore()
const metadata = ref<InventoryMetadata | null>(null), rows = ref<InventoryRow[]>([])
const emptyDraft = () => ({ keyword: '', organization_id: null as number | null, stock: '', conditions: [] as ReportCondition[] })
const session = reactive(createReportSession(emptyDraft()))
const filters = computed(() => session.draft)
const visible = ref<string[]>([])
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
const pendingPageSize = ref<number | null>(null)
const loading = ref(false), error = ref(''), stamp = ref('')
const stocks = ref<{ value: string; label: string }[]>([]), stockLoading = ref(false)
const sort = reactive({ sort: 'FID', direction: 'asc' })
const listRef = ref<InstanceType<typeof PmsDataList>>()
const plansRef = ref<InstanceType<typeof PmsReportPlans>>()
let grid: GridApi<InventoryRow> | null = null
let savedColumns: ColumnState[] = [], restoring = false, stockRevision = 0
let controller: AbortController | null = null
const storageKey = computed(() => `pms:inventory-report:v1:${auth.user?.id || 'anonymous'}`)
const defaultKeys = computed(() => metadata.value?.fields.map(field => field.key) || [])
const groups = computed(() => [{ key: 'inventory', label: '即时库存', fields: (metadata.value?.fields || []).map(field => ({...field, quick_addable: true})) }])
const filterFields = computed<ReportField[]>(() => (metadata.value?.fields || []).map(field => ({
  field: field.key, label: field.label, type: field.value_type === 'number' ? 'number' : 'text',
})))
const invalid = computed(() => validateConditions(filters.value.conditions,filterFields.value))
const dirty = computed(() => session.dirty || pendingPageSize.value !== null)
const status = computed(() => loading.value ? '正在查询' : error.value ? '查询失败' : dirty.value ? '条件已修改，待查询' : session.applied ? '已查询' : '尚未查询')
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
  field: field.key, colId: field.key, headerName: field.label, headerTooltip: field.label,
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
function onSortChanged(event: SortChangedEvent) {
  if (restoring || event.source === 'api' || event.source === 'gridInitializing') return
  const column = grid?.getColumnState().find(c => c.sort)
  restoring = true
  sort.sort = column?.colId || 'FID'; sort.direction = column?.sort || 'asc'; page.value = 1
  restoring = false; savePreferences(); void fetchRows(false, undefined, true)
}
type Draft = ReturnType<typeof emptyDraft>
const buildParams = (draft: Draft, targetPage = page.value) => ({keyword:draft.keyword, stock:draft.stock, organization_id: draft.organization_id || undefined, ...sort, page:targetPage, page_size:pageSize.value,
  filters:JSON.stringify(draft.conditions.map(({field,operator,value,valueEnd})=>({field,operator,value,valueEnd})))})
const acceptedParams = ref<ReturnType<typeof buildParams> | null>(null)
type FailedRequest = { draft: Draft; request: ReturnType<typeof buildParams>; submit: boolean }
let failedRequest: FailedRequest | null = null
const params = () => cloneQuery(acceptedParams.value!)
async function fetchRows(submit = false, replay?: FailedRequest, applySort = false) {
  if (!metadata.value || (!submit && !session.applied)) return
  if (!replay && submit && invalid.value) return
  const ticket = session.begin(replay?.draft || (submit ? filters.value : session.applied!))
  const request = replay ? cloneQuery(replay.request) : buildParams(ticket.value,submit ? 1 : page.value)
  if (!replay && !submit && !applySort && acceptedParams.value) {
    request.sort = acceptedParams.value.sort; request.direction = acceptedParams.value.direction
  }
  if (!replay && submit && pendingPageSize.value !== null) request.page_size = pendingPageSize.value
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try {
    const data = await getInventoryRows(request, controller.signal)
    if (!session.accept(ticket)) return
    acceptedParams.value = cloneQuery(request)
    failedRequest = null
    rows.value = data.items; total.value = data.total; stamp.value = data.queried_at
    restoring = true; page.value = request.page; pageSize.value = request.page_size; restoring = false
    if (submit) pendingPageSize.value = null
    await nextTick(); listRef.value?.refreshScrollbar()
  } catch { if (session.fail(ticket)) {
    failedRequest = {draft:cloneQuery(ticket.value), request:cloneQuery(request), submit}
    error.value = '库存数据加载失败，请重试'
    if (acceptedParams.value) { restoring = true; page.value = acceptedParams.value.page; pageSize.value = acceptedParams.value.page_size; restoring = false }
  } }
  finally { if (session.fail(ticket)) loading.value = false }
}
function retry() { if (!metadata.value) void initialize(); else if (failedRequest) void fetchRows(failedRequest.submit,failedRequest) }
async function initialize() {
  loading.value = true; error.value = ''
  try { metadata.value = await getInventoryMetadata(); readPreferences(); loading.value = false }
  catch { loading.value = false; error.value = '库存报表初始化失败，请重试' }
}
async function findStocks(keyword = '') {
  const current = ++stockRevision; stockLoading.value = true
  try { const data = await getInventoryStocks(keyword, filters.value.organization_id || undefined); if (current === stockRevision) stocks.value = data.items }
  catch { if (current === stockRevision) stocks.value = [] }
  finally { if (current === stockRevision) stockLoading.value = false }
}
function invalidate() { session.invalidate(); controller?.abort(); loading.value = false; failedRequest = null }
function reset() { invalidate(); session.restore(emptyDraft()); pendingPageSize.value = null; plansRef.value?.clearSelection(); error.value = '' }
function planSnapshot() { return { draft:cloneQuery(filters.value), visible:[...visible.value], columns:grid?.getColumnState() || savedColumns, pageSize:pendingPageSize.value ?? pageSize.value } }
function restorePlan(value: unknown) {
  const plan = value as ReturnType<typeof planSnapshot>
  if (!plan?.draft || typeof plan.draft.keyword !== 'string' || typeof plan.draft.stock !== 'string' ||
      !Array.isArray(plan.draft.conditions) || validateConditions(plan.draft.conditions,filterFields.value) ||
      (plan.draft.organization_id != null && !metadata.value?.organizations.some(o=>o.value === plan.draft.organization_id)) ||
      !Array.isArray(plan.visible) || !plan.visible.length || plan.visible.some(k=>!defaultKeys.value.includes(k)) ||
      !Array.isArray(plan.columns) || plan.columns.some(c=>!c || !defaultKeys.value.includes(c.colId)) ||
      !Number.isInteger(plan.pageSize) || plan.pageSize < 1 || plan.pageSize > 500) {
    ElMessage.error('方案字段或组织已失效，未应用，请重新保存'); return
  }
  invalidate(); session.restore(plan.draft)
  visible.value = [...plan.visible]; restoring = true; pendingPageSize.value = plan.pageSize
  grid?.applyColumnState({state:plan.columns,applyOrder:true})
  const sorted = plan.columns.find(c=>c.sort)
  sort.sort = sorted?.colId || 'FID'; sort.direction = sorted?.sort || 'asc'
  restoring = false
  savePreferences()
}
async function confirmExport() {
  if (dirty.value) {
    try { await ElMessageBox.confirm('当前条件尚未查询，将导出上次查询结果。是否继续？','导出查询结果',{confirmButtonText:'继续导出',cancelButtonText:'取消',type:'warning'}) }
    catch { return false }
  }
  return true
}
const exportColumns = () => grid?.getAllDisplayedColumns().map(column => column.getColId()).filter(key => visible.value.includes(key)) || visible.value
watch(() => filters.value.organization_id, () => { ++stockRevision; stocks.value = []; stockLoading.value = false })
watch(page, () => { if (!restoring) void fetchRows() }, {flush:'sync'})
watch(pageSize, () => { if (!restoring) { restoring = true; page.value = 1; restoring = false; void fetchRows() } }, {flush:'sync'})
onMounted(initialize)
onUnmounted(() => { invalidate(); ++stockRevision; grid = null })
</script>

<template>
  <PmsDataList ref="listRef" class="inventory-page pms-report-query-surface" scrollbar-label="即时库存横向滚动条">
    <template #toolbar-left>
      <PmsReportPlans ref="plansRef" :storage-key="`${storageKey}:plans:v1`" :snapshot="planSnapshot" :disabled="!metadata" @restore="restorePlan" />
    </template>
    <template #toolbar-right>
      <span class="pms-report-query-status" :class="{'is-dirty':dirty}" role="status">{{ status }}<template v-if="stamp"> · {{ new Date(stamp).toLocaleTimeString('zh-CN', {hour12:false}) }}</template></span>
      <ReportExportControl v-if="auth.hasPermission('report:inventory:export')" report="inventory" :parameters="params" :columns="exportColumns" :before-export="confirmExport" :disabled="loading || !session.applied || !total" />
      <PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="即时库存列设置" @layout-changed="savePreferences" />
    </template>
    <template #filters>
      <PmsReportQueryBar v-model:conditions="filters.conditions" :fields="filterFields" :loading="loading" :disabled="!metadata" :invalid="invalid" @query="fetchRows(true)" @reset="reset">
        <div class="query-material"><PmsTextControl v-model="filters.keyword" :prefix-icon="Search" size="compact" clearable placeholder="物料编码 / 名称 / 规格" aria-label="搜索库存物料" /></div>
        <PmsSelectControl v-model="filters.organization_id" :options="metadata?.organizations || []" size="compact" clearable filterable placeholder="全部授权组织" aria-label="库存组织筛选" @update:model-value="filters.stock = ''" />
        <PmsSelectControl v-model="filters.stock" :options="stocks" size="compact" clearable filterable remote :remote-method="findStocks" :loading="stockLoading" placeholder="全部仓库" aria-label="库存仓库筛选" @visible-change="(open: boolean) => open && findStocks()" />
      </PmsReportQueryBar>
    </template>
    <template #grid>
      <div v-if="error" class="pms-list-load-error" role="alert">{{ error }}<span v-if="session.applied">，下方保留上次查询结果</span> <el-button size="small" @click="retry">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy"
        :row-data="rows" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS"
        :locale-text="chineseLocaleText" :loading="loading" :pagination="false" :row-height="36" :suppress-multi-sort="true"
        :overlay-no-rows-template="session.applied ? '<span>没有符合条件的数据</span>' : '<span>设置条件后，点击查询</span>'"
        :enable-cell-text-selection="true" @grid-ready="onGridReady" @column-resized="onColumnResized"
        @column-moved="savePreferences" @column-pinned="savePreferences" @sort-changed="onSortChanged"
        @first-data-rendered="listRef?.refreshScrollbar()" @grid-size-changed="listRef?.refreshScrollbar()" />
      <div v-else-if="loading" class="inventory-loading" role="status">正在加载报表…</div>
    </template>
    <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" /></template>
  </PmsDataList>
</template>

<style scoped>
.inventory-loading { padding: 24px; text-align: center; color: var(--pms-text-secondary); }
:deep(.inventory-number) { text-align: right; font-variant-numeric: tabular-nums; }
:deep(.inventory-negative) { color: var(--pms-danger); }
</style>
