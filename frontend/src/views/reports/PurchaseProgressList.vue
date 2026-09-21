<script setup lang="ts">
import { computed, defineComponent, h, nextTick, onMounted, onUnmounted, reactive, ref, shallowRef, watch } from 'vue'
import { ElButton, ElMessage } from 'element-plus'
import { Close, Download, Refresh, Search } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColGroupDef, type ColumnState, type GridApi, type GridReadyEvent, type RowClickedEvent, type ColumnResizedEvent, type CellFocusedEvent } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import { PmsTextControl, PmsDateControl, PmsSelectControl, PmsFormDrawer, PmsFormField } from '@/form-system'
import { DEFAULT_PAGE_SIZE, PMS_ACTION_COLUMN, PMS_GRID_OPTIONS } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'
import { getPurchaseMetadata, getPurchaseOptions, getPurchaseRows, getPurchaseDetail, exportPurchaseRows, type PurchaseField, type PurchaseRow, type PurchaseDocument, type PurchaseMetadata, type PurchaseDetail } from '@/api/purchaseReport'
import { createPurchaseDetailState, type PurchaseDetailState } from './purchaseDetailState'

ModuleRegistry.registerModules([AllCommunityModule])
const auth = useAuthStore()
const filters = reactive({ keyword: '', project_code: '', supplier: '', progress: '' })
const dates = ref<string[]>([]), page = ref(1), pageSize = ref(DEFAULT_PAGE_SIZE), total = ref(0)
const rows = ref<PurchaseRow[]>([]), metadata = ref<PurchaseMetadata | null>(null)
const loading = ref(false), error = ref(''), exporting = ref(false), stamp = ref('')
const candidates = reactive({ project: [] as { value: string; label: string }[], supplier: [] as { value: string; label: string }[] })
const optionLoading = reactive({ project: false, supplier: false })
const optionRevision = { project: 0, supplier: 0 }
async function findOptions(field: 'project' | 'supplier', keyword = '') {
  const serial = ++optionRevision[field]; optionLoading[field] = true
  try { const data = await getPurchaseOptions(field, keyword); if (serial === optionRevision[field]) candidates[field] = data.items }
  catch { if (serial === optionRevision[field]) candidates[field] = [] }
  finally { if (serial === optionRevision[field]) optionLoading[field] = false }
}
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
const defaultKeys = ['project_code', 'material_name', 'unit_name', 'bill_no', 'line_no', 'application_date', 'document_status', 'requested', 'approved', 'last_order_date', 'ordered', 'supplier_name', 'last_stock_date', 'net_received', 'pending_order', 'pending_receipt', 'progress']
const groups = computed(() => [...new Set((metadata.value?.fields || []).map(field => field.group))].map(group => ({
  key: group, label: group, fields: metadata.value!.fields.filter(field => field.group === group).map(field => ({ ...field, quick_addable: true })),
})))
const storageKey = computed(() => `pms:purchase-report:v1:${auth.user?.id || 'anonymous'}`)
type Plan = { name: string; filters: typeof filters; dates: string[]; pageSize: number; columns: ColumnState[]; visible: string[]; sort: typeof sort }
const plans = ref<Plan[]>([]), planName = ref(''), planOpen = ref(false), activePlan = ref('当前查询')
const planOptions = computed(() => [{ value: '', label: '当前查询' }, ...plans.value.map(plan => ({ value: plan.name, label: plan.name }))])
const planSelected = ref('')
let savedColumns: ColumnState[] = [], restoring = false
function readPreferences() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey.value) || '{}')
    const keys = new Set(metadata.value?.fields.map(field => field.key))
    visible.value = Array.isArray(saved.visible) ? saved.visible.filter((key: string) => keys.has(key)) : [...defaultKeys]
    savedColumns = Array.isArray(saved.columns) ? saved.columns.filter((column: ColumnState) => keys.has(column.colId) || column.colId === 'purchase_actions') : []
    const sorting = savedColumns.find(column => column.sort && sortFields[column.colId])
    if (sorting) Object.assign(sort, { sort: sortFields[sorting.colId], direction: sorting.sort })
    plans.value = Array.isArray(saved.plans) ? saved.plans.filter((plan: Plan) => typeof plan?.name === 'string' && plan.filters && Array.isArray(plan.dates) && Array.isArray(plan.visible) && Array.isArray(plan.columns)).slice(0, 30) : []
  } catch { visible.value = [...defaultKeys]; savedColumns = []; plans.value = [] }
}
function savePreferences() {
  if (restoring) return
  try { localStorage.setItem(storageKey.value, JSON.stringify({ visible: visible.value, columns: grid?.getColumnState() || savedColumns, plans: plans.value })) }
  catch { ElMessage.warning('本机设置保存失败，请检查浏览器存储空间') }
  void nextTick(() => listRef.value?.refreshScrollbar())
}
async function savePlan() {
  const name = planName.value.trim()
  if (!name) return
  const plan: Plan = { name, filters: { ...filters }, dates: [...(dates.value || [])], pageSize: pageSize.value, columns: grid?.getColumnState() || [], visible: [...visible.value], sort: { ...sort } }
  plans.value = [...plans.value.filter(item => item.name !== name), plan].slice(-30)
  activePlan.value = name; planSelected.value = name; planOpen.value = false; planName.value = ''; savePreferences()
  ElMessage.success('查询方案已保存')
}
async function loadPlan(value: unknown) {
  const plan = plans.value.find(item => item.name === value)
  if (!plan) return
  restoring = true
  for (const key of Object.keys(filters) as (keyof typeof filters)[]) filters[key] = typeof plan.filters[key] === 'string' ? plan.filters[key] : ''
  dates.value = plan.dates.slice(0, 2); pageSize.value = [15, 50, 100, 200, 500].includes(plan.pageSize) ? plan.pageSize : 50
  Object.assign(sort, plan.sort || { sort: 'date', direction: 'desc' }); page.value = 1
  visible.value = plan.visible.filter(key => metadata.value?.fields.some(field => field.key === key))
  activePlan.value = plan.name
  await nextTick(); grid?.applyColumnState({ state: plan.columns, applyOrder: true })
  restoring = false; savePreferences(); scheduleFetch()
}
function reset() { Object.assign(filters, { keyword: '', project_code: '', supplier: '', progress: '' }); dates.value = []; page.value = 1; activePlan.value = '当前查询'; planSelected.value = '' }
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
const columns = computed<(ColDef<PurchaseRow> | ColGroupDef<PurchaseRow>)[]>(() => [
  ...groups.value.map(group => ({ headerName: group.label, groupId: group.key, children: group.fields.map(field => ({
    field: field.key, colId: field.key, headerName: field.label, headerTooltip: field.description,
    initialWidth: field.key === 'material_name' || field.key === 'specification' ? 180 : field.value_type === 'number' ? 125 : 136,
    initialPinned: ['project_code', 'material_name'].includes(field.key) ? 'left' as const : field.key === 'progress' ? 'right' as const : undefined,
    hide: !visible.value.includes(field.key), minWidth: 80, maxWidth: 800,
    sortable: Boolean(sortFields[field.key]),
    cellClass: field.value_type === 'number' ? 'purchase-number' : undefined,
    valueFormatter: (params: { data?: PurchaseRow }) => params.data ? display(params.data, field) : '',
    tooltipValueGetter: (params: { data?: PurchaseRow }) => params.data ? display(params.data, field) : '',
    cellRenderer: field.key === 'progress' ? Progress : undefined,
  })) })),
  { colId: 'purchase_actions', headerName: '操作', pinned: 'right', lockPosition: 'right', ...PMS_ACTION_COLUMN, cellRenderer: Actions, cellClass: 'pms-action-cell' },
])
const defaultColDef: ColDef = { resizable: true, sortable: false, editable: false, cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }
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
function onSortChanged() {
  if (restoring) return
  const column = grid?.getColumnState().find(state => state.sort && sortFields[state.colId])
  Object.assign(sort, { sort: column ? sortFields[column.colId] : 'date', direction: column?.sort || 'desc' })
  page.value = 1; savePreferences()
}
let revision = 0, controller: AbortController | null = null, timer: ReturnType<typeof setTimeout> | undefined
const params = () => ({ ...filters, ...sort, date_from: dates.value?.[0] || undefined, date_to: dates.value?.[1] || undefined, page: page.value, page_size: pageSize.value })
async function fetchRows() {
  const current = ++revision
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try {
    const data = await getPurchaseRows(params(), controller.signal)
    if (current !== revision) return
    rows.value = data.items; total.value = data.total; stamp.value = data.queried_at
    detail.reconcileRows(rows.value.map(row => String(row.id)))
    if (page.value > 1 && !rows.value.length && total.value) page.value = Math.ceil(total.value / pageSize.value)
    await nextTick(); listRef.value?.refreshScrollbar()
  } catch { if (current === revision) { rows.value = []; total.value = 0; detail.close(); error.value = '采购数据加载失败，请重试' } }
  finally { if (current === revision) loading.value = false }
}
function scheduleFetch() {
  if (restoring || !metadata.value) return
  ++revision; controller?.abort(); clearTimeout(timer); timer = setTimeout(fetchRows, 300)
}
async function initialize() {
  loading.value = true; error.value = ''
  try { metadata.value = await getPurchaseMetadata(); readPreferences(); await nextTick(); await fetchRows() }
  catch { error.value = '报表初始化失败，请重试'; loading.value = false }
}
async function exportRows() {
  if (exporting.value) return
  if (total.value > (metadata.value?.export_limit || 500)) { ElMessage.warning('单次最多导出 500 条，请缩小筛选范围'); return }
  exporting.value = true
  try { const blob = await exportPurchaseRows(params()); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = '采购进度查询.csv'; link.click(); URL.revokeObjectURL(url) }
  catch { /* Shared handler displays safe errors. */ }
  finally { exporting.value = false }
}
function stateLabel(row: PurchaseDocument) { return row.cancel_status === 'B' ? '已作废' : metadata.value?.document_status_labels[row.document_status] || '未知状态' }
function orderLabel(id?: number) { const order = detailState.value.data?.orders.find(row => row.id === id); return order ? `${order.bill_no} / ${order.line_no}` : '-' }
watch([filters, dates, pageSize], () => { page.value = 1 }, { deep: true, flush: 'sync' })
watch([filters, dates, page, pageSize, sort], scheduleFetch, { deep: true })
onMounted(initialize)
onUnmounted(() => { ++revision; controller?.abort(); clearTimeout(timer); detail.close(); grid = null })
</script>

<template>
  <PmsDataList ref="listRef" class="purchase-page" scrollbar-label="采购进度横向滚动条">
    <template #toolbar-left>
      <div class="purchase-plan"><PmsSelectControl v-model="planSelected" :options="planOptions" :placeholder="activePlan" size="compact" aria-label="查询方案" @update:model-value="loadPlan" /></div>
      <el-button size="small" @click="planOpen = true">保存查询方案</el-button>
    </template>
    <template #toolbar-right>
      <span v-if="stamp" class="purchase-stamp">查询时间 {{ new Date(stamp).toLocaleTimeString('zh-CN', { hour12: false }) }}</span>
      <el-tooltip content="刷新"><el-button size="small" :icon="Refresh" aria-label="刷新采购数据" :disabled="loading" @click="metadata ? fetchRows() : initialize()" /></el-tooltip>
      <el-button v-if="auth.hasPermission('report:purchase:export')" size="small" :icon="Download" :loading="exporting" :disabled="loading || !total" @click="exportRows">导出</el-button>
      <PmsListColumnPicker v-if="metadata" v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="() => grid" aria-label="采购进度列设置" @layout-changed="savePreferences" />
    </template>
    <template #filters>
      <PmsListFilters :filters="[]" :fields="[]" :active-count="0">
        <div class="purchase-filter purchase-filter--search"><PmsTextControl v-model="filters.keyword" size="compact" :prefix-icon="Search" clearable placeholder="申请单 / 物料编码 / 名称 / 规格" aria-label="搜索采购明细" /></div>
        <div class="purchase-filter"><PmsSelectControl v-model="filters.project_code" :options="candidates.project" :loading="optionLoading.project" remote filterable :remote-method="(value: string) => findOptions('project', value)" size="compact" clearable placeholder="全部项目" aria-label="项目编号筛选" @visible-change="(open: boolean) => open && findOptions('project')" /></div>
        <div class="purchase-filter"><PmsSelectControl v-model="filters.supplier" :options="candidates.supplier" :loading="optionLoading.supplier" remote filterable :remote-method="(value: string) => findOptions('supplier', value)" size="compact" clearable placeholder="全部供应商" aria-label="供应商筛选" @visible-change="(open: boolean) => open && findOptions('supplier')" /></div>
        <div class="purchase-filter purchase-filter--dates"><PmsDateControl v-model="dates" type="daterange" size="compact" value-format="YYYY-MM-DD" start-placeholder="申请开始日期" end-placeholder="申请结束日期" aria-label="申请日期范围" /></div>
        <el-button size="small" @click="reset">重置</el-button>
      </PmsListFilters>
      <div class="purchase-tabs" role="group" aria-label="采购进度筛选">
        <button :class="{ selected: !filters.progress }" :aria-pressed="!filters.progress" @click="filters.progress = ''">全部</button>
        <button v-for="(label, key) in metadata?.progress_labels" :key="key" :class="{ selected: filters.progress === key }" :aria-pressed="filters.progress === key" @click="filters.progress = String(key)">{{ label }}</button>
        <span class="purchase-scope-note">申请日期：{{ metadata?.start_date || '2026-01-01' }} 起</span>
      </div>
    </template>
    <template #grid>
      <div v-if="error" class="pms-list-load-error" role="alert">{{ error }} <el-button size="small" @click="metadata ? fetchRows() : initialize()">重试</el-button></div>
      <AgGridVue v-if="metadata" class="ag-theme-alpine wechat-table pms-ag-grid" theme="legacy"
        :row-data="rows" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS"
        :locale-text="chineseLocaleText" :loading="loading" :pagination="false" :row-height="36"
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
      <div><span>{{ activeRow?.bill_no }} / 第 {{ activeRow?.line_no }} 行</span><h2>{{ activeRow?.material_name || '采购关联明细' }}</h2><p>申请数量 {{ number(activeRow?.requested) }} {{ activeRow?.unit_name }}</p></div>
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
  <PmsFormDrawer v-model="planOpen" title="保存查询方案"><PmsFormField field-id="purchase-plan-name" label="方案名称" required><PmsTextControl id="purchase-plan-name" v-model="planName" maxlength="40" aria-label="方案名称" @keyup.enter="savePlan" /></PmsFormField><template #footer><el-button @click="planOpen = false">取消</el-button><el-button type="primary" :disabled="!planName.trim()" @click="savePlan">保存</el-button></template></PmsFormDrawer>
</template>

<style scoped>
.purchase-plan { width: 160px; }
.purchase-filter { width: 150px; max-width: 100%; }
.purchase-filter--search { width: 250px; }
.purchase-filter--dates { width: 280px; }
.purchase-stamp { color: var(--pms-text-muted); font-size: 11px; }
.purchase-tabs { display: flex; gap: 20px; flex-wrap: wrap; border-bottom: 1px solid var(--pms-border-soft); margin-bottom: 12px; }
.purchase-tabs button { border: 0; border-bottom: 2px solid transparent; background: transparent; padding: 10px 0; color: var(--pms-text-secondary); font: inherit; font-size: 12px; cursor: pointer; }
.purchase-tabs button.selected { color: var(--pms-primary); border-color: var(--pms-primary); }
.purchase-scope-note { align-self: center; margin-left: auto; font-size: 11px; color: var(--pms-text-muted); }
.purchase-loading, .purchase-empty { text-align: center; padding: 28px; color: var(--pms-text-secondary); }
.purchase-trace { position: fixed; right: 16px; top: 76px; bottom: 16px; width: 760px; max-width: calc(100vw - 32px); background: var(--pms-surface); border: 1px solid var(--pms-border); border-radius: 8px; box-shadow: -4px 0 18px rgb(16 24 40 / 4%); z-index: 50; display: flex; flex-direction: column; font-family: var(--pms-font); }
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
.purchase-detail-table th { background: var(--pms-bg-soft); color: var(--pms-text-secondary); font-size: 11px; font-weight: 500; }
.purchase-detail-table .purchase-number { text-align: right; }
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
  .purchase-page :deep(.pms-data-list-pagination) { min-width: 700px; }
}
</style>
