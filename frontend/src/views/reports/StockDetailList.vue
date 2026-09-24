<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, shallowRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColumnState, type GridApi, type GridReadyEvent, type RowClickedEvent, type ColumnResizedEvent } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import ReportExportControl from '@/components/ReportExportControl.vue'
import { PmsTextControl, PmsSelectControl, PmsDateControl, PmsFormDrawer, PmsFormField } from '@/form-system'
import { DEFAULT_PAGE_SIZE, PMS_GRID_OPTIONS } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { createDetailSwitch } from '@/utils/detailSwitch'
import { useAuthStore } from '@/stores/auth'
import { getStockDetailMetadata, getStockDetailRows, getStockDetailCandidates, type StockDetailMetadata, type StockCandidate } from '@/api/stockDetailReport'
import { buildStockDetailQuery, stockDetailOrganizations, createStockDetailRequest, formatStockQuantity, type StockDetailFilters, type StockDetailRow } from './stockDetailState'

ModuleRegistry.registerModules([AllCommunityModule])
const auth = useAuthStore()
const today = new Date()
const localDate = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const filters = reactive<StockDetailFilters>({ material: '', dates: [localDate(new Date(today.getFullYear(), today.getMonth(), 1)), localDate(today)], organization_ids: [], stock_id: null })
const materialMissing = computed(() => !String(filters.material || '').trim())
const organizationMissing = computed(() => !filters.organization_ids?.length)
const page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), metadata = ref<StockDetailMetadata | null>(null)
const initializationError = ref(''), initializing = ref(false)
const listRef = ref<InstanceType<typeof PmsDataList>>()
const request = createStockDetailRequest(getStockDetailRows, value => { result.value = value })
const result = shallowRef<Readonly<typeof request.value>>(request.value)
const selected = ref<StockDetailRow | null>(null), detailOpen = ref(false)
const detailSwitch = createDetailSwitch<StockDetailRow>(() => Promise.resolve(true), async row => { selected.value = row })
const visible = ref<string[]>([]), savedColumns = ref<ColumnState[]>([])
let grid: GridApi<StockDetailRow> | null = null, restoring = false, disposed = false
const candidates = reactive<{ material: StockCandidate[]; stock: StockCandidate[] }>({ material: [], stock: [] })
const optionLoading = reactive({ material: false, stock: false })
const optionRevision = { material: 0, stock: 0 }
const storageKey = computed(() => `pms:stock-detail:v1:${auth.user?.id || 'anonymous'}`)
interface Plan { name: string; filters: StockDetailFilters; size: number; visible: string[]; columns: ColumnState[] }
const plans = ref<Plan[]>([]), planSelected = ref(''), planOpen = ref(false), planName = ref('')
const planOptions = computed(() => [{ value: '', label: '当前查询' }, ...plans.value.map(p => ({ value: p.name, label: p.name }))])
const fields = computed(() => metadata.value?.fields || [])
const defaultKeys = computed(() => fields.value.map(f => f.key))
const groups = computed(() => [{ key: 'stock-detail', label: '物料收发明细', fields: fields.value.map(f => ({ ...f, value_type: f.type, list_available: true, quick_addable: true })) }])
const numberKeys = new Set(['opening_qty', 'income_qty', 'issue_qty', 'balance_qty'])
const exportParameters = () => buildStockDetailQuery(filters, 1, pageSize.value)
const exportColumns = () => fields.value.map(field => field.key)
function text(value: unknown) { return value === null || value === undefined || value === '' ? '-' : String(value) }
function fieldText(key: string, value: unknown) { return numberKeys.has(key) ? formatStockQuantity(value) : text(value) }
const columns = computed<ColDef<StockDetailRow>[]>(() => fields.value.map(field => {
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
}))
const defaultColDef: ColDef = { editable: false, sortable: false, resizable: true, cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }
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
  }))
}
function persist() {
  if (restoring || !metadata.value) return
  savedColumns.value = grid?.getColumnState() || savedColumns.value
  try { localStorage.setItem(storageKey.value, JSON.stringify({ visible: visible.value, columns: savedColumns.value, plans: plans.value })) }
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
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey.value) || '{}')
      if (Array.isArray(saved.visible)) visible.value = [...new Set(saved.visible.filter((key: unknown) => typeof key === 'string' && defaultKeys.value.includes(key)))] as string[]
      savedColumns.value = sanitizeColumns(saved.columns)
      plans.value = Array.isArray(saved.plans) ? saved.plans.filter((p: Plan) => typeof p?.name === 'string' && p.filters && Array.isArray(p.visible)).slice(-30) : []
    } catch { savedColumns.value = []; plans.value = [] }
  } catch { if (!disposed) initializationError.value = '报表初始化失败，请重试' }
  finally { if (!disposed) initializing.value = false }
}
async function query(resetPage = false) {
  if (materialMissing.value || organizationMissing.value) return
  if (resetPage) page.value = 1
  closeDetail()
  await request.query({ ...filters, dates: [...(filters.dates || [])] }, page.value, pageSize.value)
  await nextTick(); listRef.value?.refreshScrollbar()
}
function resetFilters() {
  const now = new Date()
  Object.assign(filters, { material: '', organization_ids: [], organization_id: undefined, stock_id: null,
    dates: [localDate(new Date(now.getFullYear(), now.getMonth(), 1)), localDate(now)] })
  planSelected.value = ''; page.value = 1
  request.clear(); closeDetail()
}
async function findOptions(kind: 'material' | 'stock', keyword = '') {
  if (organizationMissing.value) return
  const ticket = ++optionRevision[kind]; optionLoading[kind] = true
  try {
    const data = await getStockDetailCandidates(kind, keyword, stockDetailOrganizations(filters))
    if (!disposed && ticket === optionRevision[kind]) candidates[kind] = data.items.map(item => ({ ...item, label: kind === 'material' ? `${item.code} · ${item.label}` : item.label }))
  } catch { if (!disposed && ticket === optionRevision[kind]) { candidates[kind] = []; ElMessage.error('候选数据加载失败，请重试') } }
  finally { if (ticket === optionRevision[kind]) optionLoading[kind] = false }
}
function savePlan() {
  const name = planName.value.trim()
  if (!name) return
  try { buildStockDetailQuery(filters, 1, pageSize.value) } catch (error) { ElMessage.warning((error as Error).message); return }
  const plan: Plan = { name, filters: { ...filters, organization_ids: stockDetailOrganizations(filters), dates: [...filters.dates] }, size: pageSize.value,
    visible: [...visible.value], columns: grid?.getColumnState() || savedColumns.value }
  plans.value = [...plans.value.filter(p => p.name !== name), plan].slice(-30)
  persist(); planSelected.value = name; planOpen.value = false; planName.value = ''; ElMessage.success('查询方案已保存')
}
async function loadPlan(value: unknown) {
  const plan = plans.value.find(p => p.name === value)
  if (!plan) return
  try { buildStockDetailQuery(plan.filters, 1, plan.size) } catch (error) { ElMessage.warning((error as Error).message); return }
  Object.assign(filters, { ...plan.filters, organization_id: undefined, organization_ids: stockDetailOrganizations(plan.filters), dates: [...plan.filters.dates] })
  filters.stock_id = plan.filters.stock_id
  pageSize.value = plan.size; page.value = 1
  visible.value = plan.visible.filter(key => defaultKeys.value.includes(key))
  savedColumns.value = sanitizeColumns(plan.columns)
  await nextTick(); restoring = true; grid?.applyColumnState({ state: savedColumns.value, applyOrder: true }); restoring = false
  await query()
}
watch(() => filters.organization_ids, () => { ++optionRevision.stock; ++optionRevision.material; candidates.stock = []; candidates.material = []; filters.stock_id = null }, { deep: true, flush: 'sync' })
watch(filters, () => { request.clear(); closeDetail(); page.value = 1 }, { deep: true, flush: 'sync' })
watch(selected, () => grid?.redrawRows())
onMounted(initialize)
onUnmounted(() => { disposed = true; request.clear(); detailSwitch.invalidate(); ++optionRevision.stock; ++optionRevision.material; grid = null })
</script>

<template>
  <PmsDataList ref="listRef" scrollbar-label="物料收发明细横向滚动条">
    <template #toolbar-left>
      <div class="stock-detail-filter"><PmsSelectControl v-model="planSelected" :options="planOptions" size="compact" aria-label="查询方案" @update:model-value="loadPlan" /></div>
      <el-button size="small" @click="planOpen = true">保存查询方案</el-button>
    </template>
    <template #toolbar-right>
      <ReportExportControl v-if="auth.hasPermission('report:stock-detail:export')" report="stock-detail" :parameters="exportParameters" :columns="exportColumns" :disabled="result.loading || !result.queried_at || (!result.total && !result.openings.length)" />
      <PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="物料收发明细列设置" @layout-changed="persist" />
    </template>
    <template #filters>
      <PmsListFilters :filters="[]" :fields="[]" :active-count="0">
        <div class="stock-detail-filter stock-detail-material"><PmsTextControl v-model="filters.material" size="compact" clearable :error="result.error && !String(filters.material || '').trim() ? '请填写物料' : ''" placeholder="物料编码 / 名称 / 规格型号（必填）" aria-label="物料（必填）" aria-required="true" @keyup.enter="query(true)" /></div>
        <div class="stock-detail-filter"><PmsSelectControl v-model="filters.organization_ids" :options="metadata?.organizations || []" size="compact" multiple collapse-tags collapse-tags-tooltip clearable filterable placeholder="库存组织（必选）" aria-label="库存组织" aria-required="true" /></div>
        <div class="stock-detail-dates"><PmsDateControl v-model="filters.dates" type="daterange" size="compact" start-placeholder="起始日期" end-placeholder="截止日期" aria-label="收发日期范围" /></div>
        <div class="stock-detail-filter"><PmsSelectControl v-model="filters.stock_id" :options="candidates.stock" size="compact" clearable :value-on-clear="null" filterable remote :remote-method="(keyword: string) => findOptions('stock', keyword)" :loading="optionLoading.stock" placeholder="全部仓库" aria-label="仓库" @visible-change="(open: boolean) => open && findOptions('stock')" /></div>
        <el-button type="primary" size="small" :icon="Search" :disabled="!metadata || result.loading || materialMissing || organizationMissing" @click="query(true)">查询</el-button>
        <el-button size="small" @click="resetFilters">重置</el-button>
      </PmsListFilters>
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
      <div v-if="initializationError || result.error" role="alert" class="pms-list-load-error">{{ initializationError || result.error }} <el-button v-if="initializationError" size="small" @click="initialize">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy" :row-data="result.items" :pinned-top-row-data="result.openings" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS" :locale-text="chineseLocaleText" :loading="result.loading" :row-height="36" :pagination="false" :enable-cell-text-selection="true" :get-row-id="p => p.data.row_id" :get-row-class="p => p.data?.row_id === selected?.row_id ? 'pms-detail-row-active' : ''" @grid-ready="onGridReady" @row-clicked="onRowClicked" @column-resized="onColumnResized" @column-moved="persist" @column-pinned="persist" @grid-size-changed="listRef?.refreshScrollbar()" />
      <div v-else-if="initializing" class="stock-detail-loading" role="status">正在加载报表…</div>
    </template>
    <template #pagination><CustomPagination :model-value="page" :page-size="pageSize" :total="result.total" @update:model-value="value => { page = value; query() }" @update:page-size="value => { pageSize = value; query(true) }" /></template>
  </PmsDataList>
  <PmsFormDrawer v-model="detailOpen" title="收发明细" modal-penetrable aria-modal="false" @closed="closeDetail">
    <dl v-if="selected" class="stock-detail-readonly"><template v-for="field in fields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ fieldText(field.key, selected[field.key]) }}</dd></template></dl>
    <template #footer><el-button @click="closeDetail">关闭</el-button></template>
  </PmsFormDrawer>
  <PmsFormDrawer v-model="planOpen" title="保存查询方案">
    <PmsFormField field-id="stock-detail-plan-name" label="方案名称" required><PmsTextControl id="stock-detail-plan-name" v-model="planName" maxlength="40" aria-label="方案名称" @keyup.enter="savePlan" /></PmsFormField>
    <template #footer><el-button @click="planOpen = false">取消</el-button><el-button type="primary" :disabled="!planName.trim()" @click="savePlan">保存</el-button></template>
  </PmsFormDrawer>
</template>

<style scoped>
.stock-detail-filter { width: 170px; max-width: 100%; }
.stock-detail-material { width: 250px; }
.stock-detail-dates { width: 280px; max-width: 100%; }
.stock-detail-loading { padding: 24px; text-align: center; color: var(--pms-text-secondary); }
.stock-detail-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px; padding: 10px 0; color: var(--pms-text-secondary); font-size: 12px; }
.stock-detail-summary strong { margin-left: 8px; font-weight: 600; color: var(--pms-text); font-variant-numeric: tabular-nums; }
.stock-detail-summary-material { margin-right: auto; color: var(--pms-text); }
.stock-detail-summary-material span { margin-left: 8px; color: var(--pms-text-secondary); }
.stock-detail-readonly { display: grid; grid-template-columns: 100px minmax(0, 1fr); margin: 0; }
.stock-detail-readonly dt, .stock-detail-readonly dd { margin: 0; padding: 12px 0; border-bottom: 1px solid var(--pms-border-soft); overflow-wrap: anywhere; }
.stock-detail-readonly dt { color: var(--pms-text-secondary); }
:deep(.stock-detail-number) { text-align: right; font-variant-numeric: tabular-nums; }
:deep(.stock-detail-link) { border: 0; padding: 0; background: transparent; color: var(--pms-primary); font: inherit; cursor: pointer; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 600px) { .stock-detail-material, .stock-detail-dates { width: 100%; } }
</style>
