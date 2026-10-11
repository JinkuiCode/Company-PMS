<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ReportExportControl from '@/components/ReportExportControl.vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColumnState, type GridApi, type GridReadyEvent, type ColumnResizedEvent, type SortChangedEvent } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import { createReportSession } from '@/report-query/state'
import { cloneQuery, validateConditions, type QueryCondition, type QueryField } from '@/query-system/core'
import { activeReportConditions, reportFields, reportDefaults, reportScope, reportPreferences, serializeReportConditions, serializeColumnFilters, reportColumnCandidates, linkReportScope, legacyReportSchemes, createReportColumnSort } from '@/query-system/report-adapter'
import { decorateQueryColumns } from '@/query-system/column-grid'
import type { ColumnFilter, ColumnQueryContext } from '@/query-system/column-filters'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import { DEFAULT_PAGE_SIZE, PMS_GRID_OPTIONS } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'
import { getInventoryMetadata, getInventoryRows, getInventoryColumnCandidates, type InventoryField, type InventoryMetadata, type InventoryRow } from '@/api/inventoryReport'

ModuleRegistry.registerModules([AllCommunityModule])
const auth = useAuthStore()
const metadata = ref<InventoryMetadata | null>(null), rows = ref<InventoryRow[]>([])
const emptyDraft = () => ({ conditions: [] as QueryCondition[], column_filters: [] as ColumnFilter[] })
const session = reactive(createReportSession(emptyDraft()))
const filters = computed(() => session.draft)
const visible = ref<string[]>([])
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
const pendingPageSize = ref<number | null>(null)
const loading = ref(false), error = ref(''), stamp = ref('')
const sort = reactive({ sort: 'FID', direction: 'asc' })
const listRef = ref<InstanceType<typeof PmsDataList>>()
let grid: GridApi<InventoryRow> | null = null
let savedColumns: ColumnState[] = [], restoring = false
let controller: AbortController | null = null
const storageKey = computed(() => `pms:inventory-report:v1:${auth.user?.id || 'anonymous'}`)
const defaultKeys = computed(() => metadata.value?.fields.map(field => field.key) || [])
const groups = computed(() => [{ key: 'inventory', label: '即时库存', fields: (metadata.value?.fields || []).map(field => ({...field, quick_addable: true})) }])
const conditions = computed({ get: () => filters.value.conditions, set: value => { filters.value.conditions = linkReportScope(value, filters.value.conditions, 'organization_id', ['Stock']) } })
const columnFilters = computed({ get: () => filters.value.column_filters, set: value => { filters.value.column_filters = value } })
const filterFields = computed(() => reportFields(metadata.value?.query_fields || (metadata.value?.fields || []).map<QueryField>(field => ({
  field: field.key, label: field.label, type: field.value_type === 'number' ? 'number' : 'text',
})), [
  { field: 'keyword', label: '物料编码 / 名称 / 规格', type: 'text', operators: ['contains'] },
  { field: 'organization_id', label: '库存组织', type: 'enum', options: metadata.value?.organizations || [], operators: ['equals', 'reference'] },
  { field: 'Stock', label: '仓库', type: 'text' },
]))
const queryDefaults = reportDefaults(['keyword', 'organization_id', 'Stock'])
const invalid = computed(() => { try { reportScope('inventory', conditions.value); return Object.values(validateConditions(activeReportConditions(conditions.value), filterFields.value))[0] || '' } catch (error) { return (error as Error).message } })
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
const columnFields = computed(() => reportFields(metadata.value?.column_filter_fields || []))
const columnContext = (): ColumnQueryContext => ({ fields: () => columnFields.value, filters: () => columnFilters.value,
  ready: () => !!acceptedParams.value && !loading.value,
  sort: createReportColumnSort({ accepted: () => acceptedParams.value, loading: () => loading.value, fields: () => Object.fromEntries(defaultKeys.value.map(key => [key, key])), grid: () => grid,
    changed: value => { Object.assign(sort, value); savePreferences() }, unsupported: () => ElMessage.warning('此列不支持排序'),
    load: request => fetchRows(false, { draft: cloneQuery(session.applied!), request, submit: false }),
  }),
  load: (field, keyword, targetPage) => reportColumnCandidates(acceptedParams.value, field, keyword, targetPage, getInventoryColumnCandidates),
  apply: (field, filter) => {
    columnFilters.value = [...columnFilters.value.filter(f => f.field !== field), ...(filter ? [filter] : [])]
    if (!acceptedParams.value || !session.applied || loading.value) return
    const draft = cloneQuery(session.applied); draft.column_filters = cloneQuery(columnFilters.value)
    const request = { ...cloneQuery(acceptedParams.value), page: 1, column_filters: serializeColumnFilters(columnFilters.value) }
    void fetchRows(true, { draft, request, submit: true })
  },
})
const columns = computed<ColDef<InventoryRow>[]>(() => decorateQueryColumns<InventoryRow>((metadata.value?.fields || []).map(field => ({
  field: field.key, colId: field.key, headerName: field.label, headerTooltip: field.label,
  initialWidth: field.width, minWidth: 80, maxWidth: 800, hide: !visible.value.includes(field.key),
  cellClass: field.value_type === 'number' ? 'inventory-number' : undefined,
  cellClassRules: field.value_type === 'number' ? {'inventory-negative': p => Number(p.value) < 0} : undefined,
  valueFormatter: params => display(params.data, field), tooltipValueGetter: params => display(params.data, field),
})), columnContext) as ColDef<InventoryRow>[])
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
const buildParams = (draft: Draft, targetPage = page.value) => {
  const scope = reportScope('inventory', draft.conditions)
  return { ...scope.params, ...sort, page: targetPage, page_size: pageSize.value, filters: serializeReportConditions(scope.conditions), column_filters: serializeColumnFilters(draft.column_filters) }
}
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
function invalidate() { session.invalidate(); controller?.abort(); loading.value = false; failedRequest = null }
function clearColumnFilters() { columnFilters.value = []; invalidate() }
function planSnapshot() { return { visible:[...visible.value], columns:grid?.getColumnState() || savedColumns, pageSize:pendingPageSize.value ?? pageSize.value, sort: { ...sort } } }
async function submitWorkspace(_value: QueryCondition[], preferences: object = {}) {
  if (invalid.value) { ElMessage.warning(invalid.value); return }
  const plan = reportPreferences(preferences, defaultKeys.value)
  restoring = true
  if (plan.visible) visible.value = plan.visible
  if (plan.pageSize != null && plan.pageSize !== pageSize.value) pendingPageSize.value = plan.pageSize
  if (plan.columns) { savedColumns = plan.columns as ColumnState[]; await nextTick(); grid?.applyColumnState({ state: savedColumns, applyOrder: true }) }
  const sorted = grid?.getColumnState().find(c => c.sort)
  if (plan.sort && (plan.sort.sort === 'FID' || defaultKeys.value.includes(plan.sort.sort))) Object.assign(sort, plan.sort)
  else if (sorted) { sort.sort = sorted.colId; sort.direction = sorted.sort! }
  restoring = false; savePreferences(); await fetchRows(true)
}
async function confirmExport() {
  if (dirty.value) {
    try { await ElMessageBox.confirm('当前条件尚未查询，将导出上次查询结果。是否继续？','导出查询结果',{confirmButtonText:'继续导出',cancelButtonText:'取消',type:'warning'}) }
    catch { return false }
  }
  return true
}
const exportColumns = () => grid?.getAllDisplayedColumns().map(column => column.getColId()).filter(key => visible.value.includes(key)) || visible.value
watch(page, () => { if (!restoring) void fetchRows() }, {flush:'sync'})
watch(columnFilters, () => { grid?.refreshHeader(); grid?.refreshCells({ force: true }) }, { deep: true })
watch(pageSize, () => { if (!restoring) { restoring = true; page.value = 1; restoring = false; void fetchRows() } }, {flush:'sync'})
onMounted(initialize)
onUnmounted(() => { invalidate(); grid = null })
</script>

<template>
  <PmsDataList ref="listRef" class="inventory-page pms-report-query-surface" scrollbar-label="即时库存横向滚动条">
    <template #filters>
      <PmsQueryWorkspace v-model="conditions" list-key="report-inventory" :legacy-schemes="legacyReportSchemes" :fields="filterFields" :defaults="queryDefaults" :ready="!!metadata" :loading="loading" :snapshot="planSnapshot" @query="submitWorkspace" @clear-columns="clearColumnFilters">
      <template #after><div class="pms-query-utilities">
      <span class="pms-report-query-status" :class="{'is-dirty':dirty}" role="status">{{ status }}<template v-if="stamp"> · {{ new Date(stamp).toLocaleTimeString('zh-CN', {hour12:false}) }}</template></span>
      <ReportExportControl v-if="auth.hasPermission('report:inventory:export')" report="inventory" :parameters="params" :columns="exportColumns" :before-export="confirmExport" :disabled="loading || !session.applied || !total" />
      <PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="即时库存列设置" @layout-changed="savePreferences" />
      </div></template>
      </PmsQueryWorkspace>
    </template>
    <template #grid>
      <div v-if="error" class="pms-list-load-error" role="alert">{{ error }}<span v-if="session.applied">，下方保留上次查询结果</span> <el-button size="small" @click="retry">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy"
        :row-data="rows" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS"
        :locale-text="chineseLocaleText" :loading="loading" :pagination="false" :suppress-multi-sort="true"
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
