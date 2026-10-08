<script setup lang="ts">
import { computed, defineComponent, h, reactive, ref } from 'vue'
import { Document, Folder, Menu, Setting, Download } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColGroupDef } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsReportQueryBar from '@/report-query/PmsReportQueryBar.vue'
import PmsReportPlans from '@/report-query/PmsReportPlans.vue'
import PmsReportQuerySurface from '@/report-query/PmsReportQuerySurface.vue'
import { PmsTextControl, PmsSelectControl, PmsDateControl } from '@/form-system'
import { cloneQuery, validateConditions, type ReportCondition, type ReportField } from '@/report-query/state'
import { chineseLocaleText } from '@/utils/agGridLocale'

ModuleRegistry.registerModules([AllCommunityModule])
const statuses = [
  { value: '', label: '全部' },
  { value: 'not_ordered', label: '未下单' },
  { value: 'ordering', label: '部分下单' },
  { value: 'receiving', label: '待入库' },
  { value: 'complete', label: '已完成' },
  { value: 'review', label: '数据待核对' },
]
const organizations = [{ value: 1, label: '8吋Bench' }, { value: 2, label: 'Single' }]
const draft = reactive({ keyword: '', organizations: [] as number[], project: '', supplier: '', dates: [] as string[], conditions: [] as ReportCondition[] })
const applied = ref<typeof draft | null>(null)
const plans = ref<InstanceType<typeof PmsReportPlans>>()
const collapsed = ref(false), page = ref(1), pageSize = ref(50)
const fields: ReportField[] = [
  { field: 'material_name', label: '物料名称', type: 'text' },
  { field: 'bill_no', label: '申请单编号', type: 'text' },
  { field: 'requested', label: '申请数量', type: 'number' },
  { field: 'application_date', label: '申请日期', type: 'date' },
  { field: 'progress', label: '采购进度', type: 'enum', options: statuses.slice(1) },
]
const invalid = computed(() => validateConditions(draft.conditions, fields))
const dirty = computed(() => !!applied.value && JSON.stringify(draft) !== JSON.stringify(applied.value))
const progressConditions = computed(() => draft.conditions.filter(c => c.field === 'progress'))
const selected = computed(() => {
  if (!progressConditions.value.length) return ''
  const condition = progressConditions.value[0]
  return progressConditions.value.length === 1 && condition.operator === 'equals' ? condition.value : 'custom'
})
const source = Array.from({ length: 120 }, (_, i) => {
  const progress = statuses[1 + i % 5]!
  const requested = [20, 10, 60, 8, 4][i % 5]!
  return {
    id: i + 1, organization: 1 + i % 2, product_line: organizations[i % 2]!.label,
    project_code: ['A-202638', 'SS-202603-02', 'L_B-202608'][i % 3],
    material_name: ['PFA管', 'PUS-Guide外侧齿01', '气体过滤器', '卡套接头', '运输费'][i % 5],
    bill_no: `CGSQ${30960 - Math.floor(i / 10)}`, line_no: 10 - i % 10,
    application_date: '2026-09-24', unit: i % 5 === 0 ? '米' : 'Pcs',
    document_status: progress.value === 'review' ? '审核中' : '已审核',
    supplier: i % 2 ? '供应商甲' : '供应商乙',
    requested, ordered: progress.value === 'not_ordered' || progress.value === 'review' ? 0 : progress.value === 'ordering' ? requested / 2 : requested,
    received: progress.value === 'complete' ? requested : progress.value === 'receiving' ? requested / 2 : 0,
    progress: progress.value, progress_label: progress.label,
  }
})
function matchesCondition(row: typeof source[number], c: ReportCondition) {
  const value = row[c.field as keyof typeof row]
  const a = String(value ?? ''), b = String(c.value ?? '')
  if (c.operator === 'isEmpty') return value === null || value === undefined || a === ''
  if (c.operator === 'notEmpty') return value !== null && value !== undefined && a !== ''
  if (c.operator === 'equals') return a === b
  if (c.operator === 'notEquals') return a !== b
  if (c.operator === 'contains') return a.includes(b)
  if (c.operator === 'notContains') return !a.includes(b)
  if (c.operator === 'startsWith') return a.startsWith(b)
  if (c.operator === 'endsWith') return a.endsWith(b)
  const numeric = fields.find(f => f.field === c.field)?.type === 'number'
  const left = numeric ? Number(value) : a, right = numeric ? Number(c.value) : b
  if (c.operator === 'greaterThan') return left > right
  if (c.operator === 'greaterOrEqual') return left >= right
  if (c.operator === 'lessThan') return left < right
  if (c.operator === 'lessOrEqual') return left <= right
  if (c.operator === 'between') return left >= right && left <= (numeric ? Number(c.valueEnd) : String(c.valueEnd))
  return false
}
const result = computed(() => {
  const q = applied.value
  if (!q) return []
  return source.filter(row => (!q.keyword || `${row.material_name} ${row.bill_no}`.includes(q.keyword))
    && (!q.organizations.length || q.organizations.includes(row.organization))
    && (!q.project || row.project_code === q.project) && (!q.supplier || row.supplier === q.supplier)
    && (!q.dates?.[0] || row.application_date >= q.dates[0]) && (!q.dates?.[1] || row.application_date <= q.dates[1])
    && q.conditions.every(c => matchesCondition(row, c)))
})
const rows = computed(() => result.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const pages = computed(() => Math.max(1, Math.ceil(result.value.length / pageSize.value)))
function query() { if (invalid.value) return; applied.value = cloneQuery(draft); page.value = 1 }
function choose(value: string) {
  draft.conditions = draft.conditions.filter(c => c.field !== 'progress')
  if (value) draft.conditions.push({ id: Date.now(), field: 'progress', operator: 'equals', value, valueEnd: null })
  query()
}
function reset() {
  Object.assign(draft, { keyword: '', organizations: [], project: '', supplier: '', dates: [], conditions: [] })
  applied.value = null; page.value = 1; plans.value?.clearSelection()
}
function restore(value: unknown) { Object.assign(draft, cloneQuery(value)); page.value = 1 }
const Progress = defineComponent({ props: ['params'], setup(props) { return () => h('span', { class: ['pms-status', props.params.data.progress === 'complete' ? 'success' : props.params.data.progress === 'review' ? 'danger' : props.params.data.progress === 'ordering' ? 'warning' : 'info'] }, props.params.data.progress_label) } })
const column = (field: string, label: string, width = 132): ColDef => ({ field, headerName: label, width, minWidth: 90 })
const columns: (ColDef | ColGroupDef)[] = [
  { headerName: '物料信息', children: [{ ...column('project_code', '项目编号', 144), pinned: 'left' }, { ...column('material_name', '物料名称', 180), pinned: 'left' }] },
  { headerName: '采购申请', children: [column('product_line', '产品线', 124), column('unit', '申请单位', 100), column('bill_no', '申请单编号', 144), column('line_no', '申请单行号', 112), column('application_date', '申请日期'), column('document_status', '数据状态', 112), { ...column('requested', '申请数量', 112), cellClass: 'sample-number' }] },
  { headerName: '采购订单', children: [{ ...column('ordered', '累计下单数量', 128), cellClass: 'sample-number' }, column('supplier', '供应商', 144)] },
  { headerName: '采购入库', children: [{ ...column('received', '累计入库数量', 128), cellClass: 'sample-number' }] },
  { headerName: '进度', children: [{ ...column('progress_label', '采购进度', 132), pinned: 'right', cellRenderer: Progress }] },
  { colId: 'actions', headerName: '操作', width: 112, minWidth: 112, maxWidth: 112, pinned: 'right', resizable: false, sortable: false, cellRenderer: () => '<span class="sample-detail">明细</span>' },
]
</script>

<template>
  <div class="sample-app" :class="{ 'is-collapsed': collapsed }">
    <aside>
      <div class="sample-brand"><span>P</span><strong>PMS 管理系统</strong></div>
      <div class="sample-section"><el-icon><Folder /></el-icon><span>项目管理</span></div>
      <div class="sample-nav"><span>项目档案</span></div><div class="sample-nav"><span>项目进度</span></div>
      <div class="sample-section"><el-icon><Document /></el-icon><span>报表中心</span></div>
      <div class="sample-nav active"><el-icon><Document /></el-icon><span>采购进度查询</span></div>
      <div class="sample-nav"><span>即时库存查询</span></div><div class="sample-nav"><span>物料收发明细</span></div>
    </aside>
    <header><button aria-label="折叠菜单" @click="collapsed = !collapsed"><el-icon><Menu /></el-icon></button><strong>采购进度查询</strong><span>交互样稿 · 模拟数据</span></header>
    <main class="pms-report-query-surface">
      <PmsReportQuerySurface>
        <div class="pms-report-query-toolbar">
          <PmsReportPlans ref="plans" storage-key="pms:prototype:purchase-quick-filter:20261008" :snapshot="() => cloneQuery(draft)" @restore="restore" />
          <div class="pms-report-query-tools"><span class="pms-report-query-status" :class="{ 'is-dirty': dirty }" role="status">{{ dirty ? '条件已修改，待查询' : applied ? '已查询' : '尚未查询' }}</span><el-button :icon="Download" disabled>导出当前筛选</el-button><el-button disabled>导出任务</el-button><el-button :icon="Setting" disabled>列设置</el-button></div>
        </div>
        <PmsReportQueryBar v-model:conditions="draft.conditions" :fields="fields" :invalid="invalid" @query="query" @reset="reset">
          <div class="query-material"><PmsTextControl v-model="draft.keyword" size="compact" clearable placeholder="申请单 / 物料名称" aria-label="搜索采购明细" /></div>
          <PmsSelectControl v-model="draft.organizations" :options="organizations" size="compact" multiple collapse-tags clearable placeholder="全部产品线" aria-label="产品线" />
          <PmsSelectControl v-model="draft.project" :options="['A-202638', 'SS-202603-02', 'L_B-202608'].map(value => ({ value, label: value }))" size="compact" clearable placeholder="全部项目" aria-label="项目编号" />
          <div class="query-dates"><PmsDateControl v-model="draft.dates" size="compact" type="daterange" value-format="YYYY-MM-DD" start-placeholder="申请开始日期" end-placeholder="申请结束日期" aria-label="申请日期范围" /></div>
          <PmsSelectControl v-model="draft.supplier" :options="['供应商甲', '供应商乙'].map(value => ({ value, label: value }))" size="compact" clearable placeholder="全部供应商" aria-label="供应商" />
        </PmsReportQueryBar>
      </PmsReportQuerySurface>
      <div class="sample-progress-bar">
        <div class="sample-progress" role="group" aria-label="采购进度快捷筛选">
          <button v-for="status in statuses" :key="status.value" :aria-pressed="selected === status.value" :class="{ active: selected === status.value }" @click="choose(status.value)">{{ status.label }}</button>
        </div>
        <span v-if="selected === 'custom'" class="sample-range">自定义采购进度条件</span><span v-else class="sample-range">申请日期：2026-01-01 起</span>
      </div>
      <div class="sample-grid">
        <AgGridVue class="ag-theme-alpine pms-ag-grid" theme="legacy" :row-data="rows" :column-defs="columns" :default-col-def="{ resizable: true, sortable: true }" :locale-text="chineseLocaleText" :row-height="37" :header-height="34" :group-header-height="30" :suppress-no-rows-overlay="true" />
        <div v-if="!rows.length" class="sample-empty">{{ applied ? '暂无符合条件的数据' : '设置条件后，点击查询' }}</div>
      </div>
      <footer><span>{{ applied ? `共 ${result.length} 条` : '未查询' }}</span><div class="sample-pages"><el-button size="small" :disabled="page <= 1" aria-label="上一页" @click="page--">‹</el-button><span>{{ page }} / {{ pages }}</span><el-button size="small" :disabled="page >= pages" aria-label="下一页" @click="page++">›</el-button></div><span>50 条/页</span></footer>
    </main>
  </div>
</template>

<style>
html, body, #app { margin: 0; height: 100%; }
.sample-app { height: 100%; display: grid; grid-template-columns: 188px minmax(0, 1fr); grid-template-rows: 56px minmax(0, 1fr); background: var(--pms-bg); color: var(--pms-text); font: 13px var(--pms-font); }
.sample-app aside { grid-row: 1 / 3; background: var(--pms-surface); border-right: 1px solid var(--pms-border-soft); }
.sample-brand { height: 56px; display: flex; align-items: center; gap: 10px; padding: 0 16px; border-bottom: 1px solid var(--pms-border-soft); }
.sample-brand > span { width: 30px; height: 30px; display: grid; place-items: center; background: var(--pms-primary-soft); color: var(--pms-primary); border-radius: 6px; }
.sample-section, .sample-nav { display: flex; align-items: center; gap: 10px; height: 36px; padding: 0 16px; color: var(--pms-text-secondary); }
.sample-section { margin-top: 16px; }.sample-nav { margin: 2px 8px; padding-left: 28px; border-radius: 6px; }.sample-nav.active { color: var(--pms-primary); background: var(--pms-primary-soft); font-weight: 600; }
.sample-app header { display: flex; align-items: center; gap: 12px; padding: 0 20px; background: var(--pms-surface); border-bottom: 1px solid var(--pms-border-soft); }
.sample-app header button { display: grid; place-items: center; padding: 4px; border: 0; background: none; color: var(--pms-text-secondary); cursor: pointer; }.sample-app header > span { margin-left: auto; color: var(--pms-text-muted); font-size: 12px; }
.sample-app main { margin: 16px; padding: 16px; min-width: 0; min-height: 0; background: var(--pms-surface); border: 1px solid var(--pms-border-soft); border-radius: 8px; display: flex; flex-direction: column; }
.sample-progress-bar { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 36px; margin-bottom: 8px; border-bottom: 1px solid var(--pms-border-soft); }
.sample-progress { display: flex; gap: 20px; min-width: 0; overflow-x: auto; }
.sample-progress button { height: 36px; flex-shrink: 0; padding: 0 0 6px; border: 0; border-bottom: 2px solid transparent; background: none; color: var(--pms-text-secondary); font: inherit; font-size: 12px; cursor: pointer; }
.sample-progress button:hover { color: var(--pms-primary); }.sample-progress button.active { color: var(--pms-primary); border-bottom-color: var(--pms-primary); font-weight: 600; }
.sample-app button:focus-visible { outline: 2px solid var(--pms-primary); outline-offset: -2px; }
.sample-range { color: var(--pms-text-muted); font-size: 12px; white-space: nowrap; }
.sample-grid { position: relative; flex: 1; min-height: 0; }.sample-grid > .ag-theme-alpine { height: 100%; width: 100%; }
/* Preview-only alignment; approved rollout will live in the shared table theme. */
.sample-grid .ag-header-cell-label, .sample-grid .ag-header-group-cell-label { justify-content: center; }
.sample-grid .sample-number { justify-content: flex-end; font-variant-numeric: tabular-nums; }
.sample-detail { color: var(--pms-primary); font-size: 12px; }
.sample-empty { position: absolute; inset: 64px 0 0; display: grid; place-items: center; pointer-events: none; color: var(--pms-text-muted); }
.sample-app footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-top: 10px; color: var(--pms-text-secondary); font-size: 12px; }.sample-pages { display: flex; align-items: center; gap: 12px; font-variant-numeric: tabular-nums; }
.sample-app.is-collapsed { grid-template-columns: 52px minmax(0, 1fr); }.sample-app.is-collapsed aside strong, .sample-app.is-collapsed aside .sample-nav span, .sample-app.is-collapsed .sample-section span { display: none; }.sample-app.is-collapsed .sample-nav, .sample-app.is-collapsed .sample-section { padding: 0 8px; }.sample-app.is-collapsed .sample-brand { padding: 0 10px; }
@media (max-width: 700px) { .sample-app { grid-template-columns: minmax(0, 1fr); }.sample-app aside { display: none; }.sample-app main { margin: 8px; padding: 10px; }.sample-app header { padding: 0 12px; }.sample-range { display: none; }.sample-progress { gap: 16px; }.sample-grid { overflow: auto; }.sample-grid > .ag-theme-alpine { min-width: 1050px; }.sample-app.is-collapsed { grid-template-columns: minmax(0, 1fr); } }
</style>
