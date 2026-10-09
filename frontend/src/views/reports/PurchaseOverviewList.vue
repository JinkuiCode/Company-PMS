<script setup lang="ts">
import { computed, defineComponent, h, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElButton, ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColumnState, type GridApi, type GridReadyEvent } from 'ag-grid-community'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsReportQueryBar from '@/report-query/PmsReportQueryBar.vue'
import PmsReportPlans from '@/report-query/PmsReportPlans.vue'
import { cloneQuery, validateConditions, type ReportCondition } from '@/report-query/state'
import { PmsTextControl, PmsSelectControl, PmsDateControl } from '@/form-system'
import { DEFAULT_PAGE_SIZE, PMS_GRID_OPTIONS, PMS_ACTION_COLUMN } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'
import { getPurchaseMetadata, getPurchaseOverview, type PurchaseMetadata, type PurchaseOverviewRow, type PurchaseQueryDraft, type PurchaseDetailEntry } from '@/api/purchaseReport'
import { usePurchaseCandidates } from '@/composables/usePurchaseCandidates'

ModuleRegistry.registerModules([AllCommunityModule])
const emit = defineEmits<{ detail: [entry: PurchaseDetailEntry] }>()
const auth = useAuthStore(), metadata = ref<PurchaseMetadata | null>(null)
const filters = reactive({ keyword: '', project_code: '', supplier: '', progress: '', organization_ids: [] as number[] })
const dates = ref<string[]>([]), conditions = ref<ReportCondition[]>([]), overviewStatus = ref('')
const quickOptions = [{ value: '', label: '全部项目' }, { value: 'unfinished', label: '未完成' }, { value: 'complete', label: '已完成' }, { value: 'review', label: '含待核对' }]
const filterFields = computed(() => metadata.value?.filter_fields || [])
const { candidates, optionLoading, findOptions: options, organizationsChanged, restoreProject, invalidate: invalidateCandidates, projectChanged, validationError, validating } = usePurchaseCandidates(() => filters.organization_ids, () => filters.project_code, value => { filters.project_code = value })
const invalid = computed(() => validating.value ? '正在核验项目范围' : validationError.value || validateConditions(conditions.value, filterFields.value))
const rows = ref<PurchaseOverviewRow[]>([]), total = ref(0), totals = reactive({ all: 0, complete: 0, review: 0 })
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), pendingSize = ref<number | null>(null)
const loading = ref(false), error = ref(''), stamp = ref('')
const sort = reactive({ sort: 'project_code', direction: 'asc' })
const listRef = ref<InstanceType<typeof PmsDataList>>()
let grid: GridApi<PurchaseOverviewRow> | null = null, restoring = false, serial = 0, controller: AbortController | null = null
const fields = computed(() => metadata.value?.overview_fields || [])
const defaultKeys = ['product_line_name', 'project_code', 'project_name', 'completion_rate', 'total_lines', 'not_ordered_lines', 'ordering_lines', 'receiving_lines', 'complete_lines', 'review_lines']
const visible = ref([...defaultKeys]), savedColumns = ref<ColumnState[]>([])
const groups = computed(() => [...new Set(fields.value.map(f => f.group))].map(group => ({ key: group, label: group, fields: fields.value.filter(f => f.group === group).map(f => ({ ...f, quick_addable: true })) })))
const key = computed(() => `pms:purchase-overview:v1:${auth.user?.id || 'anonymous'}`)
function saveLayout() {
  if (restoring) return
  savedColumns.value = grid?.getColumnState() || savedColumns.value
  try { localStorage.setItem(key.value, JSON.stringify({ visible: visible.value, columns: savedColumns.value })) }
  catch { ElMessage.warning('列设置保存失败，请检查浏览器存储空间') }
  void nextTick(() => listRef.value?.refreshScrollbar())
}
const draft = (): PurchaseQueryDraft => ({ ...cloneQuery(filters), dates: [...(dates.value || [])], conditions: cloneQuery(conditions.value) })
type Selection = { draft: PurchaseQueryDraft; status: string }
const applied = ref<Selection | null>(null)
const dirty = computed(() => !!applied.value && (JSON.stringify({ draft: draft(), status: overviewStatus.value }) !== JSON.stringify(applied.value) || pendingSize.value !== null))
function parameters(value: Selection, submit: boolean) {
  return { ...value.draft, dates: undefined, conditions: undefined, filters: JSON.stringify(value.draft.conditions.map(({field,operator,value,valueEnd}) => ({field,operator,value,valueEnd}))),
    date_from: value.draft.dates[0] || undefined, date_to: value.draft.dates[1] || undefined,
    overview_status: value.status, ...sort, page: submit ? 1 : page.value, page_size: submit ? pendingSize.value ?? pageSize.value : pageSize.value }
}
type Attempt = { selection: Selection; params: ReturnType<typeof parameters>; submit: boolean }
let accepted: Attempt | null = null, failed: Attempt | null = null
function invalidate() { ++serial; controller?.abort(); loading.value = false; failed = null }
async function query(submit = false, replay?: Attempt, applySort = false) {
  if (!metadata.value || (!submit && !applied.value) || (submit && invalid.value && !replay)) return
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
function detailEntry(): PurchaseDetailEntry { return { draft: applied.value ? cloneQuery(applied.value.draft) : null } }
function drill(row: PurchaseOverviewRow, progress = '') {
  if (!applied.value || loading.value) return
  emit('detail', { ...detailEntry(), scope: { project_code: row.project_code, organization_id: row.organization_id, product_line_name: row.product_line_name }, progress })
}
defineExpose({ detailEntry })
const Action = defineComponent({ props: ['params'], setup(props) { return () => h(ElButton, { size: 'small', link: true, type: 'primary', disabled: loading.value, onClick: () => drill(props.params.data) }, () => '明细') } })
const Completion = defineComponent({ props: ['params'], setup(props) { return () => {
  const value = Number(props.params.data.completion_rate)
  return h('div', { class: 'overview-completion' }, [h('span', { class: 'overview-track' }, [h('span', { class: { done: value === 100 }, style: { width: `${value}%` } })]), h('span', `${value.toFixed(1)}%`)])
} } })
const Count = defineComponent({ props: ['params'], setup(props) { return () => h('button', { type: 'button', class: ['overview-count', { review: props.params.colDef.field === 'review_lines' }], disabled: loading.value, onClick: () => drill(props.params.data, props.params.colDef.field.replace(/_lines$/, '')) }, String(props.params.value)) } })
const columns = computed<ColDef<PurchaseOverviewRow>[]>(() => [
  ...fields.value.map(field => ({ field: field.key, headerName: field.label, colId: field.key, hide: !visible.value.includes(field.key), initialWidth: field.key === 'project_name' ? 190 : field.key === 'completion_rate' ? 170 : field.key === 'project_code' ? 125 : field.value_type === 'number' ? 88 : 110, minWidth: 80, maxWidth: 800,
    initialPinned: defaultKeys.slice(0, 3).includes(field.key) ? 'left' as const : undefined,
    initialFlex: defaultKeys.slice(0, 3).includes(field.key) ? undefined : 1,
    sortable: ['project_code', 'completion_rate', 'total_lines'].includes(field.key),
    cellClass: field.value_type === 'number' ? 'overview-number' : undefined,
    valueFormatter: ({value}: {value?: unknown}) => value === null || value === undefined || value === '' ? '' : String(value),
    tooltipValueGetter: ({value}: {value?: unknown}) => ['project_name', 'organization_name'].includes(field.key) ? String(value || '') : '',
    cellRenderer: field.key === 'completion_rate' ? Completion : field.key.endsWith('_lines') && field.key !== 'total_lines' ? Count : undefined,
  })), { colId: 'purchase_actions', headerName: '操作', pinned: 'right', lockPosition: 'right', ...PMS_ACTION_COLUMN, cellRenderer: Action, cellClass: 'pms-action-cell' },
])
const defaultColDef: ColDef = { resizable: true, sortable: false, comparator: () => 0, editable: false, cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }
function ready(event: GridReadyEvent<PurchaseOverviewRow>) {
  grid = event.api; restoring = true
  grid.applyColumnState({ state: savedColumns.value, applyOrder: true }); restoring = false
  listRef.value?.refreshScrollbar()
}
function sortChanged(event: { source: string }) {
  if (restoring || ['api', 'gridInitializing'].includes(event.source)) return
  const current = grid?.getColumnState().find(c => c.sort && ['project_code', 'completion_rate', 'total_lines'].includes(c.colId))
  Object.assign(sort, { sort: current?.colId || 'project_code', direction: current?.sort || 'asc' })
  restoring = true; page.value = 1; restoring = false; saveLayout(); void query(false, undefined, true)
}
function resized(event: { finished: boolean }) { if (event.finished) saveLayout() }
const planSnapshot = () => ({ ...draft(), overviewStatus: overviewStatus.value, pageSize: pendingSize.value ?? pageSize.value, visible: visible.value, columns: grid?.getColumnState() || savedColumns.value, sort: { ...sort } })
async function restorePlan(value: unknown) {
  const plan = value as ReturnType<typeof planSnapshot>
  if (!plan || !Array.isArray(plan.conditions) || !Array.isArray(plan.dates) || !Array.isArray(plan.organization_ids) || !Array.isArray(plan.columns) || !Array.isArray(plan.visible)) { ElMessage.warning('查询方案格式无效'); return }
  const problem = validateConditions(plan.conditions, filterFields.value)
  if (problem) { ElMessage.warning(problem); return }
  if (plan.organization_ids.some(id => !metadata.value?.organizations?.some(option => option.value === id))) { ElMessage.warning('查询方案包含不可选产品线，请重新配置方案'); return }
  invalidate(); restoring = true
  Object.assign(filters, { keyword: plan.keyword || '', project_code: plan.project_code || '', supplier: plan.supplier || '', progress: plan.progress || '', organization_ids: [...plan.organization_ids] })
  dates.value = [...plan.dates]; conditions.value = cloneQuery(plan.conditions); overviewStatus.value = quickOptions.some(o => o.value === plan.overviewStatus) ? plan.overviewStatus : ''
  pendingSize.value = [15,50,100,200,500].includes(plan.pageSize) ? plan.pageSize : 50
  visible.value = plan.visible.filter(k => fields.value.some(f => f.key === k)); savedColumns.value = plan.columns
  Object.assign(sort, { sort: ['project_code','completion_rate','total_lines'].includes(plan.sort?.sort) ? plan.sort.sort : 'project_code', direction: plan.sort?.direction === 'desc' ? 'desc' : 'asc' })
  await nextTick(); grid?.applyColumnState({ state: plan.columns, applyOrder: true }); restoring = false; saveLayout()
  await restoreProject()
}
function reset() { invalidate(); invalidateCandidates(); Object.assign(filters, { keyword: '', project_code: '', supplier: '', progress: '', organization_ids: [] }); dates.value = []; conditions.value = []; overviewStatus.value = ''; pendingSize.value = null }
async function initialize() {
  loading.value = true
  try {
    metadata.value = await getPurchaseMetadata()
    try { const saved = JSON.parse(localStorage.getItem(key.value) || '{}'); if (Array.isArray(saved.visible)) visible.value = saved.visible.filter((k: string) => fields.value.some(f => f.key === k)); if (Array.isArray(saved.columns)) savedColumns.value = saved.columns } catch { /* Ignore invalid local layout, retaining defaults. */ }
    const sorting = savedColumns.value.find(c => c.sort && ['project_code','completion_rate','total_lines'].includes(c.colId))
    if (sorting) Object.assign(sort, { sort: sorting.colId, direction: sorting.sort })
    await nextTick()
  } catch { error.value = '总进度初始化失败，请重试' } finally { loading.value = false }
}
function retry() { if (!metadata.value) void initialize(); else if (failed) void query(failed.submit, failed) }
watch(page, () => { if (!restoring) void query() }, { flush: 'sync' })
watch(pageSize, () => { if (!restoring) { restoring = true; page.value = 1; restoring = false; void query() } }, { flush: 'sync' })
onMounted(initialize)
onUnmounted(() => { invalidate(); grid = null })
</script>
<template>
  <PmsDataList ref="listRef" class="purchase-overview-page pms-report-query-surface" scrollbar-label="采购总进度横向滚动条">
    <template #toolbar-left><slot name="view-switch" /><PmsReportPlans :storage-key="key + ':plans'" :snapshot="planSnapshot" :disabled="!metadata || !!invalid" @restore="restorePlan" /></template>
    <template #toolbar-right><span class="pms-report-query-status" :class="{'is-dirty':dirty}">{{ loading ? '正在查询' : dirty ? '条件已修改，待查询' : applied ? '已查询' : '尚未查询' }}<template v-if="stamp"> · {{ new Date(stamp).toLocaleTimeString('zh-CN',{hour12:false}) }}</template></span><PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="采购总进度列设置" @layout-changed="saveLayout" /></template>
    <template #filters>
      <PmsReportQueryBar v-model:conditions="conditions" :fields="filterFields" :loading="loading" :disabled="!metadata" :invalid="invalid" @query="query(true)" @reset="reset">
        <div class="query-material"><PmsTextControl v-model="filters.keyword" size="compact" :prefix-icon="Search" clearable placeholder="申请单 / 物料编码 / 名称 / 规格" aria-label="搜索采购明细" /></div>
        <PmsSelectControl v-model="filters.organization_ids" :options="metadata?.organizations || []" multiple collapse-tags collapse-tags-tooltip filterable clearable size="compact" placeholder="全部产品线" aria-label="产品线" @update:model-value="organizationsChanged" />
        <PmsSelectControl v-model="filters.project_code" :options="candidates.project" :loading="optionLoading.project" remote filterable :remote-method="(v: string) => options('project',v)" clearable size="compact" placeholder="全部项目" aria-label="项目编码筛选" @visible-change="(v: boolean) => v && options('project')" @update:model-value="projectChanged" />
        <div class="query-dates"><PmsDateControl v-model="dates" type="daterange" size="compact" value-format="YYYY-MM-DD" start-placeholder="申请开始日期" end-placeholder="申请结束日期" aria-label="申请日期范围" /></div>
        <PmsSelectControl v-model="filters.supplier" :options="candidates.supplier" :loading="optionLoading.supplier" remote filterable :remote-method="(v: string) => options('supplier',v)" clearable size="compact" placeholder="全部供应商" aria-label="供应商筛选" @visible-change="(v: boolean) => v && options('supplier')" />
      </PmsReportQueryBar>
      <div class="overview-shortcuts" role="group" aria-label="项目进度快捷筛选"><button v-for="option in quickOptions" :key="option.value" type="button" :aria-pressed="overviewStatus === option.value" :disabled="loading || !metadata" @click="overviewStatus = option.value; query(true)">{{ option.label }}</button><span v-if="applied">{{ total }} 个项目组织组合 · {{ totals.all }} 申请行 · 已完成 {{ totals.complete }} 行 · 待核对 {{ totals.review }} 行</span></div>
    </template>
    <template #grid>
      <div v-if="error" class="pms-list-load-error" role="alert">{{ error }}<span v-if="applied">，下方保留上次查询结果</span> <el-button size="small" @click="retry">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy" :row-data="rows" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS" :locale-text="chineseLocaleText" :loading="loading" :pagination="false" :get-row-id="p => p.data.id" :enable-cell-text-selection="true" :overlay-no-rows-template="applied ? '<span>没有符合条件的项目</span>' : '<span>设置条件后，点击查询</span>'" @grid-ready="ready" @sort-changed="sortChanged" @column-resized="resized" @column-moved="saveLayout" @column-pinned="saveLayout" @first-data-rendered="listRef?.refreshScrollbar()" @grid-size-changed="listRef?.refreshScrollbar()" />
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
