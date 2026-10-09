<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { Search, Filter, Plus, Delete, Download, Document, Box, Tickets, RefreshLeft, ArrowRight, Close, Warning, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { PmsTextControl, PmsSelectControl, PmsNumberControl, PmsDateControl, PmsFormDrawer, PmsFormField } from '../../src/form-system'
import PmsListColumnPicker from '../../src/components/PmsListColumnPicker.vue'
import { PMS_GRID_OPTIONS } from '../../src/config/listUi'
import { chineseLocaleText } from '../../src/utils/agGridLocale'
import { formatStockQuantity } from '../../src/views/reports/stockDetailState'
import { clone, createSession, defaultDraft, labels, operators, organizations, stocks, reports, validate, queryRows } from './model.mjs'

ModuleRegistry.registerModules([AllCommunityModule])
const icons = { inventory: Box, purchase: Tickets, stock: Document }
const report = ref('inventory'), scenario = ref('normal')
const config = computed(() => reports[report.value])
const session = reactive(createSession(defaultDraft(report.value)))
const draft = computed(() => session.draft)
const grid = ref(null), result = ref([]), loading = ref(false), error = ref(''), stamp = ref('')
const page = ref(1), pageSize = ref(50), sort = ref({ field: '', direction: 'asc' })
const visible = ref(config.value.fields.map(f => f.key)), restoring = ref(false)
const plan = ref(''), plans = ref([]), saveOpen = ref(false), planName = ref('')
const more = ref(false), conditionDraft = ref([]), conditionError = ref('')
const detail = ref(null), exportOpen = ref(false), exported = ref([])
const expandedQuick = ref(false)
let generation = 0
const storageKey = () => `pms:prototype:report-query:v1:${report.value}`
const fieldOptions = computed(() => config.value.fields.map(f => ({ value: f.key, label: f.label })))
const planOptions = computed(() => [{ value: '', label: '当前查询' }, ...plans.value.map(p => ({ value: p.name, label: p.name }))])
const availableStocks = computed(() => stocks.filter(s => !draft.value.organizations.length || draft.value.organizations.includes(s.org)))
const invalid = computed(() => validate(report.value, draft.value))
const locked = computed(() => scenario.value === 'denied')
const canQuery = computed(() => !loading.value && !invalid.value && !locked.value)
const canExport = computed(() => !!session.applied && result.value.length > 0 && !loading.value && !locked.value)
const statusText = computed(() => loading.value ? '正在查询' : error.value ? '查询失败' : session.dirty ? '条件已修改，待查询' : session.applied ? '已查询' : '尚未查询')
const sortedRows = computed(() => {
  const rows = [...result.value]
  if (sort.value.field) rows.sort((a, b) => String(a[sort.value.field] ?? '').localeCompare(String(b[sort.value.field] ?? ''), 'zh-CN', { numeric: true }) * (sort.value.direction === 'asc' ? 1 : -1))
  return rows
})
const pageRows = computed(() => sortedRows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const groups = computed(() => [{ key: 'report', label: config.value.title, fields: config.value.fields.map(f => ({ ...f, value_type: f.type, list_available: true, quick_addable: true })) }])
function display(field, value) {
  if (value === null || value === undefined) return ''
  if (field.type === 'number') return formatStockQuantity(value)
  return field.options?.find(o => o.value === value)?.label || String(value)
}
const columns = computed(() => config.value.fields.map(f => ({
  field: f.key, colId: f.key, headerName: f.label, initialWidth: f.width, minWidth: 70, maxWidth: 800,
  hide: !visible.value.includes(f.key), initialPinned: f.key === 'material_code' || f.key === 'project' ? 'left' : undefined,
  valueFormatter: p => display(f, p.value), tooltipValueGetter: p => display(f, p.value),
  cellClass: f.type === 'number' ? 'rq-number' : undefined,
  cellRenderer: f.key === 'progress' || f.key === 'state' ? p => { const span = document.createElement('span'); span.className = 'rq-pill ' + (['可用', '已完成'].includes(p.value) ? 'ok' : ''); span.textContent = p.value || ''; return span } : undefined,
})))
const defaultColDef = { resizable: true, sortable: true, comparator: () => 0, editable: false, cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }
function readPreferences() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey()) || '{}')
    plans.value = saved.plans || []
    visible.value = saved.visible || config.value.fields.map(f => f.key)
    return saved.columns || []
  } catch { plans.value = []; return [] }
}
function persist() {
  if (restoring.value) return
  localStorage.setItem(storageKey(), JSON.stringify({ visible: visible.value, plans: plans.value, columns: grid.value?.getColumnState() || [] }))
}
function gridReady(e) { grid.value = e.api; const state = readPreferences(); restoring.value = true; if (state.length) grid.value.applyColumnState({ state, applyOrder: true }); restoring.value = false }
function onSort() { if (restoring.value) return; const item = grid.value?.getColumnState().find(c => c.sort); sort.value = { field: item?.colId || '', direction: item?.sort || 'asc' }; page.value = 1 }
function invalidate() { ++generation; loading.value = false }
watch(report, () => {
  invalidate(); session.restore(defaultDraft(report.value)); session.applied = null; result.value = []; error.value = ''; stamp.value = ''; page.value = 1; sort.value = { field: '', direction: 'asc' }; detail.value = null; more.value = false; plan.value = ''; grid.value = null; visible.value = config.value.fields.map(f => f.key); readPreferences()
})
watch(scenario, () => { invalidate(); error.value = ''; if (locked.value) { result.value = []; session.applied = null; detail.value = null } })
function orgChanged() { draft.value.stock = '' }
async function query() {
  if (!canQuery.value) return
  const revision = ++generation, submitted = clone(draft.value), kind = report.value
  loading.value = true; error.value = ''; detail.value = null
  await new Promise(resolve => setTimeout(resolve, 400))
  if (revision !== generation) return
  loading.value = false
  if (scenario.value === 'error') { error.value = '模拟数据源暂时不可用，请重试'; return }
  session.applied = submitted; result.value = queryRows(kind, submitted); page.value = 1
  stamp.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}
function reset() { invalidate(); session.restore(defaultDraft(report.value)); plan.value = ''; error.value = '' }
function openMore() { conditionDraft.value = clone(draft.value.conditions); conditionError.value = '' }
function conditionField(c) { return config.value.fields.find(f => f.key === c.field) }
function addCondition() { const f = config.value.fields[0]; conditionDraft.value.push({ id: Date.now() + Math.random(), field: f.key, type: f.type, op: operators(f.type)[0], value: '', end: '' }) }
function changeField(c) { const f = conditionField(c); c.type = f.type; c.op = operators(f.type)[0]; c.value = ''; c.end = ''; conditionError.value = '' }
function changeOp(c) { c.value = ['in', 'notIn'].includes(c.op) ? [] : c.type === 'number' ? null : ''; c.end = ''; conditionError.value = '' }
function applyMore() {
  conditionError.value = validate('inventory', { conditions: conditionDraft.value })
  if (conditionError.value) return
  draft.value.conditions = clone(conditionDraft.value); more.value = false
}
function describe(c) {
  const f = config.value.fields.find(f => f.key === c.field)
  const value = Array.isArray(c.value) ? c.value.map(v => display(f, v)).join('、') : display(f, c.value)
  return `${f?.label || ''} ${labels[c.op]}${['empty', 'notEmpty'].includes(c.op) ? '' : ' ' + value + (c.op === 'between' ? ' 至 ' + display(f, c.end) : '')}`
}
function loadPlan() {
  if (!plan.value) return
  const item = plans.value.find(p => p.name === plan.value)
  if (!item) return
  invalidate(); session.restore(item.filters); visible.value = [...item.visible]; pageSize.value = item.pageSize
  restoring.value = true
  nextTick(() => { grid.value?.applyColumnState({ state: item.columns, applyOrder: true }); restoring.value = false; persist() })
}
function savePlan() {
  if (!planName.value.trim()) return
  const name = planName.value.trim()
  const item = { name, filters: clone(draft.value), visible: [...visible.value], columns: grid.value?.getColumnState() || [], pageSize: pageSize.value }
  plans.value = [...plans.value.filter(p => p.name !== name), item]; plan.value = name; persist(); saveOpen.value = false; ElMessage.success('查询方案已保存到此样稿')
}
function exportSample() {
  const quote = value => '"' + String(value ?? '').replaceAll('"', '""') + '"'
  const fields = grid.value.getAllDisplayedColumns().map(c => config.value.fields.find(f => f.key === c.getColId())).filter(Boolean)
  const csv = '\uFEFF' + [fields.map(f => quote(f.label)).join(','), ...sortedRows.value.map(row => fields.map(f => quote(display(f, row[f.key]))).join(','))].join('\r\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })), a = document.createElement('a')
  a.href = url; a.download = `${config.value.title}-模拟数据.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  exportOpen.value = false; exported.value = clone(sortedRows.value); ElMessage.success('已导出上次查询的模拟结果')
}
readPreferences()
</script>

<template>
  <div class="rq-shell">
    <aside class="rq-sidebar">
      <div class="rq-brand"><span>P</span><strong>PMS 管理系统</strong></div>
      <div class="rq-nav-label">报表中心</div>
      <nav aria-label="样稿报表"><button v-for="(r, key) in reports" :key="key" :class="{ active: report === key }" @click="report = key"><el-icon><component :is="icons[key]" /></el-icon>{{ r.title }}<el-icon v-if="report === key" class="rq-nav-arrow"><ArrowRight /></el-icon></button></nav>
      <div class="rq-sidebar-foot">统一查询模块<span>交互样稿 · v1</span></div>
    </aside>
    <main class="rq-main">
      <header class="rq-header"><div class="rq-breadcrumb">报表中心 <el-icon><ArrowRight /></el-icon><strong>{{ config.title }}</strong></div><div class="rq-preview"><span>样稿 · 模拟数据</span><PmsSelectControl v-model="scenario" size="compact" :options="[{value:'normal',label:'正常状态'},{value:'error',label:'模拟查询失败'},{value:'denied',label:'无查看权限'}]" aria-label="样稿状态" /></div></header>
      <section class="rq-workspace">
        <section class="rq-report" :aria-label="config.title">
          <div class="rq-toolbar">
            <div class="rq-status" role="status"><span :class="{ dirty: session.dirty, failed: error }"><i />{{ locked ? '无查看权限' : statusText }}</span><span v-if="session.applied && !locked">{{ stamp }} · {{ result.length }} 条</span></div>
            <div class="rq-plans"><PmsSelectControl v-model="plan" :options="planOptions" aria-label="查询方案" size="compact" @update:model-value="loadPlan" /><el-button size="small" :disabled="locked" @click="saveOpen = true; planName = plan">保存方案</el-button></div>
            <div class="rq-tools"><el-tooltip :content="session.dirty ? '导出上次已执行查询的结果' : '导出已查询的模拟结果'"><span><el-button :icon="Download" size="small" :disabled="!canExport" @click="exportOpen = true">导出</el-button></span></el-tooltip><PmsListColumnPicker v-model="visible" :groups="groups" :default-keys="config.fields.map(f => f.key)" :column-definitions="columns" :get-grid-api="() => grid" aria-label="报表列设置" @layout-changed="persist" /></div>
          </div>
          <form class="rq-quick" :class="{ 'rq-expanded': expandedQuick }" @submit.prevent="query">
            <label class="rq-quick-field rq-material"><span>物料 <b v-if="report === 'stock'">*</b></span><PmsTextControl v-model="draft.material" :disabled="locked" :prefix-icon="Search" clearable size="compact" placeholder="编码 / 名称" aria-label="物料" /></label>
            <template v-if="report !== 'purchase'">
              <label class="rq-quick-field rq-org"><span>库存组织 <b v-if="report === 'stock'">*</b></span><PmsSelectControl v-model="draft.organizations" :disabled="locked" :options="organizations" multiple collapse-tags collapse-tags-tooltip filterable clearable size="compact" :placeholder="report === 'stock' ? '请选择' : '全部授权组织'" aria-label="库存组织" @update:model-value="orgChanged" /></label>
              <label class="rq-quick-field rq-stock"><span>仓库</span><PmsSelectControl v-model="draft.stock" :disabled="locked || (report === 'stock' && !draft.organizations.length)" :options="availableStocks" filterable clearable size="compact" placeholder="全部仓库" aria-label="仓库" /></label>
            </template>
            <label v-if="report !== 'inventory'" class="rq-quick-field rq-date"><span>{{ report === 'purchase' ? '申请日期' : '日期范围' }} <b v-if="report === 'stock'">*</b></span><PmsDateControl v-model="draft.dates" :disabled="locked" type="daterange" size="compact" start-placeholder="开始日期" end-placeholder="结束日期" aria-label="日期范围" /></label>
            <label v-if="report === 'purchase'" class="rq-quick-field rq-stock"><span>采购进度</span><PmsSelectControl v-model="draft.progress" :disabled="locked" clearable :options="reports.purchase.fields.find(f => f.key === 'progress').options" size="compact" placeholder="全部进度" aria-label="采购进度" /></label>
            <div class="rq-query-actions"><el-tooltip :disabled="!invalid" :content="invalid"><span><el-button type="primary" size="small" :icon="Search" :loading="loading" :disabled="!canQuery" native-type="submit">查询</el-button></span></el-tooltip><el-button size="small" :disabled="locked" :icon="RefreshLeft" @click="reset">重置</el-button><el-button class="rq-expand" size="small" :aria-expanded="expandedQuick" @click="expandedQuick = !expandedQuick">{{ expandedQuick ? '收起' : '其他条件' }}</el-button>
              <el-popover v-model:visible="more" trigger="click" placement="bottom-end" :width="730" popper-class="rq-condition-popper">
                <template #reference><el-button size="small" :disabled="locked" :icon="Filter" @click="openMore">更多条件<span v-if="draft.conditions.length" class="rq-count">{{ draft.conditions.length }}</span></el-button></template>
                <div class="rq-condition-panel" role="dialog" aria-label="更多条件">
                  <div class="rq-panel-head"><strong>筛选条件</strong><span>同时满足全部条件</span></div>
                  <div class="rq-condition-labels"><span>字段</span><span>运算符</span><span>值</span></div>
                  <div class="rq-condition-body">
                    <div v-if="!conditionDraft.length" class="rq-condition-empty">尚未添加条件</div>
                    <div v-for="(c, i) in conditionDraft" :key="c.id" class="rq-condition-row">
                      <PmsSelectControl v-model="c.field" :options="fieldOptions" filterable size="compact" :aria-label="`条件${i+1}字段`" @update:model-value="changeField(c)" />
                      <PmsSelectControl v-model="c.op" :options="operators(c.type).map(value => ({ value, label: labels[value] }))" size="compact" :aria-label="`条件${i+1}运算符`" @update:model-value="changeOp(c)" />
                      <div class="rq-condition-value">
                        <span v-if="['empty','notEmpty'].includes(c.op)" class="rq-no-value">无需填写值</span>
                        <PmsSelectControl v-else-if="c.type === 'select'" :key="c.op" v-model="c.value" :options="conditionField(c).options" :multiple="['in','notIn'].includes(c.op)" collapse-tags filterable size="compact" :aria-label="`条件${i+1}值`" placeholder="请选择" />
                        <template v-else-if="c.type === 'number'"><PmsNumberControl v-model="c.value" :controls="false" size="compact" :aria-label="`条件${i+1}值`" /><template v-if="c.op === 'between'"><span>至</span><PmsNumberControl v-model="c.end" :controls="false" size="compact" :aria-label="`条件${i+1}结束值`" /></template></template>
                        <template v-else-if="c.type === 'date'"><PmsDateControl v-model="c.value" size="compact" :aria-label="`条件${i+1}值`" /><template v-if="c.op === 'between'"><span>至</span><PmsDateControl v-model="c.end" size="compact" :aria-label="`条件${i+1}结束值`" /></template></template>
                        <PmsTextControl v-else v-model="c.value" clearable size="compact" :aria-label="`条件${i+1}值`" placeholder="输入筛选值" />
                      </div>
                      <el-button :icon="Delete" text :aria-label="`删除条件${i+1}`" title="删除条件" @click="conditionDraft.splice(i,1)" />
                    </div>
                  </div>
                  <div v-if="conditionError" class="rq-validation" role="alert">{{ conditionError }}</div>
                  <el-button class="rq-add" :icon="Plus" size="small" text type="primary" @click="addCondition">添加条件</el-button>
                  <footer class="rq-panel-footer"><el-button size="small" text @click="conditionDraft = []; conditionError = ''">清空条件</el-button><div><el-button size="small" @click="more = false">取消</el-button><el-button size="small" type="primary" @click="applyMore">应用条件</el-button></div></footer>
                </div>
              </el-popover>
            </div>
          </form>
          <div v-if="draft.conditions.length" class="rq-tags"><span v-for="(c,i) in draft.conditions" :key="c.id" class="rq-tag">{{ describe(c) }}<button :aria-label="`移除筛选${i+1}`" title="移除筛选" @click="draft.conditions.splice(i,1)"><el-icon><Close /></el-icon></button></span></div>
          <div v-if="error" class="rq-error" role="alert"><el-icon><Warning /></el-icon>{{ error }}<span v-if="session.applied">下方仍为上次查询结果</span><el-button text size="small" @click="query">重试</el-button></div>
          <div class="rq-grid-wrap">
            <AgGridVue :key="report" class="ag-theme-alpine wechat-table pms-ag-grid rq-grid" theme="legacy" :column-defs="columns" :default-col-def="defaultColDef" :row-data="locked ? [] : pageRows" :grid-options="PMS_GRID_OPTIONS" :locale-text="chineseLocaleText" :loading="loading" :suppress-no-rows-overlay="true" :row-height="38" :header-height="38" :get-row-id="p => String(p.data.id)" :suppress-multi-sort="true" :pagination="false" @grid-ready="gridReady" @sort-changed="onSort" @row-clicked="e => detail && (detail = e.data)" @row-double-clicked="e => detail = e.data" @column-resized="e => e.finished && persist()" />
            <div v-if="!loading && (!session.applied || !result.length || locked)" class="rq-empty"><el-icon><Lock v-if="locked" /><Search v-else /></el-icon><strong>{{ locked ? '当前角色无报表查看权限' : session.applied ? '没有符合条件的数据' : '设置条件后，点击查询' }}</strong><span>{{ locked ? '请联系系统管理员' : session.applied ? '调整条件后重新查询' : '进入页面不会自动查询业务数据' }}</span></div>
          </div>
          <footer class="rq-pagination"><span>{{ session.applied ? `共 ${result.length} 条` : '未查询' }}</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="result.length" :disabled="!session.applied || loading || locked" layout="prev, pager, next" /><PmsSelectControl v-model="pageSize" :options="[15,50,100,200].map(value => ({value,label:`${value} 条/页`}))" size="compact" aria-label="每页条数" @update:model-value="page = 1" /></footer>
        </section>
      </section>
    </main>
    <PmsFormDrawer v-model="saveOpen" title="保存查询方案" width="420px" :busy="false" @submit="savePlan"><PmsFormField label="方案名称" required><PmsTextControl v-model="planName" aria-label="方案名称" placeholder="例如：研发仓可用物料" /></PmsFormField><p class="rq-help">保存当前条件、显示列、排列、冻结、列宽及每页条数。保存后不自动查询。</p><template #footer><el-button @click="saveOpen = false">取消</el-button><el-button type="primary" :disabled="!planName.trim()" @click="savePlan">保存</el-button></template></PmsFormDrawer>
    <PmsFormDrawer :model-value="!!detail" title="记录详情" width="440px" @update:model-value="v => !v && (detail = null)"><dl v-if="detail" class="rq-detail"><template v-for="f in config.fields" :key="f.key"><dt>{{ f.label }}</dt><dd>{{ display(f, detail[f.key]) }}</dd></template></dl><template #footer><el-button @click="detail = null">关闭</el-button></template></PmsFormDrawer>
    <el-dialog v-model="exportOpen" title="导出查询结果" width="430px"><p>将导出上次查询的 {{ result.length }} 条模拟数据。</p><p v-if="session.dirty" class="rq-validation">当前修改的条件尚未查询，不包含在本次导出中。</p><template #footer><el-button @click="exportOpen = false">取消</el-button><el-button type="primary" @click="exportSample">导出模拟 CSV</el-button></template></el-dialog>
  </div>
</template>

<style>
html, body, #app { height: 100%; }
.rq-shell { display: flex; height: 100%; min-height: 630px; font-size: 13px; }
.rq-sidebar { width: 196px; flex-shrink: 0; display: flex; flex-direction: column; background: var(--pms-surface); border-right: 1px solid var(--pms-border-soft); }
.rq-brand { height: 64px; padding: 0 20px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--pms-border-soft); }
.rq-brand>span { display: grid; place-items: center; width: 30px; height: 32px; border: 1px solid var(--pms-border); background: var(--pms-primary-soft); color: var(--pms-primary); border-radius: 6px; font-weight: 600; }
.rq-brand strong { font-size: 14px; }
.rq-nav-label { margin: 30px 22px 12px; color: var(--pms-text-muted); font-size: 11px; }
.rq-sidebar nav { padding: 0 10px; }
.rq-sidebar nav button { display: flex; align-items: center; gap: 10px; width: 100%; padding: 12px; margin-bottom: 5px; border: 0; border-radius: 6px; color: var(--pms-text-secondary); background: transparent; cursor: pointer; text-align: left; }
.rq-sidebar nav button:hover { background: var(--pms-bg-soft); }
.rq-sidebar nav button.active { color: var(--pms-primary); background: var(--pms-primary-soft); font-weight: 500; }
.rq-nav-arrow { margin-left: auto; }
.rq-sidebar-foot { margin-top: auto; padding: 20px 22px; color: var(--pms-text-secondary); font-size: 12px; }
.rq-sidebar-foot span { display: block; color: var(--pms-text-muted); margin-top: 5px; font-size: 11px; }
.rq-main { min-width: 0; flex: 1; display: flex; flex-direction: column; }
.rq-header { height: 64px; flex-shrink: 0; display: flex; justify-content: space-between; align-items: center; padding: 0 24px; background: var(--pms-surface); border-bottom: 1px solid var(--pms-border-soft); gap: 12px; }
.rq-breadcrumb { display: flex; align-items: center; gap: 12px; color: var(--pms-text-muted); white-space: nowrap; font-size: 12px; }
.rq-breadcrumb strong { font-weight: 500; color: var(--pms-text); }
.rq-preview { display: flex; align-items: center; gap: 16px; color: var(--pms-text-muted); font-size: 11px; }
.rq-preview>.pms-form-control { width: 138px; }
.rq-workspace { padding: 22px 24px 20px; flex: 1; min-height: 0; display: flex; flex-direction: column; }
.rq-report { display: flex; flex: 1; min-height: 0; flex-direction: column; background: var(--pms-surface); border: 1px solid var(--pms-border); border-radius: 8px; padding: 0 18px; }
.rq-toolbar { min-height: 52px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--pms-border-soft); }
.rq-plans, .rq-tools { display: flex; align-items: center; gap: 8px; }
.rq-plans>.pms-form-control { width: 205px; }
.rq-tools>.el-button+.el-button, .rq-query-actions>.el-button+.el-button { margin-left: 0; }
.rq-quick { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; padding: 10px 0; }
.rq-quick-field { display: flex; align-items: center; gap: 6px; flex: 0 0 190px; min-width: 0; max-width: none; }
.rq-quick-field>span { flex-shrink: 0; white-space: nowrap; }
.rq-quick-field>.pms-form-control { flex: 1; min-width: 0; width: 0; }
.rq-quick-field>span { font-size: 12px; color: var(--pms-text-secondary); }
.rq-quick-field b { color: var(--pms-danger); font-weight: 400; }
.rq-material { flex-basis: 215px; }
.rq-date { flex-basis: 290px; }
.rq-org { flex-basis: 215px; }
.rq-expand { display: none; }
.rq-query-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.rq-count { display: inline-grid; place-items: center; margin-left: 5px; width: 16px; height: 16px; border-radius: 4px; background: var(--pms-primary-soft); color: var(--pms-primary); font-size: 11px; }
.rq-tags { display: flex; flex-wrap: wrap; gap: 8px; padding-bottom: 12px; }
.rq-tag { display: inline-flex; align-items: center; gap: 8px; font-size: 11px; padding: 4px 7px 4px 9px; background: var(--pms-bg-soft); border: 1px solid var(--pms-border); border-radius: 4px; color: var(--pms-text-secondary); }
.rq-tag button { padding: 0; border: 0; display: inline-flex; color: var(--pms-text-muted); background: transparent; cursor: pointer; }
.rq-status { display: flex; align-items: center; gap: 10px; margin-left: auto; order: 1; font-size: 11px; color: var(--pms-text-muted); }
.rq-tools { order: 2; }
.rq-plans { order: 0; }
.rq-status>span:first-child { display: flex; align-items: center; gap: 6px; }
.rq-status i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.rq-status .dirty { color: var(--pms-warning); }
.rq-status .failed, .rq-validation { color: var(--pms-danger); }
.rq-grid-wrap { position: relative; flex: 1; min-height: 210px; }
.rq-grid { height: 100%; min-height: 210px; width: 100%; }
.rq-number { text-align: right; font-variant-numeric: tabular-nums; }
.rq-pill { font-size: 11px; padding: 3px 8px; color: var(--pms-text-secondary); border-radius: 12px; background: var(--pms-neutral-soft); }
.rq-pill.ok { background: var(--pms-success-soft); color: var(--pms-success); }
.rq-empty { position: absolute; top: 40px; bottom: 0; left: 0; right: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; pointer-events: none; gap: 12px; color: var(--pms-text-muted); }
.rq-empty>.el-icon { font-size: 26px; margin-bottom: 5px; }
.rq-empty strong { font-size: 14px; font-weight: 500; color: var(--pms-text-secondary); }
.rq-empty span { font-size: 12px; }
.rq-pagination { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 58px; color: var(--pms-text-secondary); font-size: 12px; }
.rq-pagination>.pms-form-control { width: 110px; }
.rq-error { display: flex; align-items: center; gap: 8px; background: var(--pms-danger-soft); padding: 8px 12px; color: var(--pms-danger); font-size: 12px; }
.rq-error span { color: var(--pms-text-secondary); }
.rq-condition-popper { max-width: calc(100vw - 28px); padding: 0 !important; border-radius: 8px !important; }
.rq-panel-head { display: flex; justify-content: space-between; align-items: center; padding: 16px 18px; border-bottom: 1px solid var(--pms-border-soft); }
.rq-panel-head strong { font-size: 14px; color: var(--pms-text); }
.rq-panel-head>span { font-size: 11px; color: var(--pms-text-muted); }
.rq-condition-labels, .rq-condition-row { display: grid; grid-template-columns: 155px 118px minmax(0, 1fr) 30px; gap: 10px; align-items: center; }
.rq-condition-labels { padding: 14px 18px 8px; color: var(--pms-text-muted); font-size: 11px; }
.rq-condition-body { padding: 0 18px; max-height: 320px; overflow-y: auto; }
.rq-condition-row { margin-bottom: 10px; }
.rq-condition-value { display: flex; min-width: 0; align-items: center; gap: 6px; }
.rq-condition-value>.pms-form-control { min-width: 0; flex: 1; width: 100%; }
.rq-condition-value>span { flex-shrink: 0; font-size: 11px; color: var(--pms-text-muted); }
.rq-condition-empty { padding: 22px; text-align: center; color: var(--pms-text-muted); font-size: 12px; }
.rq-no-value { padding-left: 8px; }
.rq-validation { font-size: 12px; padding: 0 18px; }
.rq-add { margin: 0 0 10px 12px; }
.rq-panel-footer { display: flex; justify-content: space-between; padding: 12px 18px; border-top: 1px solid var(--pms-border-soft); }
.rq-help { color: var(--pms-text-muted); font-size: 12px; line-height: 1.8; }
.rq-detail { display: grid; grid-template-columns: 130px 1fr; font-size: 13px; margin: 0; }
.rq-detail dt, .rq-detail dd { padding: 12px 0; border-bottom: 1px solid var(--pms-border-soft); margin: 0; min-height: 44px; overflow-wrap: anywhere; }
.rq-detail dt { color: var(--pms-text-secondary); }
@media(max-width:1100px) { .rq-sidebar { width: 170px; } .rq-brand { padding: 0 12px; } .rq-workspace { padding: 18px 16px; } .rq-quick-field { max-width: none; } .rq-query-actions { margin-left: 0; } }
@media(max-width:700px) { .rq-shell { min-height: 850px; } .rq-sidebar { width: 52px; } .rq-brand { padding: 10px; } .rq-brand strong, .rq-nav-label, .rq-sidebar-foot, .rq-nav-arrow { display: none; } .rq-sidebar nav { padding: 14px 5px; } .rq-sidebar nav button { font-size: 0; padding: 13px 10px; } .rq-sidebar nav button>.el-icon { font-size: 17px; } .rq-header { height: 70px; padding: 10px 12px; flex-wrap: wrap; } .rq-preview { gap: 8px; } .rq-preview>.pms-form-control { width: 120px; } .rq-workspace { padding: 14px 10px; } .rq-report { padding: 0 10px; } .rq-page-heading>span { display: none; } .rq-toolbar { flex-wrap: wrap; padding: 12px 0; } .rq-plans { width: 100%; } .rq-plans>.pms-form-control { flex: 1; min-width: 0; } .rq-tools { margin-left: auto; } .rq-quick { gap: 12px 8px; } .rq-quick-field { flex: 1 0 115px; } .rq-date { flex-basis: 100%; } .rq-query-actions { flex-wrap: wrap; gap: 6px; } .rq-status { flex-wrap: wrap; gap: 6px 12px; } .rq-pagination { flex-wrap: wrap; padding: 8px 0; } .rq-pagination>.pms-form-control { width: 100px; } .rq-condition-labels { display: none; } .rq-condition-body { padding-top: 12px; } .rq-condition-row { grid-template-columns: minmax(0,1fr) minmax(0,1fr) 28px; gap: 8px; padding-bottom: 10px; border-bottom: 1px solid var(--pms-border-soft); } .rq-condition-value { grid-column: 1 / 3; grid-row: 2; } .rq-condition-row>.el-button { grid-column: 3; grid-row: 1 / 3; } }
</style>

<style>
.rq-header, .rq-brand { height: 54px; }
.rq-workspace { padding: 16px; }
@media (max-width: 1250px) {
  .rq-quick:not(.rq-expanded) .rq-stock { display: none; }
  .rq-expand { display: inline-flex; }
  .rq-status>span+span { display: none; }
}
@media (max-width: 700px) {
  .rq-header { height: 70px; }
  .rq-workspace { padding: 10px; }
  .rq-toolbar { padding: 8px 0; gap: 8px; }
  .rq-status { margin-left: 0; }
  .rq-quick-field { flex-basis: 100%; }
  .rq-quick-field>span { width: 62px; }
  .rq-quick { gap: 8px; }
}
</style>
