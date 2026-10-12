<script setup lang="ts">
import { computed, defineComponent, h, nextTick, onMounted, onUnmounted, reactive, ref, shallowRef, watch } from 'vue'
import { ElButton, ElMessage, ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColGroupDef, type ColumnState, type GridApi, type GridReadyEvent, type RowClickedEvent, type ColumnResizedEvent, type CellFocusedEvent, type SortChangedEvent } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import { cloneQuery, validateConditions, type QueryCondition } from '@/query-system/core'
import { activeReportConditions, reportFields, reportDefaults, reportScope, reportReference, purchaseReferenceScope, reportPreferences, serializeReportConditions, purchaseConditions, selectReportProgress, withReportProgress, linkReportScope, saveReportPreferences, legacyReportSchemes, purchaseDetailEntry, createReportColumnSort } from '@/query-system/report-adapter'
import { decorateQueryColumns } from '@/query-system/column-grid'
import type { ColumnFilter, ColumnQueryContext } from '@/query-system/column-filters'
import { usePageColumnFilter } from '@/query-system/page-column-filter'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import { migrateReportIdentity, reportIdentityVersion } from './report-identity-layout'
import CustomPagination from '@/components/CustomPagination.vue'
import { DEFAULT_PAGE_SIZE, PMS_ACTION_COLUMN, PMS_GRID_OPTIONS } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'
import { getPurchaseMetadata, getPurchaseRows, getPurchaseDetail, getPurchaseProjectReference, type PurchaseField, type PurchaseRow, type PurchaseDocument, type PurchaseMetadata, type PurchaseDetail, type PurchaseDetailEntry } from '@/api/purchaseReport'
import ReportExportControl from '@/components/ReportExportControl.vue'
import { createPurchaseDetailState, type PurchaseDetailState } from './purchaseDetailState'

ModuleRegistry.registerModules([AllCommunityModule])
const props = defineProps<{ entry?: PurchaseDetailEntry; active?: boolean }>()
const emit = defineEmits<{ overview: [] }>()
const projectScope = ref<PurchaseDetailEntry['scope']>()
const appliedProjectScope = ref<PurchaseDetailEntry['scope']>()
const auth = useAuthStore()
const queryDraft = ref<QueryCondition[]>([]), columnFilters = ref<ColumnFilter[]>([])
const conditions = computed({ get: () => queryDraft.value, set: value => { queryDraft.value = linkReportScope(value, queryDraft.value, 'organization_ids', ['project_code', 'project_name']) } })
const referenceScope = (q?: { conditions?: QueryCondition[]; line?: number | null }) => {
  return purchaseReferenceScope(q)
}
const projectReference = () => ({ ...reportReference('项目档案', 'id', 'number', getPurchaseProjectReference, referenceScope), lineOptions: () => metadata.value?.organizations || [] })
const filterFields = computed(() => reportFields((metadata.value?.query_fields || metadata.value?.filter_fields || []).filter(field => field.field !== 'project_name'), [
  { field: 'keyword', label: '申请单 / 物料 / 规格', type: 'text', operators: ['contains'] },
  { field: 'organization_ids', label: '产品线', type: 'enum', options: metadata.value?.organizations || [], operators: ['equals', 'in', 'reference'] },
  { field: 'project_code', label: '项目编码', type: 'text', reference: projectReference() },
  { field: 'supplier_name', label: '供应商', type: 'text' },
]))
const queryDefaults = reportDefaults(['keyword', 'organization_ids', 'project_code', 'application_date', 'supplier_name'])
const invalid = computed(() => { try { reportScope('purchase', conditions.value); return Object.values(validateConditions(activeReportConditions(conditions.value), filterFields.value))[0] || '' } catch (error) { return (error as Error).message } })
const progressOptions = computed(() => Object.entries(metadata.value?.progress_labels || {}).map(([value, label]) => ({ value, label })))
const selectedProgress = computed(() => selectReportProgress(conditions.value, progressOptions.value.map(option => option.value)))
function chooseProgress(value: string) {
  if (!metadata.value || loading.value) return
  conditions.value = withReportProgress(conditions.value, value)
  void fetchRows(true)
}
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
const rows = ref<PurchaseRow[]>([]), metadata = ref<PurchaseMetadata | null>(null)
const loading = ref(false), error = ref(''), stamp = ref('')
const listRef = ref<InstanceType<typeof PmsDataList>>()
let grid: GridApi<PurchaseRow> | null = null
const visible = ref<string[]>([])
const sort = reactive({ sort: 'date', direction: 'desc' })
const sortFields: Record<string, string> = { application_date: 'date', bill_no: 'bill_no', project_code: 'project_code', material_code: 'material_code' }
const detailState = shallowRef<Readonly<PurchaseDetailState<PurchaseDetail>>>({ open: false, requestId: null, orderId: null, loading: false, data: null, error: null })
const detail = createPurchaseDetailState(getPurchaseDetail, state => { detailState.value = state; grid?.redrawRows() })
const activeRow = computed(() => rows.value.find(row => String(row.id) === detailState.value.requestId))
const receipts = computed(() => (detailState.value.data?.receipts || []).filter(row => !detailState.value.orderId || String(row.order_id) === detailState.value.orderId))
const selectedOrder = computed(() => detailState.value.data?.orders.find(row => String(row.id) === detailState.value.orderId))
const projectPrefix = ['product_line_name', 'project_code']
const fields = computed(() => {
  const available = (metadata.value?.fields || []).filter(field => field.key !== 'project_name')
  return [...projectPrefix.flatMap(key => available.filter(field => field.key === key)), ...available.filter(field => !projectPrefix.includes(field.key))]
})
const defaultKeys = [...projectPrefix, 'material_name', 'unit_name', 'bill_no', 'line_no', 'application_date', 'document_status', 'requested', 'approved', 'last_order_date', 'ordered', 'supplier_name', 'last_stock_date', 'net_received', 'pending_order', 'pending_receipt', 'progress']
const groups = computed(() => [...new Set(fields.value.map(field => field.group))].map(group => ({
  key: group, label: group, fields: fields.value.filter(field => field.group === group).map(field => ({ ...field, quick_addable: true })),
})))
const storageKey = computed(() => `pms:purchase-report:v1:${auth.user?.id || 'anonymous'}`)
let savedColumns: ColumnState[] = [], restoring = false
function readPreferences() {
  try {
    const raw = JSON.parse(localStorage.getItem(storageKey.value) || '{}')
    const saved = migrateReportIdentity(raw)
    const keys = new Set(fields.value.map(field => field.key))
    visible.value = Array.isArray(saved.visible) ? saved.visible.filter((key: string) => keys.has(key)) : [...defaultKeys]
    savedColumns = Array.isArray(saved.columns) ? saved.columns.filter((column: ColumnState) => keys.has(column.colId) || column.colId === 'purchase_actions') : []
    const sorting = savedColumns.find(column => column.sort && sortFields[column.colId])
    if (saved.sort && Object.values(sortFields).includes(saved.sort.sort)) Object.assign(sort, saved.sort)
    else if (sorting) Object.assign(sort, { sort: sortFields[sorting.colId], direction: sorting.sort })
    if (raw.reportIdentityVersion !== 1) savePreferences()
  } catch { visible.value = [...defaultKeys]; savedColumns = [] }
}
function savePreferences() {
  if (restoring || !reportIdentityVersion(fields.value)) return
  try { saveReportPreferences(localStorage, storageKey.value, { visible: visible.value, columns: grid?.getColumnState() || savedColumns, sort: { ...sort }, reportIdentityVersion: 1 }) }
  catch { ElMessage.warning('本机设置保存失败，请检查浏览器存储空间') }
  void nextTick(() => listRef.value?.refreshScrollbar())
}
const planSnapshot = () => ({ reportIdentityVersion: reportIdentityVersion(fields.value), pageSize: pendingPageSize.value ?? pageSize.value, columns: grid?.getColumnState() || savedColumns, visible: [...visible.value], scope: cloneQuery(projectScope.value || null), sort: { ...sort } })
function clearColumnFilters() { pageColumns.clear(); invalidate() }
async function submitWorkspace(_value: QueryCondition[], preferences: object = {}) {
  if (invalid.value) { ElMessage.warning(invalid.value); return }
  const plan = reportPreferences(migrateReportIdentity(preferences), fields.value.map(f => f.key))
  if (plan.scope !== undefined) projectScope.value = plan.scope || undefined
  restoring = true
  if (plan.pageSize != null && plan.pageSize !== pageSize.value) pendingPageSize.value = plan.pageSize
  if (plan.visible) visible.value = plan.visible
  if (plan.columns) { savedColumns = plan.columns as ColumnState[]; await nextTick(); grid?.applyColumnState({ state: savedColumns, applyOrder: true }) }
  const sorting = grid?.getColumnState().find(c => c.sort && sortFields[c.colId])
  if (plan.sort && Object.values(sortFields).includes(plan.sort.sort)) Object.assign(sort, plan.sort)
  else if (sorting) Object.assign(sort, { sort: sortFields[sorting.colId], direction: sorting.sort })
  restoring = false; savePreferences(); await fetchRows(true)
}
const number = (value: unknown) => value === null || value === undefined || value === '' ? '-' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 8 }).format(Number(value))
const date = (value: unknown) => value ? String(value).slice(0, 10) : '-'
function display(row: PurchaseRow, field: PurchaseField) {
  if (field.key === 'document_status') return metadata.value?.document_status_labels[String(row[field.key])] || '未知状态'
  if (field.key === 'close_status') return row[field.key] === 'A' ? '未关闭' : row[field.key] === 'B' ? '已关闭' : '-'
  return field.value_type === 'number' ? number(row[field.key]) : field.value_type === 'date' ? date(row[field.key]) : String(row[field.key] ?? '-')
}
const tone = (progress: string) => progress === 'complete' ? 'success' : progress === 'review' ? 'danger' : progress === 'ordering' ? 'warning' : 'info'
const Actions = defineComponent({ props: ['params'], setup(props) { return () => h(ElButton, { size: 'small', link: true, type: 'primary', onClick: () => void detail.open(String(props.params.data.id)) }, () => '明细') } })
const Progress = defineComponent({ props: ['params'], setup(props) { return () => h('span', { class: ['pms-status', tone(props.params.data.progress)] }, props.params.data.progress_label) } })
const columnFields = computed(() => reportFields(metadata.value?.column_filter_fields || []).filter(f => f.field !== 'project_name' && f.operators?.join() !== 'reference'))
const pageColumns = usePageColumnFilter(rows, () => columnFields.value, columnFilters, () => [page.value, pageSize.value], undefined, () => !!acceptedParams.value && !loading.value)
const visibleRows = pageColumns.visibleRows
const columnContext = (): ColumnQueryContext => ({ ...pageColumns.context,
  ready: () => !!acceptedParams.value && !loading.value,
  sort: createReportColumnSort({ accepted: () => acceptedParams.value, loading: () => loading.value, fields: () => sortFields, grid: () => grid,
    changed: value => { Object.assign(sort, value); savePreferences() }, unsupported: () => ElMessage.warning('此列不支持排序'),
    load: params => fetchRows(false, { draft: cloneQuery(applied.value!), params, submit: false, scope: appliedProjectScope.value }),
  }),
})
const columns = computed<(ColDef<PurchaseRow> | ColGroupDef<PurchaseRow>)[]>(() => decorateQueryColumns<PurchaseRow>([
  ...groups.value.map(group => ({ headerName: group.label, groupId: group.key, children: group.fields.map(field => ({
    field: field.key, colId: field.key, headerName: field.label, headerTooltip: field.label,
    initialWidth: field.key === 'material_name' || field.key === 'specification' ? 180 : field.value_type === 'number' ? 125 : 136,
    initialPinned: projectPrefix.includes(field.key) ? 'left' as const : field.key === 'progress' ? 'right' as const : undefined,
    hide: !visible.value.includes(field.key), minWidth: 80, maxWidth: 800,
    sortable: Boolean(sortFields[field.key]),
    cellClass: field.value_type === 'number' ? 'purchase-number' : undefined,
    valueFormatter: (params: { data?: PurchaseRow }) => params.data ? display(params.data, field) : '',
    tooltipValueGetter: (params: { data?: PurchaseRow }) => params.data ? display(params.data, field) : '',
    cellRenderer: field.key === 'progress' ? Progress : undefined,
  })) })),
  { colId: 'purchase_actions', headerName: '操作', pinned: 'right', lockPosition: 'right', ...PMS_ACTION_COLUMN, cellRenderer: Actions, cellClass: 'pms-action-cell' },
], columnContext))
const defaultColDef: ColDef = { resizable: true, sortable: false, comparator:()=>0, editable: false, cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }
function onGridReady(event: GridReadyEvent<PurchaseRow>) {
  grid = event.api
  if (savedColumns.length) { restoring = true; grid.applyColumnState({ state: savedColumns, applyOrder: true }); restoring = false }
  listRef.value?.refreshScrollbar()
}
function onCellFocus(event: CellFocusedEvent) {
  if (event.rowIndex === null) return
  const row = grid?.getDisplayedRowAtIndex(event.rowIndex)?.data
  if (row) void detail.selectRow(String(row.id))
}
function onRowClicked(event: RowClickedEvent<PurchaseRow>) { if (event.data) void detail.selectRow(String(event.data.id)) }
function onColumnResized(event: ColumnResizedEvent) { if (event.finished) savePreferences() }
function onSortChanged(event: SortChangedEvent) {
  if (restoring || event.source === 'api' || event.source === 'gridInitializing') return
  const column = grid?.getColumnState().find(state => state.sort && sortFields[state.colId])
  Object.assign(sort, { sort: column ? sortFields[column.colId] : 'date', direction: column?.sort || 'desc' })
  restoring = true; page.value = 1; restoring = false; savePreferences(); void fetchRows(false, undefined, true)
}
let revision = 0, controller: AbortController | null = null
const draftSnapshot = () => {
  const scope = reportScope('purchase', conditions.value)
  return { keyword: String(scope.params.keyword || ''), project_code: '', supplier: String(scope.params.supplier || ''), progress: '', organization_ids: (scope.params.organization_ids as number[]) || [], dates: [] as string[], conditions: scope.conditions, column_filters: [] as ColumnFilter[] }
}
type Draft = ReturnType<typeof draftSnapshot>
const applied = ref<Draft | null>(null), pendingPageSize = ref<number | null>(null)
const dirty = computed(() => { if (!applied.value) return false; try { return JSON.stringify(draftSnapshot()) !== JSON.stringify(applied.value) || JSON.stringify(projectScope.value || null) !== JSON.stringify(appliedProjectScope.value || null) || pendingPageSize.value !== null } catch { return true } })
const resultScopeLabel = computed(() => appliedProjectScope.value ? `${appliedProjectScope.value.product_line_name} · ${appliedProjectScope.value.project_code || '未关联项目'}` : applied.value?.project_code ? `项目编码 ${applied.value.project_code}` : '当前查询范围全部项目')
const buildParams = (draft:Draft, submit:boolean) => ({...draft,...sort,
  ...(projectScope.value ? {project_code:projectScope.value.project_code,organization_ids:[projectScope.value.organization_id]} : {}),
  project_code_is_empty: !!projectScope.value && !projectScope.value.project_code,
  dates:undefined, conditions:undefined, date_from:draft.dates[0] || undefined,date_to:draft.dates[1] || undefined,filters:serializeReportConditions(draft.conditions),column_filters: '[]',page:submit?1:page.value,page_size:submit?(pendingPageSize.value??pageSize.value):pageSize.value})
const acceptedParams = ref<ReturnType<typeof buildParams> | null>(null)
type RequestSnapshot = {draft:Draft; params:ReturnType<typeof buildParams>; submit:boolean; scope:PurchaseDetailEntry['scope']}
let failedRequest: RequestSnapshot | null = null
const params = () => cloneQuery(acceptedParams.value!)
function invalidate() { ++revision; controller?.abort(); loading.value=false; failedRequest=null }
async function confirmExport() {
  if (dirty.value) { try { await ElMessageBox.confirm('当前条件尚未查询，将导出上次查询结果。是否继续？','导出查询结果',{confirmButtonText:'继续导出',cancelButtonText:'取消',type:'warning'}) } catch { return false } }
  return true
}
function retry() { if (!metadata.value) void initialize(); else if (failedRequest) void fetchRows(failedRequest.submit,failedRequest) }
async function fetchRows(submit = false, replay?:RequestSnapshot, applySort = false) {
  if (!metadata.value || (!submit && !applied.value)) return
  if (!replay && submit && invalid.value) return
  pageColumns.clear()
  const draft = cloneQuery(replay?.draft || (submit?draftSnapshot():applied.value!))
  const scope = replay ? replay.scope : submit ? projectScope.value : appliedProjectScope.value
  const request = replay?cloneQuery(replay.params):buildParams(draft,submit)
  if (!replay && !submit && !applySort && acceptedParams.value) {
    request.sort = acceptedParams.value.sort; request.direction = acceptedParams.value.direction
  }
  if (!replay && !submit && acceptedParams.value) {
    request.project_code = acceptedParams.value.project_code; request.organization_ids = [...acceptedParams.value.organization_ids]
    request.project_code_is_empty = acceptedParams.value.project_code_is_empty
  }
  const current = ++revision
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try {
    const data = await getPurchaseRows(request, controller.signal)
    if (current !== revision) return
    rows.value = data.items; total.value = data.total; stamp.value = data.queried_at
    applied.value=draft; appliedProjectScope.value=scope ? cloneQuery(scope) : undefined; acceptedParams.value=cloneQuery(request); failedRequest=null
    restoring=true; page.value=request.page; pageSize.value=request.page_size; restoring=false
    if(submit) pendingPageSize.value=null
    detail.reconcileRows(rows.value.map(row => String(row.id)))
    await nextTick(); listRef.value?.refreshScrollbar()
  } catch { if (current === revision) {
    failedRequest={draft,params:cloneQuery(request),submit,scope:scope ? cloneQuery(scope) : undefined}; error.value='采购数据加载失败，请重试'
    if(acceptedParams.value) { restoring=true; page.value=acceptedParams.value.page; pageSize.value=acceptedParams.value.page_size; restoring=false }
  } }
  finally { if (current === revision) loading.value = false }
}
async function initialize() {
  loading.value = true; error.value = ''
  try { metadata.value = await getPurchaseMetadata(); readPreferences(); await nextTick(); loading.value=false; await applyEntry() }
  catch { error.value = '报表初始化失败，请重试'; loading.value = false }
}
async function applyEntry() {
  if (!metadata.value || !props.entry) return
  const entry = purchaseDetailEntry(props.entry.draft, filterFields.value, props.entry.scope, props.entry.progress)
  invalidate(); detail.close(); projectScope.value = entry.scope
  const value = entry.draft
  if (!value) { pageColumns.clear(); projectScope.value = undefined; return }
  conditions.value = purchaseConditions(value); pageColumns.clear()
  if (projectScope.value) conditions.value = conditions.value.filter(c => c.field !== 'organization_ids')
  if (entry.progress) conditions.value = withReportProgress(conditions.value, entry.progress)
  await fetchRows(true)
}
function clearProjectScope() { projectScope.value = undefined; void fetchRows(true) }
watch(() => props.entry, () => { void applyEntry() })
watch(() => props.active, value => { if (value === false) { invalidate(); detail.close() } else void nextTick(() => listRef.value?.refreshScrollbar()) })
const exportColumns = () => grid?.getAllDisplayedColumns().map(column => column.getColId()).filter(key => visible.value.includes(key)) || visible.value
function stateLabel(row: PurchaseDocument) { return row.cancel_status === 'B' ? '已作废' : metadata.value?.document_status_labels[row.document_status] || '未知状态' }
function orderLabel(id?: number) { const order = detailState.value.data?.orders.find(row => row.id === id); return order ? `${order.bill_no} / ${order.line_no}` : '-' }
watch(page,()=>{if(!restoring) void fetchRows()}, {flush:'sync'})
watch(columnFilters, () => { grid?.refreshHeader(); grid?.refreshCells({ force: true }) }, { deep: true })
watch(pageSize,()=>{if(!restoring) {restoring=true;page.value=1;restoring=false;void fetchRows()}}, {flush:'sync'})
onMounted(initialize)
onUnmounted(() => { invalidate(); detail.close(); grid = null })
</script>

<template>
  <PmsDataList ref="listRef" class="purchase-page pms-report-query-surface" scrollbar-label="采购进度横向滚动条">
    <template #toolbar-left>
      <slot name="view-switch" />
    </template>
    <template #toolbar-right>
      <span class="pms-report-query-status" :class="{'is-dirty':dirty}">{{loading?'正在查询':dirty?'条件已修改，待查询':applied?'已查询':'尚未查询'}}<template v-if="stamp"> · {{ new Date(stamp).toLocaleTimeString('zh-CN', { hour12: false }) }}</template></span>
      <ReportExportControl v-if="auth.hasPermission('report:purchase:export')" report="purchase" :parameters="params" :columns="exportColumns" :before-export="confirmExport" :disabled="loading || !applied || !total" />
      <PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="采购进度列设置" @layout-changed="savePreferences" />
      <PmsPageGuide page="purchase" />
    </template>
    <template #filters>
      <PmsQueryWorkspace v-model="conditions" list-key="report-purchase-progress" :legacy-schemes="legacyReportSchemes" :fields="filterFields" :defaults="queryDefaults" :ready="!!metadata" :loading="loading" :snapshot="planSnapshot" @query="submitWorkspace" @clear-columns="clearColumnFilters" />
      <div class="purchase-shortcuts" role="group" aria-label="采购进度快捷筛选">
        <button type="button" :aria-pressed="selectedProgress === ''" :disabled="loading || !metadata" @click="chooseProgress('')">全部</button>
        <button v-for="option in progressOptions" :key="option.value" type="button" :aria-pressed="selectedProgress === option.value" :disabled="loading || !metadata" @click="chooseProgress(option.value)">{{ option.label }}</button>
        <span v-if="selectedProgress === 'custom'" class="purchase-custom-progress">自定义</span>
      </div>
      <div v-if="entry" class="purchase-context"><el-button size="small" link type="primary" @click="emit('overview')">返回总进度</el-button><template v-if="projectScope"><span>当前项目限定：{{ projectScope.product_line_name }} · {{ projectScope.project_code || '未关联项目' }}</span><el-button size="small" link type="primary" @click="clearProjectScope">清除项目限定</el-button></template><span v-else>当前查询范围全部项目</span></div>
    </template>
    <template #grid>
      <div v-if="error" class="pms-list-load-error" role="alert">{{ error }}<span v-if="applied">，下方保留上次查询结果；上次结果范围：{{ resultScopeLabel }}</span> <el-button size="small" @click="retry">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy"
        :row-data="visibleRows" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS"
        :locale-text="chineseLocaleText" :loading="loading" :pagination="false"
        :overlay-no-rows-template="applied ? '<span>没有符合条件的数据</span>' : '<span>设置条件后，点击查询</span>'"
        :get-row-id="params => String(params.data.id)" :get-row-class="params => String(params.data.id) === detailState.requestId ? 'purchase-selected-row' : ''"
        :enable-cell-text-selection="true" @grid-ready="onGridReady" @cell-focused="onCellFocus"
        @row-clicked="onRowClicked"
        @column-resized="onColumnResized" @column-moved="savePreferences" @column-pinned="savePreferences"
        @sort-changed="onSortChanged"
        @first-data-rendered="listRef?.refreshScrollbar()" @grid-size-changed="listRef?.refreshScrollbar()" />
      <div v-else-if="loading" class="purchase-loading" role="status">正在加载报表…</div>
    </template>
    <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" /></template>
  </PmsDataList>

  <section v-if="detailState.open" class="purchase-trace" role="dialog" aria-label="采购关联明细" @keydown.esc="detail.close()">
    <header class="purchase-trace-header">
      <div><span>{{ activeRow?.bill_no }} / 第 {{ activeRow?.line_no }} 行</span><h2>{{ activeRow?.material_name || '采购关联明细' }}</h2><p>产品线 {{ activeRow?.product_line_name || '-' }} · 申请数量 {{ number(activeRow?.requested) }} {{ activeRow?.unit_name }}</p></div>
      <el-tooltip content="关闭"><el-button :icon="Close" aria-label="关闭采购明细" @click="detail.close()" /></el-tooltip>
    </header>
    <div class="purchase-trace-scroll" :aria-busy="detailState.loading">
      <div v-if="detailState.loading" class="purchase-loading" role="status">正在加载关联明细…</div>
      <div v-else-if="detailState.error" class="purchase-loading" role="alert">{{ detailState.error }} <el-button @click="detail.retry()">重试</el-button></div>
      <template v-else-if="detailState.data">
        <p v-if="detailState.data.summary.issues.length" class="purchase-warning" role="status">关联来源、状态或数量存在待核对项，无法确认的累计数量显示为“-”。</p>
        <section aria-label="关联订单明细">
          <div class="purchase-section-heading"><h3>关联订单明细</h3><span>{{ detailState.data.orders.length }} 条</span></div>
          <div class="purchase-detail-scroll"><table class="purchase-detail-table"><thead><tr><th>订单编号</th><th>行号</th><th>订单日期</th><th>供应商</th><th>数据状态</th><th>单位</th><th class="purchase-number">数量</th></tr></thead>
            <tbody><tr v-for="order in detailState.data.orders" :key="order.id" :class="{ picked: String(order.id) === detailState.orderId }" @click="detail.selectOrder(String(order.id))"><td><button class="purchase-order-link" :aria-pressed="String(order.id) === detailState.orderId" @click.stop="detail.selectOrder(String(order.id))">{{ order.bill_no || '-' }}</button></td><td>{{ order.line_no }}</td><td>{{ date(order.order_date) }}</td><td>{{ order.supplier_name || '-' }}</td><td><span class="pms-status" :class="order.effective ? 'success' : 'info'">{{ stateLabel(order) }}</span></td><td>{{ order.unit_name || '-' }}</td><td class="purchase-number">{{ number(order.quantity) }}</td></tr>
              <tr v-if="!detailState.data.orders.length"><td colspan="7" class="purchase-empty">尚未形成采购订单</td></tr></tbody>
          </table></div>
        </section>
        <section aria-label="关联入库明细">
          <div class="purchase-section-heading"><h3>关联入库明细</h3><span>{{ receipts.length }} 条</span></div>
          <div v-if="selectedOrder" class="purchase-receipt-filter"><span>{{ selectedOrder.bill_no }} / 第 {{ selectedOrder.line_no }} 行</span><el-button link type="primary" @click="detail.selectOrder(null)">查看全部</el-button></div>
          <div class="purchase-detail-scroll"><table class="purchase-detail-table"><thead><tr><th>入库单编号</th><th>行号</th><th>入库日期</th><th>数据状态</th><th>单位</th><th class="purchase-number">实收数量</th><th>来源订单 / 行号</th></tr></thead>
            <tbody><tr v-for="stock in receipts" :key="stock.id"><td>{{ stock.bill_no || '-' }}</td><td>{{ stock.line_no }}</td><td>{{ date(stock.stock_date) }}</td><td><span class="pms-status" :class="stock.effective ? 'success' : 'info'">{{ stateLabel(stock) }}</span></td><td>{{ stock.unit_name || '-' }}</td><td class="purchase-number">{{ number(stock.quantity) }}</td><td>{{ orderLabel(stock.order_id) }}</td></tr>
              <tr v-if="!receipts.length"><td colspan="7" class="purchase-empty">{{ selectedOrder ? '此订单暂无入库记录' : '暂无关联入库记录' }}</td></tr></tbody>
          </table></div>
        </section>
      </template>
    </div>
    <footer class="purchase-trace-footer">仅查询，不修改金蝶单据<span v-if="detailState.data">累计净入库 {{ number(detailState.data.summary.net_received) }} {{ activeRow?.unit_name }}</span></footer>
  </section>
</template>

<style scoped>
.purchase-plan { width: 160px; }
.purchase-context { display:flex; align-items:center; flex-wrap:wrap; gap:10px; min-height:26px; font-size:12px; color:var(--pms-text-secondary); }
.purchase-filter { width: 150px; max-width: 100%; }
.purchase-filter--search { width: 250px; }
.purchase-filter--dates { width: 280px; }
.purchase-stamp { color: var(--pms-text-muted); font-size: 11px; }
.purchase-shortcuts { display: flex; align-items: center; gap: 16px; min-height: 26px; margin-bottom: 2px; overflow-x: auto; border-bottom: 1px solid var(--pms-border-soft); }
.purchase-shortcuts button { flex: 0 0 auto; height: 24px; border: 0; border-bottom: 2px solid transparent; padding: 0; background: transparent; color: var(--pms-text-secondary); font: inherit; font-size: 12px; white-space: nowrap; cursor: pointer; }
.purchase-shortcuts button[aria-pressed="true"] { color: var(--pms-primary); border-bottom-color: var(--pms-primary); }
.purchase-shortcuts button:disabled { cursor: not-allowed; opacity: 0.5; }
.purchase-shortcuts button:focus-visible { outline-offset: -2px; }
.purchase-custom-progress { flex: 0 0 auto; font-size: 12px; color: var(--pms-text-secondary); }
.purchase-scope-note { align-self: center; margin-left: auto; font-size: 11px; color: var(--pms-text-muted); }
.purchase-loading, .purchase-empty { text-align: center; padding: 28px; color: var(--pms-text-secondary); }
.purchase-trace { position: fixed; right: var(--pms-page-inset); top: calc(var(--pms-header-height) + var(--pms-page-inset)); bottom: var(--pms-page-inset); width: 760px; max-width: calc(100vw - 12px); background: var(--pms-surface); border: 1px solid var(--pms-border); border-radius: 8px; box-shadow: -4px 0 18px rgb(16 24 40 / 4%); z-index: 50; display: flex; flex-direction: column; font-family: var(--pms-font); }
.purchase-trace-header { padding: 20px; display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--pms-border-soft); }
.purchase-trace-header h2 { font-size: 17px; margin: 5px 0; overflow-wrap: anywhere; }
.purchase-trace-header span, .purchase-trace-header p { font-size: 12px; color: var(--pms-text-secondary); margin: 0; }
.purchase-trace-scroll { flex: 1; min-height: 0; padding: 0 20px 20px; overflow-y: auto; overscroll-behavior: contain; }
.purchase-section-heading, .purchase-receipt-filter { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.purchase-section-heading { margin: 20px 0 12px; }
.purchase-section-heading h3 { font-size: 13px; margin: 0; }
.purchase-section-heading span, .purchase-receipt-filter { color: var(--pms-text-secondary); font-size: 12px; }
.purchase-receipt-filter { padding-bottom: 10px; }
.purchase-detail-scroll { overflow-x: auto; border: 1px solid var(--pms-border-soft); border-radius: 6px; }
.purchase-detail-table { width: 100%; min-width: 700px; border-collapse: collapse; white-space: nowrap; font-size: 12px; font-variant-numeric: tabular-nums; }
.purchase-detail-table th, .purchase-detail-table td { padding: 10px 8px; border-bottom: 1px solid var(--pms-border-soft); text-align: left; }
.purchase-detail-table th { background: var(--pms-bg-soft); color: var(--pms-text-secondary); font-size: 11px; font-weight: 500; text-align: center; }
.purchase-detail-table td.purchase-number { text-align: right; }
.purchase-detail-table tr.picked { background: var(--pms-primary-soft); }
.purchase-detail-table tbody tr:hover { background: var(--pms-bg-soft); }
.purchase-order-link { background: none; border: 0; padding: 0; color: var(--pms-primary); font: inherit; cursor: pointer; }
.purchase-trace-footer { border-top: 1px solid var(--pms-border-soft); padding: 12px 20px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; font-size: 11px; color: var(--pms-text-secondary); }
.purchase-warning { padding: 10px; color: var(--pms-warning); background: var(--pms-warning-soft); border-radius: 4px; font-size: 12px; }
.purchase-page :deep(.purchase-number) { text-align: right; font-variant-numeric: tabular-nums; }
.purchase-page :deep(.purchase-selected-row) { background: var(--pms-primary-soft); }
@media(max-width: 700px) { .purchase-stamp { display: none; } .purchase-filter--search, .purchase-filter--dates { width: 100%; } .purchase-filter { flex: 1 1 130px; } .purchase-trace { right: 8px; max-width: calc(100vw - 16px); } .purchase-tabs { gap: 12px; } }
@media(max-width: 700px) {
  .purchase-page { overflow: auto; }
  .purchase-page :deep(.pms-data-list-grid-shell) { flex: none; min-height: 300px; overflow-x: auto; }
  .purchase-page :deep(.pms-ag-grid) { flex: none; width: 700px; min-width: 700px; height: 280px; }
}
</style>
