<script setup lang="ts">
import { computed, defineComponent, h, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElButton, ElMessage, ElMessageBox } from 'element-plus'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColumnState, type GridApi, type GridReadyEvent } from 'ag-grid-community'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import ReportExportControl from '@/components/ReportExportControl.vue'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import { cloneQuery, validateConditions, type QueryCondition } from '@/query-system/core'
import { activeReportConditions, reportFields, reportDefaults, reportScope, reportReference, reportPreferences, saveReportPreferences, serializeReportConditions, linkReportScope, legacyReportSchemes, purchaseDetailEntry, createReportColumnSort } from '@/query-system/report-adapter'
import { migrateOverviewLayout } from './purchase-overview-layout'
import { migrateReportIdentity, reportIdentityVersion } from './report-identity-layout'
import { decorateQueryColumns } from '@/query-system/column-grid'
import type { ColumnFilter, ColumnQueryContext } from '@/query-system/column-filters'
import { usePageColumnFilter } from '@/query-system/page-column-filter'
import { DEFAULT_PAGE_SIZE, PMS_GRID_OPTIONS, PMS_SINGLE_ACTION_COLUMN as PMS_ACTION_COLUMN } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'
import { getPurchaseMetadata, getPurchaseOverview, getPurchaseProjectReference, type PurchaseMetadata, type PurchaseOverviewRow, type PurchaseQueryDraft, type PurchaseDetailEntry } from '@/api/purchaseReport'

ModuleRegistry.registerModules([AllCommunityModule])
const emit = defineEmits<{ detail: [entry: PurchaseDetailEntry] }>()
const auth = useAuthStore(), metadata = ref<PurchaseMetadata | null>(null)
const queryDraft = ref<QueryCondition[]>([]), columnFilters = ref<ColumnFilter[]>([]), overviewStatus = ref('')
const conditions = computed({ get: () => queryDraft.value, set: value => { queryDraft.value = linkReportScope(value, queryDraft.value, 'organization_ids', ['project_code', 'project_name']) } })
const quickOptions = [{ value: '', label: '全部项目' }, { value: 'unfinished', label: '未完成' }, { value: 'complete', label: '已完成' }, { value: 'review', label: '含待核对' }]
const referenceScope = (q?: { conditions?: QueryCondition[]; line?: number | null }) => {
  const selected = (reportScope('purchase', q?.conditions || conditions.value).params.organization_ids as number[]) || []
  if (q?.line != null && selected.length && !selected.includes(q.line)) throw Error('所选项目产品线不在当前查询范围')
  return { organization_ids: q?.line != null ? [q.line] : selected }
}
const projectReference = () => ({ ...reportReference('项目档案', 'id', 'number', getPurchaseProjectReference, referenceScope), lineOptions: () => metadata.value?.organizations || [] })
const filterFields = computed(() => reportFields((metadata.value?.overview_query_fields || metadata.value?.query_fields || metadata.value?.filter_fields || []).filter(field => field.field !== 'project_name'), [
  { field: 'organization_ids', label: '产品线', type: 'enum', options: metadata.value?.organizations || [], operators: ['equals', 'in', 'reference'] },
  { field: 'project_code', label: '项目编码', type: 'text', reference: projectReference() },
  { field: 'supplier_name', label: '供应商', type: 'text' },
]))
const queryDefaults = reportDefaults(['bill_no', 'organization_ids', 'project_code', 'application_date', 'supplier_name'])
const invalid = computed(() => { try { reportScope('purchase', conditions.value); return Object.values(validateConditions(activeReportConditions(conditions.value), filterFields.value))[0] || '' } catch (error) { return (error as Error).message } })
const rows = ref<PurchaseOverviewRow[]>([]), total = ref(0), totals = reactive({ all: 0, complete: 0, review: 0 })
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), pendingSize = ref<number | null>(null)
const loading = ref(false), error = ref(''), stamp = ref('')
const sort = reactive({ sort: 'project_code', direction: 'asc' })
const sortFields = { project_code: 'project_code', completion_rate: 'completion_rate', conversion_rate: 'conversion_rate', total_lines: 'total_lines' }
const sortableKeys = Object.keys(sortFields)
const rateKeys = ['completion_rate', 'conversion_rate']
const listRef = ref<InstanceType<typeof PmsDataList>>()
let grid: GridApi<PurchaseOverviewRow> | null = null, restoring = false, serial = 0, controller: AbortController | null = null
const projectPrefix = ['product_line_name', 'project_code']
const fields = computed(() => {
  const available = (metadata.value?.overview_fields || []).filter(field => field.key !== 'project_name')
  return [...projectPrefix.flatMap(key => available.filter(field => field.key === key)), ...available.filter(field => !projectPrefix.includes(field.key))]
})
const defaultKeys = [...projectPrefix, ...rateKeys, 'total_lines', 'not_ordered_lines', 'ordering_lines', 'receiving_lines', 'complete_lines', 'review_lines']
const visible = ref([...defaultKeys]), savedColumns = ref<ColumnState[]>([])
const groups = computed(() => [...new Set(fields.value.map(f => f.group))].map(group => ({ key: group, label: group, fields: fields.value.filter(f => f.group === group).map(f => ({ ...f, quick_addable: true })) })))
const key = computed(() => `pms:purchase-overview:v1:${auth.user?.id || 'anonymous'}`)
function saveLayout() {
  if (restoring || !reportIdentityVersion(fields.value)) return
  savedColumns.value = grid?.getColumnState() || savedColumns.value
  try { saveReportPreferences(localStorage, key.value, { visible: visible.value, columns: savedColumns.value, sort: { ...sort }, metricLayoutVersion: 1, reportIdentityVersion: 1 }) }
  catch { ElMessage.warning('列设置保存失败，请检查浏览器存储空间') }
  void nextTick(() => listRef.value?.refreshScrollbar())
}
const draft = (): PurchaseQueryDraft => {
  const scope = reportScope('purchase', conditions.value)
  return { keyword: String(scope.params.keyword || ''), project_code: '', supplier: String(scope.params.supplier || ''), progress: '', organization_ids: (scope.params.organization_ids as number[]) || [], dates: [], conditions: scope.conditions, column_filters: [] as ColumnFilter[] }
}
type Selection = { draft: PurchaseQueryDraft; status: string }
const applied = ref<Selection | null>(null)
const dirty = computed(() => { if (!applied.value) return false; try { return JSON.stringify({ draft: draft(), status: overviewStatus.value }) !== JSON.stringify(applied.value) || pendingSize.value !== null } catch { return true } })
function parameters(value: Selection, submit: boolean) {
  return { ...value.draft, view: 'overview' as const, dates: undefined, conditions: undefined, filters: serializeReportConditions(value.draft.conditions), column_filters: '[]',
    date_from: value.draft.dates[0] || undefined, date_to: value.draft.dates[1] || undefined,
    overview_status: value.status, ...sort, page: submit ? 1 : page.value, page_size: submit ? pendingSize.value ?? pageSize.value : pageSize.value }
}
type Attempt = { selection: Selection; params: ReturnType<typeof parameters>; submit: boolean }
let accepted: Attempt | null = null, failed: Attempt | null = null
const exportParameters = () => cloneQuery(accepted!.params)
const exportColumns = () => grid?.getAllDisplayedColumns().map(column => column.getColId()).filter(key => visible.value.includes(key)) || visible.value
async function beforeExport() {
  if (dirty.value) {
    try { await ElMessageBox.confirm('当前条件尚未查询，将导出上次查询结果。是否继续？', '导出查询结果', { confirmButtonText: '继续导出', cancelButtonText: '取消', type: 'warning' }) }
    catch { return false }
  }
  return !!accepted && !loading.value
}
function invalidate() { ++serial; controller?.abort(); loading.value = false; failed = null }
async function query(submit = false, replay?: Attempt, applySort = false) {
  if (!metadata.value || (!submit && !applied.value) || (submit && invalid.value && !replay)) return
  pageColumns.clear()
  const selection = cloneQuery(replay?.selection || (submit ? { draft: draft(), status: overviewStatus.value } : applied.value!))
  const params = replay?.params || parameters(selection, submit)
  if (!submit && !replay && !applySort && accepted) {
    params.sort = accepted.params.sort; params.direction = accepted.params.direction
  }
  const current = ++serial; controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try {
    const data = await getPurchaseOverview(params, controller.signal)
    if (current !== serial) return
    rows.value = data.items; total.value = data.total; Object.assign(totals, { all: data.total_lines, complete: data.complete_lines, review: data.review_lines }); stamp.value = data.queried_at
    applied.value = selection; accepted = { selection, params: cloneQuery(params), submit }; failed = null
    restoring = true; page.value = params.page; pageSize.value = params.page_size; restoring = false
    if (submit) pendingSize.value = null
    await nextTick(); listRef.value?.refreshScrollbar()
  } catch { if (current === serial) {
    failed = { selection, params: cloneQuery(params), submit }; error.value = '总进度查询失败，请重试'
    if (accepted) { restoring = true; page.value = accepted.params.page; pageSize.value = accepted.params.page_size; restoring = false }
  } } finally { if (current === serial) loading.value = false }
}
function detailEntry(): PurchaseDetailEntry { return purchaseDetailEntry(applied.value?.draft || null, metadata.value?.query_fields || metadata.value?.filter_fields || []) }
function drill(row: PurchaseOverviewRow, progress = '') {
  if (!applied.value || loading.value) return
  emit('detail', { ...detailEntry(), scope: { project_code: row.project_code, organization_id: row.organization_id, product_line_name: row.product_line_name }, progress })
}
defineExpose({ detailEntry })
const Action = defineComponent({ props: ['params'], setup(props) { return () => h(ElButton, { size: 'small', link: true, type: 'primary', disabled: loading.value, onClick: () => drill(props.params.data) }, () => '明细') } })
const Completion = defineComponent({ props: ['params'], setup(props) { return () => {
  const value = Number(props.params.value)
  return h('div', { class: 'overview-completion' }, [h('span', { class: 'overview-track' }, [h('span', { class: { done: value === 100 }, style: { width: `${value}%` } })]), h('span', `${value.toFixed(1)}%`)])
} } })
const Count = defineComponent({ props: ['params'], setup(props) { return () => h('button', { type: 'button', class: ['overview-count', { review: props.params.colDef.field === 'review_lines' }], disabled: loading.value, onClick: () => drill(props.params.data, props.params.colDef.field.replace(/_lines$/, '')) }, String(props.params.value)) } })
const columnFields = computed(() => reportFields(metadata.value?.overview_column_filter_fields || []).filter(f => f.field !== 'project_name' && f.operators?.join() !== 'reference'))
const pageColumns = usePageColumnFilter(rows, () => columnFields.value, columnFilters, () => [page.value, pageSize.value], undefined, () => !!accepted && !loading.value)
const visibleRows = pageColumns.visibleRows
const columnContext = (): ColumnQueryContext => ({ ...pageColumns.context,
  ready: () => !!accepted && !loading.value,
  sort: createReportColumnSort({ accepted: () => accepted?.params || null, loading: () => loading.value, fields: () => sortFields, grid: () => grid,
    changed: value => { Object.assign(sort, value); saveLayout() }, unsupported: () => ElMessage.warning('此列不支持排序'),
    load: params => query(false, { selection: cloneQuery(accepted!.selection), params, submit: false }),
  }),
})
const columns = computed<ColDef<PurchaseOverviewRow>[]>(() => decorateQueryColumns<PurchaseOverviewRow>([
  ...fields.value.map(field => ({ field: field.key, headerName: field.label, colId: field.key, hide: !visible.value.includes(field.key), initialWidth: rateKeys.includes(field.key) ? 170 : field.key === 'project_code' ? 125 : field.value_type === 'number' ? 88 : 110, minWidth: 80, maxWidth: 800,
    initialPinned: projectPrefix.includes(field.key) ? 'left' as const : undefined,
    initialFlex: projectPrefix.includes(field.key) ? undefined : 1,
    sortable: sortableKeys.includes(field.key),
    cellClass: field.value_type === 'number' ? 'overview-number' : undefined,
    valueFormatter: ({value}: {value?: unknown}) => value === null || value === undefined || value === '' ? '' : String(value),
    tooltipValueGetter: ({value}: {value?: unknown}) => ['product_line_name', 'organization_name'].includes(field.key) ? String(value || '') : '',
    cellRenderer: rateKeys.includes(field.key) ? Completion : field.key.endsWith('_lines') && field.key !== 'total_lines' ? Count : undefined,
  })), { colId: 'purchase_actions', headerName: '操作', pinned: 'right', lockPosition: 'right', ...PMS_ACTION_COLUMN, cellRenderer: Action, cellClass: 'pms-action-cell' },
], columnContext) as ColDef<PurchaseOverviewRow>[])
const defaultColDef: ColDef = { resizable: true, sortable: false, comparator: () => 0, editable: false, cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }
function ready(event: GridReadyEvent<PurchaseOverviewRow>) {
  grid = event.api; restoring = true
  grid.applyColumnState({ state: savedColumns.value, applyOrder: true }); restoring = false
  listRef.value?.refreshScrollbar()
}
function sortChanged(event: { source: string }) {
  if (restoring || ['api', 'gridInitializing'].includes(event.source)) return
  const current = grid?.getColumnState().find(c => c.sort && sortableKeys.includes(c.colId))
  Object.assign(sort, { sort: current?.colId || 'project_code', direction: current?.sort || 'asc' })
  restoring = true; page.value = 1; restoring = false; saveLayout(); void query(false, undefined, true)
}
function resized(event: { finished: boolean }) { if (event.finished) saveLayout() }
const planSnapshot = () => ({ reportIdentityVersion: reportIdentityVersion(fields.value), metricLayoutVersion: 1, pageSize: pendingSize.value ?? pageSize.value, visible: [...visible.value], columns: grid?.getColumnState() || savedColumns.value, overviewStatus: overviewStatus.value, sort: { ...sort } })
function clearColumnFilters() { pageColumns.clear(); overviewStatus.value = ''; invalidate() }
async function submitWorkspace(_value: QueryCondition[], preferences: object = {}) {
  if (invalid.value) { ElMessage.warning(invalid.value); return }
  const plan = reportPreferences(migrateReportIdentity(migrateOverviewLayout(preferences)), fields.value.map(f => f.key))
  if (plan.overviewStatus !== undefined) overviewStatus.value = plan.overviewStatus
  restoring = true
  if (plan.pageSize != null && plan.pageSize !== pageSize.value) pendingSize.value = plan.pageSize
  if (plan.visible) visible.value = plan.visible
  if (plan.columns) { savedColumns.value = plan.columns as ColumnState[]; await nextTick(); grid?.applyColumnState({ state: savedColumns.value, applyOrder: true }) }
  const sorting = grid?.getColumnState().find(c => c.sort && sortableKeys.includes(c.colId))
  if (plan.sort && sortableKeys.includes(plan.sort.sort)) Object.assign(sort, plan.sort)
  else if (sorting) Object.assign(sort, { sort: sorting.colId, direction: sorting.sort })
  else if (plan.columns) Object.assign(sort, { sort: 'project_code', direction: 'asc' })
  restoring = false; saveLayout(); await query(true)
}
async function initialize() {
  loading.value = true
  try {
    metadata.value = await getPurchaseMetadata()
    try {
      const raw = JSON.parse(localStorage.getItem(key.value) || '{}')
      const saved = migrateReportIdentity(migrateOverviewLayout(raw))
      if (Array.isArray(saved.visible)) visible.value = saved.visible.filter(k => fields.value.some(f => f.key === k))
      if (Array.isArray(saved.columns)) savedColumns.value = saved.columns
      const sorting = savedColumns.value.find(c => c.sort && sortableKeys.includes(c.colId))
      const savedSort = reportPreferences(saved, fields.value.map(f => f.key)).sort
      if (savedSort && sortableKeys.includes(savedSort.sort)) Object.assign(sort, savedSort)
      else if (sorting) Object.assign(sort, { sort: sorting.colId, direction: sorting.sort })
      if (raw.metricLayoutVersion !== 1 || raw.reportIdentityVersion !== 1) saveLayout()
    } catch { /* Ignore invalid local layout, retaining defaults. */ }
    await nextTick()
  } catch { error.value = '总进度初始化失败，请重试' } finally { loading.value = false }
}
function retry() { if (!metadata.value) void initialize(); else if (failed) void query(failed.submit, failed) }
watch(page, () => { if (!restoring) void query() }, { flush: 'sync' })
watch(columnFilters, () => { grid?.refreshHeader(); grid?.refreshCells({ force: true }) }, { deep: true })
watch(pageSize, () => { if (!restoring) { restoring = true; page.value = 1; restoring = false; void query() } }, { flush: 'sync' })
onMounted(initialize)
onUnmounted(() => { invalidate(); grid = null })
</script>
<template>
  <PmsDataList ref="listRef" class="purchase-overview-page pms-report-query-surface" scrollbar-label="采购总进度横向滚动条">
    <template #toolbar-left><slot name="view-switch" /></template>
    <template #toolbar-right>
      <span class="pms-report-query-status" :class="{'is-dirty':dirty}">{{ loading ? '正在查询' : dirty ? '条件已修改，待查询' : applied ? '已查询' : '尚未查询' }}<template v-if="stamp"> · {{ new Date(stamp).toLocaleTimeString('zh-CN',{hour12:false}) }}</template></span>
      <ReportExportControl v-if="auth.hasPermission('report:purchase:export')" report="purchase" :parameters="exportParameters" :columns="exportColumns" :before-export="beforeExport" :disabled="loading || !applied || !total" />
      <PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="采购总进度列设置" @layout-changed="saveLayout" />
      <PmsPageGuide page="purchase" />
    </template>
    <template #filters>
      <PmsQueryWorkspace entry-mode="report" v-model="conditions" list-key="report-purchase-overview" :legacy-schemes="legacyReportSchemes" :fields="filterFields" :defaults="queryDefaults" :ready="!!metadata" :loading="loading" :snapshot="planSnapshot" @query="submitWorkspace" @clear-columns="clearColumnFilters" />
      <div class="overview-shortcuts" role="group" aria-label="项目进度快捷筛选"><button v-for="option in quickOptions" :key="option.value" type="button" :aria-pressed="overviewStatus === option.value" :disabled="loading || !metadata" @click="overviewStatus = option.value; query(true)">{{ option.label }}</button><span v-if="applied">{{ total }} 个项目组织组合 · {{ totals.all }} 申请行 · 已完成 {{ totals.complete }} 行 · 待核对 {{ totals.review }} 行</span></div>
    </template>
    <template #grid>
      <div v-if="error" class="pms-list-load-error" role="alert">{{ error }}<span v-if="applied">，下方保留上次查询结果</span> <el-button size="small" @click="retry">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy" :row-data="visibleRows" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS" :locale-text="chineseLocaleText" :loading="loading" :pagination="false" :get-row-id="p => p.data.id" :enable-cell-text-selection="true" :overlay-no-rows-template="applied ? '<span>没有符合条件的项目</span>' : '<span>设置条件后，点击查询</span>'" @grid-ready="ready" @sort-changed="sortChanged" @column-resized="resized" @column-moved="saveLayout" @column-pinned="saveLayout" @first-data-rendered="listRef?.refreshScrollbar()" @grid-size-changed="listRef?.refreshScrollbar()" />
    </template>
    <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" /></template>
  </PmsDataList>
</template>
<style scoped>
.overview-shortcuts{display:flex;align-items:center;gap:16px;min-height:26px;margin-bottom:2px;overflow-x:auto;border-bottom:1px solid var(--pms-border-soft)}
.overview-shortcuts button{height:24px;border:0;border-bottom:2px solid transparent;padding:0;background:transparent;color:var(--pms-text-secondary);font:inherit;font-size:12px;white-space:nowrap;cursor:pointer}
.overview-shortcuts button[aria-pressed=true]{color:var(--pms-primary);border-bottom-color:var(--pms-primary)}
.overview-shortcuts button:disabled{opacity:0.5;cursor:not-allowed}
.overview-shortcuts>span{margin-left:auto;white-space:nowrap;font-size:11px;color:var(--pms-text-muted)}
.purchase-overview-page :deep(.overview-completion){display:flex;align-items:center;gap:8px;height:100%;font-variant-numeric:tabular-nums;font-size:12px}
.purchase-overview-page :deep(.overview-completion>span:last-child){min-width:44px;text-align:right}
.purchase-overview-page :deep(.overview-track){flex:1;height:5px;background:var(--pms-border-soft);border-radius:3px;overflow:hidden}
.purchase-overview-page :deep(.overview-track>span){display:block;height:100%;background:var(--pms-primary);opacity:0.65;border-radius:3px}
.purchase-overview-page :deep(.overview-track>span.done){background:var(--pms-success);opacity:1}
.purchase-overview-page :deep(.overview-count){width:100%;border:0;background:transparent;padding:0;color:var(--pms-text-secondary);font:inherit;font-variant-numeric:tabular-nums;text-align:right;cursor:pointer}
.purchase-overview-page :deep(.overview-count:hover){color:var(--pms-primary);text-decoration:underline}
.purchase-overview-page :deep(.overview-count.review){color:var(--pms-danger)}
.purchase-overview-page :deep(.overview-number){text-align:right;font-variant-numeric:tabular-nums}
@media(max-width:1000px){.overview-shortcuts>span{display:none}}
@media(max-width:700px){.purchase-overview-page{overflow:auto}.purchase-overview-page :deep(.pms-data-list-grid-shell){flex:none;min-height:300px;overflow-x:auto}.purchase-overview-page :deep(.pms-ag-grid){flex:none;width:1100px;min-width:1100px;height:280px}}
</style>
