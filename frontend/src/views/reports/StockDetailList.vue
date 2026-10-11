<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, shallowRef, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColumnState, type GridApi, type GridReadyEvent, type RowClickedEvent, type ColumnResizedEvent } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import '@/report-query/query-surface.css'
import { cloneQuery, validateConditions, type QueryCondition } from '@/query-system/core'
import { activeReportConditions, reportFields, reportDefaults, reportScope, reportReference, reportPreferences, serializeReportConditions, createReportRequest, serializeColumnFilters, reportColumnCandidates, linkReportScope, saveReportPreferences, legacyReportSchemes, createReportColumnSort } from '@/query-system/report-adapter'
import { decorateQueryColumns } from '@/query-system/column-grid'
import type { ColumnFilter, ColumnQueryContext } from '@/query-system/column-filters'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import ReportExportControl from '@/components/ReportExportControl.vue'
import { PmsFormDrawer } from '@/form-system'
import { DEFAULT_PAGE_SIZE, PMS_GRID_OPTIONS } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { createDetailSwitch } from '@/utils/detailSwitch'
import { useAuthStore } from '@/stores/auth'
import { getStockDetailMetadata, getStockDetailRows, getStockDetailReference, getStockDetailColumnCandidates, type StockDetailMetadata } from '@/api/stockDetailReport'
import { buildStockDetailQuery, formatStockQuantity, type StockDetailRow, type StockDetailResult } from './stockDetailState'

ModuleRegistry.registerModules([AllCommunityModule])
const auth = useAuthStore()
const today = new Date()
const localDate = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const filters = reactive({ conditions: [] as QueryCondition[], column_filters: [] as ColumnFilter[] })
const metadata = ref<StockDetailMetadata | null>(null)
const pendingPageSize = ref<number | null>(null)
const initializationError = ref(''), initializing = ref(false)
const listRef = ref<InstanceType<typeof PmsDataList>>()
const sort = reactive({ sort: 'bill_date', direction: 'asc' as 'asc' | 'desc' })
function buildQuery(draft: typeof filters, targetPage: number, size: number) {
  const scope = reportScope('stock-detail', draft.conditions)
  return { ...buildStockDetailQuery({ material: String(scope.params.material || ''), organization_ids: scope.params.organization_ids as number[], stock_id: (scope.params.stock_id as number) ?? null, dates: [String(scope.params.start_date || ''), String(scope.params.end_date || '')] }, targetPage, size),
    filters: serializeReportConditions(scope.conditions), column_filters: serializeColumnFilters(draft.column_filters), ...sort }
}
const request = createReportRequest(buildQuery, getStockDetailRows, { items: [], openings: [], total: 0, summary: null } as StockDetailResult, value => { result.value = value })
const result = shallowRef<Readonly<typeof request.value>>(request.value)
const page = computed(() => result.value.applied?.page ?? 1)
const pageSize = computed(() => result.value.applied?.page_size ?? DEFAULT_PAGE_SIZE)
const paginationRevision = ref(0)
const selected = ref<StockDetailRow | null>(null), detailOpen = ref(false)
const detailSwitch = createDetailSwitch<StockDetailRow>(() => Promise.resolve(true), async row => { selected.value = row })
const visible = ref<string[]>([]), savedColumns = ref<ColumnState[]>([])
let grid: GridApi<StockDetailRow> | null = null, restoring = false, disposed = false
const storageKey = computed(() => `pms:stock-detail:v1:${auth.user?.id || 'anonymous'}`)
const fields = computed(() => metadata.value?.fields || [])
const conditions = computed({ get: () => filters.conditions, set: value => { filters.conditions = linkReportScope(value, filters.conditions, 'organization_ids', ['stock_id']) } })
const columnFilters = computed({ get: () => filters.column_filters, set: value => { filters.column_filters = value } })
const referenceScope = (q?: { conditions?: QueryCondition[] }) => {
  const ids = activeReportConditions(q?.conditions || conditions.value).filter(c => c.field === 'organization_ids').flatMap(c => Array.isArray(c.value) ? c.value : [c.value]).filter(v => typeof v === 'number')
  if (!ids.length) throw Error('请先选择库存组织，再选择仓库')
  return { organization_ids: ids }
}
const filterFields = computed(() => reportFields((metadata.value?.query_fields || metadata.value?.filter_fields || []).filter(field => field.field !== 'stock_name'), [
  { field: 'material', label: '物料（必填）', type: 'text', required: true, operators: ['contains'] },
  { field: 'organization_ids', label: '库存组织（必选）', type: 'enum', required: true, options: metadata.value?.organizations || [], operators: ['equals', 'in', 'reference'] },
  { field: 'bill_date', label: '收发日期', type: 'date', required: true, operators: ['between'] },
  { field: 'stock_id', label: '仓库', type: 'text', operators: ['reference'], reference: reportReference('仓库', 'stock_id', 'number', params => getStockDetailReference('stock', params), referenceScope) },
]))
const queryDefaults = reportDefaults(['material', 'organization_ids', 'bill_date', 'stock_id'], { field: 'bill_date', start: localDate(new Date(today.getFullYear(), today.getMonth(), 1)), end: localDate(today) })
const queryInvalid = computed(() => {
  try { buildQuery(filters, 1, pendingPageSize.value ?? pageSize.value) }
  catch (error) { return (error as Error).message }
  return Object.values(validateConditions(activeReportConditions(conditions.value), filterFields.value))[0] || ''
})
const defaultKeys = computed(() => fields.value.map(f => f.key))
const groups = computed(() => [{ key: 'stock-detail', label: '物料收发明细', fields: fields.value.map(f => ({ ...f, value_type: f.type, list_available: true, quick_addable: true })) }])
const numberKeys = new Set(['opening_qty', 'income_qty', 'issue_qty', 'balance_qty'])
const dirty = computed(() => {
  if (!result.value.applied) return false
  try {
    const applied = result.value.applied
    return JSON.stringify(buildQuery(filters, 1, 50)) !== JSON.stringify({ ...applied, page: 1, page_size: 50 })
  } catch { return true }
})
const exportParameters = () => ({ ...result.value.applied!, organization_ids: [...result.value.applied!.organization_ids], page: 1 })
async function beforeExport() {
  if (dirty.value) {
    try { await ElMessageBox.confirm('当前条件尚未查询，将导出上次查询结果。是否继续？', '导出查询结果', { confirmButtonText: '继续导出', cancelButtonText: '取消', type: 'warning' }) }
    catch { return false }
  }
  return !!result.value.applied && !result.value.loading
}
const queryStatus = computed(() => initializing.value ? '正在加载…' : initializationError.value ? '初始化失败' : result.value.loading ? '正在查询…' : result.value.error ? '查询失败' : dirty.value ? '条件已修改，请查询' : result.value.applied ? '已查询' : '尚未查询')
const hasAppliedConditions = computed(() => result.value.applied?.filters !== '[]' && !!result.value.applied?.filters)
const exportColumns = () => fields.value.map(field => field.key)
function text(value: unknown) { return value === null || value === undefined || value === '' ? '' : String(value) }
function fieldText(key: string, value: unknown) { return numberKeys.has(key) ? formatStockQuantity(value) : text(value) }
const columnFields = computed(() => reportFields(metadata.value?.column_filter_fields || []))
const columnContext = (): ColumnQueryContext => ({ fields: () => columnFields.value, filters: () => columnFilters.value,
  ready: () => !!result.value.applied && !result.value.loading,
  sort: createReportColumnSort({ accepted: () => result.value.applied, loading: () => result.value.loading, fields: () => Object.fromEntries((metadata.value?.sort_fields || []).map(key => [key, key])), grid: () => grid,
    changed: value => { Object.assign(sort, value); persist() }, unsupported: () => ElMessage.warning('此列不支持排序'),
    load: params => { closeDetail(); return request.submit(params) },
  }),
  load: (field, keyword, targetPage) => reportColumnCandidates(result.value.applied, field, keyword, targetPage, getStockDetailColumnCandidates),
  apply: (field, filter) => {
    columnFilters.value = [...columnFilters.value.filter(f => f.field !== field), ...(filter ? [filter] : [])]
    if (!result.value.applied || result.value.loading) return
    closeDetail()
    void request.submit({ ...cloneQuery(result.value.applied), page: 1, column_filters: serializeColumnFilters(columnFilters.value) })
  },
})
const columns = computed<ColDef<StockDetailRow>[]>(() => decorateQueryColumns<StockDetailRow>(fields.value.map(field => {
  const definition: ColDef<StockDetailRow> = {
    field: field.key, colId: field.key, headerName: field.label,
    headerTooltip: field.label, initialWidth: field.width, minWidth: 65, maxWidth: 800,
    hide: !visible.value.includes(field.key), initialPinned: numberKeys.has(field.key) ? 'right' : undefined,
    cellClass: numberKeys.has(field.key) ? 'stock-detail-number' : undefined,
    valueFormatter: p => fieldText(field.key, p.value), tooltipValueGetter: p => fieldText(field.key, p.value),
  }
  if (field.key === 'bill_no') definition.cellRenderer = (p: { data?: StockDetailRow; value?: unknown }) => {
    if (!p.data || p.data.row_kind !== 'movement') return ''
    if (!auth.hasPermission('report:stock-detail:view')) return text(p.value)
    const button = document.createElement('button')
    button.className = 'stock-detail-link'; button.type = 'button'; button.textContent = text(p.value)
    button.setAttribute('aria-label', `查看单据 ${text(p.value)}`)
    button.addEventListener('click', event => { event.stopPropagation(); openDetail(p.data!) })
    return button
  }
  return definition
}), columnContext) as ColDef<StockDetailRow>[])
const defaultColDef: ColDef = { editable: false, sortable: false, resizable: true, comparator: () => 0, cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }
function closeDetail() { detailSwitch.invalidate(); detailOpen.value = false; selected.value = null }
function openDetail(row: StockDetailRow) { if (row.row_kind === 'movement') { detailOpen.value = true; void detailSwitch.select(row) } }
function selectRow(row?: StockDetailRow) { if (detailOpen.value && row?.row_kind === 'movement') void detailSwitch.select(row) }
function onRowClicked(event: RowClickedEvent<StockDetailRow>) { selectRow(event.data) }
function onColumnResized(event: ColumnResizedEvent) { if (event.finished) persist() }
function sanitizeColumns(value: unknown): ColumnState[] {
  if (!Array.isArray(value)) return []
  return value.filter(c => c && defaultKeys.value.includes(c.colId)).map(c => ({
    colId: c.colId, width: Math.max(65, Math.min(800, Number(c.width) || 140)),
    pinned: c.pinned === 'left' || c.pinned === 'right' ? c.pinned : null, hide: !visible.value.includes(c.colId),
    sort: metadata.value?.sort_fields?.includes(c.colId) && (c.sort === 'asc' || c.sort === 'desc') ? c.sort : null,
  }))
}
function persist() {
  if (restoring || !metadata.value) return
  savedColumns.value = grid?.getColumnState() || savedColumns.value
  try { saveReportPreferences(localStorage, storageKey.value, { visible: visible.value, columns: savedColumns.value }) }
  catch { ElMessage.warning('设置保存失败，请检查浏览器存储空间') }
  void nextTick(() => listRef.value?.refreshScrollbar())
}
function onGridReady(event: GridReadyEvent<StockDetailRow>) {
  grid = event.api; restoring = true
  if (savedColumns.value.length) grid.applyColumnState({ state: savedColumns.value, applyOrder: true })
  restoring = false
}
async function initialize() {
  initializing.value = true; initializationError.value = ''
  try {
    const data = await getStockDetailMetadata()
    if (disposed) return
    metadata.value = data; visible.value = [...defaultKeys.value]
    if (data.default_sort && data.sort_fields?.includes(data.default_sort.sort)) Object.assign(sort, data.default_sort)
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey.value) || '{}')
      if (Array.isArray(saved.visible)) visible.value = [...new Set(saved.visible.filter((key: unknown) => typeof key === 'string' && defaultKeys.value.includes(key)))] as string[]
      savedColumns.value = sanitizeColumns(saved.columns)
      const sorted = savedColumns.value.find(c => c.sort)
      if (sorted) Object.assign(sort, { sort: sorted.colId, direction: sorted.sort })
    } catch { savedColumns.value = [] }
  } catch { if (!disposed) initializationError.value = '报表初始化失败，请重试' }
  finally { if (!disposed) initializing.value = false }
}
async function query(resetPage = false) {
  if (!metadata.value || result.value.loading) return
  if (queryInvalid.value) { ElMessage.warning(queryInvalid.value); return }
  closeDetail()
  if (await request.query(cloneQuery(filters), resetPage ? 1 : page.value, pendingPageSize.value ?? pageSize.value)) pendingPageSize.value = null
  await nextTick(); listRef.value?.refreshScrollbar()
}
async function paginate(nextPage: number, size = pageSize.value) {
  if (result.value.loading) { ++paginationRevision.value; return }
  closeDetail()
  const pending = request.paginate(nextPage, size)
  // Native select changes its DOM value before a successful page is accepted.
  ++paginationRevision.value
  await pending
  await nextTick(); listRef.value?.refreshScrollbar()
}
async function retry() {
  const isSubmit = request.retryKind === 'submit'
  closeDetail()
  if (await request.retry() && isSubmit) pendingPageSize.value = null
  await nextTick(); listRef.value?.refreshScrollbar()
}
function clearColumnFilters() { columnFilters.value = []; pendingPageSize.value = null; request.invalidate(); closeDetail() }
const planSnapshot = () => ({ pageSize: pendingPageSize.value ?? pageSize.value, visible: [...visible.value], columns: grid?.getColumnState() || savedColumns.value, sort: { ...sort } })
async function submitWorkspace(_value: QueryCondition[], preferences: object = {}) {
  if (queryInvalid.value) { ElMessage.warning(queryInvalid.value); return }
  const plan = reportPreferences(preferences, defaultKeys.value)
  if (plan.sort && metadata.value?.sort_fields?.includes(plan.sort.sort)) Object.assign(sort, plan.sort)
  restoring = true
  if (plan.visible) visible.value = plan.visible
  if (plan.pageSize != null && plan.pageSize !== pageSize.value) pendingPageSize.value = plan.pageSize
  if (plan.columns) { savedColumns.value = sanitizeColumns(plan.columns); await nextTick(); grid?.applyColumnState({ state: savedColumns.value, applyOrder: true }) }
  restoring = false; persist(); await query(true)
}
watch(selected, () => grid?.redrawRows())
watch(columnFilters, () => { grid?.refreshHeader(); grid?.refreshCells({ force: true }) }, { deep: true })
onMounted(initialize)
onUnmounted(() => { disposed = true; request.clear(); detailSwitch.invalidate(); grid = null })
</script>

<template>
  <PmsDataList ref="listRef" class="pms-report-query-surface" scrollbar-label="物料收发明细横向滚动条">
    <template #filters>
      <PmsQueryWorkspace v-model="conditions" list-key="report-stock-detail" :legacy-schemes="legacyReportSchemes" :fields="filterFields" :defaults="queryDefaults" :ready="!!metadata && !initializing" :loading="result.loading" :snapshot="planSnapshot" @query="submitWorkspace" @clear-columns="clearColumnFilters">
      <template #after><div class="pms-query-utilities">
      <span class="pms-report-query-status" role="status">{{ queryStatus }}</span>
      <ReportExportControl v-if="auth.hasPermission('report:stock-detail:export')" report="stock-detail" :parameters="exportParameters" :before-export="beforeExport" :columns="exportColumns" :disabled="result.loading || !result.applied || (!result.total && !result.openings.length)" />
      <PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="物料收发明细列设置" @layout-changed="persist" />
      </div></template>
      </PmsQueryWorkspace>
      <div v-if="hasAppliedConditions" class="stock-detail-scope-note">
        <span>{{ metadata?.summary_scope_note || '完整期间汇总（不随附加条件重算）' }}</span>
        <span>{{ metadata?.opening_scope_note || '期初保留完整查询范围（不随附加条件筛选）' }}</span>
      </div>
      <div v-if="result.summary" class="stock-detail-summary" aria-label="完整查询数量汇总">
        <span class="stock-detail-summary-material">{{ result.summary.material_name }} <span>{{ result.summary.material_code }} · {{ result.summary.unit_name }}</span></span>
        <span>期初<strong>{{ formatStockQuantity(result.summary.opening_qty) }}</strong></span>
        <span>收入<strong>{{ formatStockQuantity(result.summary.income_qty) }}</strong></span>
        <span>发出<strong>{{ formatStockQuantity(result.summary.issue_qty) }}</strong></span>
        <span>期末结存<strong>{{ formatStockQuantity(result.summary.balance_qty) }}</strong></span>
      </div>
      <div v-else-if="result.queried_at && result.openings.length > 1" class="stock-detail-summary">多个库存维度，数量按明细分别展示</div>
    </template>
    <template #grid>
      <div v-if="initializationError || result.error" role="alert" class="pms-list-load-error">{{ initializationError || result.error }} <el-button size="small" :disabled="result.loading || initializing" @click="initializationError ? initialize() : retry()">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy" :row-data="result.items" :pinned-top-row-data="result.openings" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS" :locale-text="chineseLocaleText" :loading="result.loading" :pagination="false" :enable-cell-text-selection="true" :get-row-id="p => p.data.row_id" :get-row-class="p => p.data?.row_id === selected?.row_id ? 'pms-detail-row-active' : ''" @grid-ready="onGridReady" @row-clicked="onRowClicked" @column-resized="onColumnResized" @column-moved="persist" @column-pinned="persist" @grid-size-changed="listRef?.refreshScrollbar()" />
      <div v-else-if="initializing" class="stock-detail-loading" role="status">正在加载报表…</div>
    </template>
    <template #pagination><CustomPagination :key="paginationRevision" :model-value="page" :page-size="pageSize" :total="result.total" @update:model-value="value => paginate(value)" @update:page-size="value => paginate(1, value)" /></template>
  </PmsDataList>
  <PmsFormDrawer v-model="detailOpen" title="收发明细" modal-penetrable aria-modal="false" @closed="closeDetail">
    <dl v-if="selected" class="stock-detail-readonly"><template v-for="field in fields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ fieldText(field.key, selected[field.key]) }}</dd></template></dl>
    <template #footer><el-button @click="closeDetail">关闭</el-button></template>
  </PmsFormDrawer>
</template>

<style scoped>
.stock-detail-loading { padding: 24px; text-align: center; color: var(--pms-text-secondary); }
.stock-detail-scope-note { display: flex; flex-wrap: wrap; gap: 8px 16px; color: var(--pms-text-secondary); font-size: 12px; }
.stock-detail-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; padding: 4px 0; color: var(--pms-text-secondary); font-size: 12px; }
.stock-detail-summary strong { margin-left: 8px; font-weight: 600; color: var(--pms-text); font-variant-numeric: tabular-nums; }
.stock-detail-summary-material { margin-right: auto; color: var(--pms-text); }
.stock-detail-summary-material span { margin-left: 8px; color: var(--pms-text-secondary); }
.stock-detail-readonly { display: grid; grid-template-columns: 100px minmax(0, 1fr); margin: 0; }
.stock-detail-readonly dt, .stock-detail-readonly dd { margin: 0; padding: 12px 0; border-bottom: 1px solid var(--pms-border-soft); overflow-wrap: anywhere; }
.stock-detail-readonly dt { color: var(--pms-text-secondary); }
:deep(.stock-detail-number) { text-align: right; font-variant-numeric: tabular-nums; }
:deep(.stock-detail-link) { border: 0; padding: 0; background: transparent; color: var(--pms-primary); font: inherit; cursor: pointer; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
