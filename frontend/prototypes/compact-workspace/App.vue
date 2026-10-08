<script setup lang="ts">
import { computed, defineComponent, h, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Menu, Folder, Document, Setting, Search, Plus, Download } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type ColGroupDef, type GridApi, type GridReadyEvent } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { PmsTextControl, PmsSelectControl, PmsDateControl, PmsFormDrawer, PmsFormField } from '@/form-system'
import PmsReportQueryBar from '@/report-query/PmsReportQueryBar.vue'
import PmsReportPlans from '@/report-query/PmsReportPlans.vue'
import PmsReportQuerySurface from '@/report-query/PmsReportQuerySurface.vue'
import PmsReportConditions from '@/report-query/PmsReportConditions.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import GridHorizontalScrollbar from '@/components/GridHorizontalScrollbar.vue'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { cloneQuery, type ReportCondition, type ReportField } from '@/report-query/state'

ModuleRegistry.registerModules([AllCommunityModule])
const views = [{ value: 'archive', label: '项目档案' }, { value: 'progress', label: '项目进度' }, { value: 'purchase', label: '采购进度查询' }]
const active = ref('archive'), compact = ref(true), embedded = ref(true), menuOpen = ref(false)
const title = computed(() => views.find(v => v.value === active.value)!.label)
const page = ref(1), pageSize = ref(50), hasQueried = ref(false)
const keyword = ref(''), organization = ref<number[]>([]), project = ref(''), category = ref(''), status = ref('1'), dates = ref<string[]>([])
const conditions = ref<ReportCondition[]>([]), selectedStatus = ref('')
const plans = ref<InstanceType<typeof PmsReportPlans>>()
const organizations = [{ value: 1, label: '8吋Bench' }, { value: 2, label: 'Single' }]
const progressOptions = [{ value: '', label: '全部' }, { value: 'not_ordered', label: '未下单' }, { value: 'ordering', label: '部分下单' }, { value: 'receiving', label: '待入库' }, { value: 'complete', label: '已完成' }, { value: 'review', label: '数据待核对' }]
const fields: ReportField[] = [{ field: 'name', label: '项目/物料名称', type: 'text' }, { field: 'code', label: '项目编号', type: 'text' }]
const source = Array.from({ length: 160 }, (_, i) => ({
  id: i + 1, code: ['A-202638', 'SS-202603-02', 'L_B-202608', 'A-202639'][i % 4],
  name: ['晶圆清洗设备升级', '半导体湿法工艺设备', '槽式清洗系统改造', '自动化搬运项目'][i % 4],
  customer: ['苏州客户甲', '上海客户乙', '无锡客户丙'][i % 3], category: i % 2 ? 'Single' : 'Bench',
  organization: 1 + i % 2, product_line: organizations[i % 2]!.label, manager: ['王明', '李华', '张伟'][i % 3],
  series: ['标准型', '定制型'][i % 2], serial: `SN-2026-${String(i + 1).padStart(4, '0')}`,
  start: '2026-09-01', end: '2026-12-15', contract: '2026-08-28', ship: '2026-12-20',
  phase: ['设计', '采购', '装配', '调试'][i % 4], percent: `${[20, 45, 65, 80][i % 4]}%`,
  state: '启用', creator: '金奎宇', material: ['PFA管', 'PUS-Guide外侧齿01', '气体过滤器', '卡套接头', '运输费'][i % 5],
  bill: `CGSQ${30960 - Math.floor(i / 10)}`, line: 10 - i % 10, unit: i % 5 === 0 ? '米' : 'Pcs',
  requested: [20, 10, 60, 8, 4][i % 5], ordered: i % 5 === 0 ? 0 : 10, received: i % 5 === 3 ? 8 : 0,
  progress: progressOptions[1 + i % 5]!.value, progress_label: progressOptions[1 + i % 5]!.label,
  date: '2026-09-24', document_status: i % 5 === 4 ? '审核中' : '已审核', supplier: '供应商甲',
}))
const result = computed(() => active.value === 'purchase' && !hasQueried.value ? [] : source.filter(row =>
  (!keyword.value || `${row.code} ${row.name} ${row.material} ${row.customer}`.includes(keyword.value))
  && (!organization.value.length || organization.value.includes(row.organization))
  && (!category.value || category.value === row.category)
  && (!project.value || project.value === row.code)
  && (active.value !== 'purchase' || !selectedStatus.value || row.progress === selectedStatus.value)))
const rows = computed(() => result.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
let grid: GridApi | null = null
const scrollbar = ref<InstanceType<typeof GridHorizontalScrollbar>>()
async function refreshScroll() { await nextTick(); scrollbar.value?.refresh() }
function gridReady(e: GridReadyEvent) { grid = e.api; void refreshScroll() }
function switchView(value: string) { active.value = value; reset(); void refreshScroll() }
function density(value: boolean) { compact.value = value; menuOpen.value = !value; void refreshScroll() }
function reset() { keyword.value = ''; organization.value = []; project.value = ''; category.value = ''; dates.value = []; conditions.value = []; selectedStatus.value = ''; page.value = 1; hasQueried.value = false }
function query() { hasQueried.value = true; page.value = 1 }
function quick(value: string) { selectedStatus.value = value; query() }
const snapshot = () => ({ keyword: keyword.value, organization: organization.value, project: project.value, dates: dates.value, selectedStatus: selectedStatus.value, conditions: conditions.value })
function restore(value: any) { const state = cloneQuery(value); keyword.value = state.keyword; organization.value = state.organization; project.value = state.project; dates.value = state.dates; selectedStatus.value = state.selectedStatus; conditions.value = state.conditions; hasQueried.value = false; page.value = 1 }

const drawer = ref(false), edit = ref(false), formError = ref(false)
const drawerTop = ref(102), selectedPurchase = ref<typeof source[number] | null>(null)
function positionDrawer() { drawerTop.value = Math.round(document.querySelector('.workspace-header')!.getBoundingClientRect().bottom) + 6 }
watch([compact, embedded], async () => { await nextTick(); positionDrawer(); void refreshScroll() })
const form = reactive({ code: '', name: '', customer: '', product_line: null as number | null, category: '', manager: '金奎宇', contract: '', ship: '', province: '', city: '', address: '', contact: '', phone: '', warranty: '' })
function openForm(row?: typeof source[number]) {
  positionDrawer(); selectedPurchase.value = active.value === 'purchase' ? row || null : null
  edit.value = !!row; formError.value = false
  Object.assign(form, { code: row?.code || '', name: row?.name || '', customer: row?.customer || '', product_line: row?.organization || null, category: row?.category || '', manager: row?.manager || '金奎宇', contract: row?.contract || '', ship: row?.ship || '', province: '', city: '', address: '', contact: '', phone: '', warranty: '' })
  drawer.value = true
}
function saveForm() {
  formError.value = !form.code.trim() || !form.name.trim() || !form.contract || !form.ship
  if (formError.value) return
  drawer.value = false; ElMessage.success('样稿保存成功，未写入业务数据')
}
const Actions = defineComponent({ props: ['params'], setup(props) { return () => h('button', { class: 'workspace-action', onClick: () => openForm(props.params.data) }, active.value === 'purchase' ? '明细' : '编辑') } })
const State = defineComponent({ props: ['params'], setup(props) { return () => h('span', { class: 'pms-status success' }, '启用') } })
const Progress = defineComponent({ props: ['params'], setup(props) { return () => h('span', { class: ['pms-status', props.params.data.progress === 'complete' ? 'success' : props.params.data.progress === 'review' ? 'danger' : props.params.data.progress === 'ordering' ? 'warning' : 'info'] }, props.params.data.progress_label) } })
const columns = computed<(ColDef | ColGroupDef)[]>(() => {
  const col = (field: string, headerName: string, width = 128): ColDef => ({ field, headerName, width: compact.value ? width : Math.round(width * 1.12), minWidth: 80 })
  const actions: ColDef = { headerName: '操作', colId: 'actions', pinned: 'right', width: 112, minWidth: 112, maxWidth: 112, sortable: false, resizable: false, cellRenderer: Actions }
  if (active.value === 'purchase') return [
    { headerName: '物料信息', children: [{ ...col('code', '项目编号', 136), pinned: 'left' }, { ...col('material', '物料名称', 170), pinned: 'left' }] },
    { headerName: '采购申请', children: [col('product_line', '产品线', 110), col('unit', '申请单位', 88), col('bill', '申请单编号', 132), col('line', '申请单行号', 100), col('date', '申请日期', 120), col('document_status', '数据状态', 100), { ...col('requested', '申请数量', 104), cellClass: 'workspace-number' }] },
    { headerName: '采购订单', children: [{ ...col('ordered', '累计下单数量', 120), cellClass: 'workspace-number' }, col('supplier', '供应商', 140)] },
    { headerName: '采购入库', children: [{ ...col('received', '累计入库数量', 120), cellClass: 'workspace-number' }] },
    { headerName: '进度', children: [{ ...col('progress_label', '采购进度', 124), pinned: 'right', cellRenderer: Progress }] }, actions,
  ]
  const leading: ColDef[] = [{ colId: 'select', width: 36, minWidth: 36, maxWidth: 36, pinned: 'left', checkboxSelection: true, headerCheckboxSelection: true, sortable: false, resizable: false }, { ...col('code', '项目编号', 140), pinned: 'left' }, col('name', '项目名称', 184), col('customer', '客户', 150), col('product_line', '产品线', 112)]
  return [...leading, ...(active.value === 'archive' ? [col('category', '产品类别', 104), { ...col('state', '启用状态', 92), cellRenderer: State }, col('manager', '负责人', 100), col('series', '设备系列', 106), col('serial', '序列号', 130), col('contract', '合同签订日期', 126), col('ship', '合同出货日期', 126), col('creator', '创建人', 100)] : [col('manager', '负责人', 100), col('phase', '项目阶段', 100), col('percent', '完成进度', 100), col('start', '计划开始', 120), col('end', '计划结束', 120), col('creator', '编辑人', 100)]), actions]
})
const drawerStyle = computed(() => ({ top: `${drawerTop.value}px`, right: '6px', height: `calc(100% - ${drawerTop.value + 6}px)`, width: compact.value ? '460px' : '492px', maxWidth: 'calc(100vw - 12px)', '--pms-form-control-height-compact': compact.value ? '28px' : '32px', '--pms-form-control-height-regular': compact.value ? '32px' : '36px' }))
</script>

<template>
  <div class="compact-preview" :class="{ 'is-compact': compact, 'is-embedded': embedded, 'has-menu': menuOpen }">
    <div class="preview-strip"><strong>OA 嵌入布局样稿</strong><nav aria-label="样稿页面"><button v-for="view in views" :key="view.value" :aria-pressed="active === view.value" @click="switchView(view.value)">{{ view.label }}</button></nav><div class="preview-comparison" role="group" aria-label="布局对比"><button :aria-pressed="!compact" @click="density(false)">原尺寸参考</button><button :aria-pressed="compact" @click="density(true)">紧凑方案</button></div><label class="embed-toggle"><input v-model="embedded" type="checkbox">模拟OA区域</label></div>
    <aside v-if="embedded" class="oa-reserved"><strong>OA 导航</strong><span>公司系统</span><span>报表</span><span>人事</span><span>研发项目</span><span>公共功能</span><span class="oa-active">PMS</span><small>此区域仅模拟占位<br>不修改OA布局</small></aside>
    <div class="embedded-app">
      <header class="workspace-header"><button class="menu-trigger" :aria-expanded="menuOpen" aria-label="展开或隐藏PMS菜单" @click="menuOpen = !menuOpen; refreshScroll()"><el-icon><Menu /></el-icon></button><span class="workspace-brand">P</span><strong>{{ title }}</strong><span class="workspace-user">金奎宇</span><el-button size="small" type="danger" plain disabled>退出</el-button></header>
      <aside v-if="menuOpen" class="workspace-menu"><strong>PMS 管理系统</strong><div>项目管理</div><button v-for="view in views.slice(0, 2)" :key="view.value" :aria-current="active === view.value ? 'page' : undefined" @click="switchView(view.value)"><el-icon><Folder /></el-icon>{{ view.label }}</button><div>报表中心</div><button :aria-current="active === 'purchase' ? 'page' : undefined" @click="switchView('purchase')"><el-icon><Document /></el-icon>采购进度查询</button><span>即时库存查询</span><span>物料收发明细</span></aside>
      <el-config-provider :size="compact ? 'small' : 'default'">
      <main class="workspace-main pms-report-query-surface">
        <div class="workspace-panel">
          <template v-if="active === 'purchase'">
            <PmsReportQuerySurface><div class="pms-report-query-toolbar"><PmsReportPlans ref="plans" storage-key="pms:compact-prototype:20261008" :snapshot="snapshot" @restore="restore" /><div class="pms-report-query-tools"><span class="pms-report-query-status">{{ hasQueried ? '已查询' : '尚未查询' }}</span><el-button :icon="Download" disabled>导出当前筛选</el-button><el-button disabled>导出任务</el-button><el-button :icon="Setting" disabled>列设置</el-button></div></div>
              <PmsReportQueryBar v-model:conditions="conditions" :fields="fields" @query="query" @reset="reset"><div class="query-material"><PmsTextControl v-model="keyword" size="compact" :prefix-icon="Search" clearable placeholder="申请单 / 物料名称" aria-label="搜索采购明细" /></div><PmsSelectControl v-model="organization" size="compact" :options="organizations" multiple collapse-tags clearable placeholder="全部产品线" aria-label="产品线筛选" /><PmsSelectControl v-model="project" size="compact" clearable :options="['A-202638', 'SS-202603-02'].map(value => ({ value, label: value }))" placeholder="全部项目" aria-label="项目筛选" /><div class="query-dates"><PmsDateControl v-model="dates" size="compact" type="daterange" value-format="YYYY-MM-DD" start-placeholder="申请开始日期" end-placeholder="申请结束日期" aria-label="申请日期范围" /></div></PmsReportQueryBar>
            </PmsReportQuerySurface>
            <div class="workspace-shortcuts" role="group" aria-label="采购进度快捷筛选"><button v-for="option in progressOptions" :key="option.value" :aria-pressed="selectedStatus === option.value" @click="quick(option.value)">{{ option.label }}</button><span>申请日期：2026-01-01 起</span></div>
          </template>
          <template v-else>
            <div class="workspace-toolbar"><div><el-button v-if="active === 'archive'" type="primary" size="small" :icon="Plus" @click="openForm()">新增档案</el-button><el-button v-else size="small" disabled>批量维护</el-button><el-button size="small" disabled>批量启用</el-button><el-button size="small" disabled>批量禁用</el-button></div><el-button size="small" :icon="Setting" disabled>列设置</el-button></div>
            <div class="workspace-filters"><div class="workspace-search"><PmsTextControl v-model="keyword" size="compact" :prefix-icon="Search" clearable placeholder="搜索编号、名称、客户" aria-label="搜索项目" @update:model-value="page = 1" /></div><PmsSelectControl v-model="status" size="compact" :options="[{ value: '1', label: '启用' }, { value: '', label: '全部状态' }]" aria-label="启用状态" /><PmsSelectControl v-model="organization" size="compact" :options="organizations" multiple collapse-tags clearable placeholder="全部产品线" aria-label="产品线筛选" @update:model-value="page = 1" /><PmsSelectControl v-model="category" size="compact" :options="[{ value: 'Bench', label: 'Bench' }, { value: 'Single', label: 'Single' }]" clearable placeholder="全部产品类别" aria-label="产品类别筛选" @update:model-value="page = 1" /><PmsReportConditions v-model="conditions" :fields="fields" trigger-label="添加筛选" /></div>
          </template>
          <div class="workspace-grid-shell"><AgGridVue :key="`${active}:${compact}`" class="ag-theme-alpine pms-ag-grid" theme="legacy" :row-data="rows" :column-defs="columns" :default-col-def="{ resizable: true, sortable: true, tooltipValueGetter: p => p.value, cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }" :locale-text="chineseLocaleText" :row-height="compact ? 32 : 38" :header-height="compact ? 30 : 36" :group-header-height="compact ? 26 : 36" :suppress-no-rows-overlay="true" :tooltip-show-delay="200" @grid-ready="gridReady" @grid-size-changed="refreshScroll" /><div v-if="active === 'purchase' && !hasQueried" class="workspace-empty">设置条件后，点击查询</div><GridHorizontalScrollbar ref="scrollbar" label="样稿列表横向滚动条" /></div>
          <CustomPagination v-model="page" v-model:page-size="pageSize" :total="result.length" @update:page-size="page = 1" />
        </div>
      </main>
      </el-config-provider>
    </div>
    <PmsFormDrawer v-model="drawer" :size="compact ? '460px' : '492px'" :title="active === 'purchase' ? '采购申请明细' : edit ? '编辑项目档案' : '新增项目档案'" class="compact-preview-drawer" :class="{ 'is-compact-drawer': compact }" :style="drawerStyle">
      <div class="preview-form-note">交互样稿，不保存业务数据</div>
      <template v-if="selectedPurchase">
        <h3 class="pms-form-drawer__section">采购申请</h3>
        <PmsFormField v-for="[key, label] in [['code', '项目编号'], ['product_line', '产品线'], ['material', '物料名称'], ['bill', '申请单编号'], ['date', '申请日期'], ['requested', '申请数量'], ['progress_label', '采购进度']]" :key="key" :field-id="`purchase-${key}`" :label="label"><PmsTextControl :id="`purchase-${key}`" :model-value="String(selectedPurchase[key])" readonly /></PmsFormField>
      </template>
      <template v-else>
      <h3 class="pms-form-drawer__section">基础信息</h3>
      <PmsFormField field-id="compact-code" label="项目编号" required :error="formError && !form.code.trim() ? '请输入项目编号' : ''"><PmsTextControl id="compact-code" v-model="form.code" aria-label="项目编号" :error="formError && !form.code.trim()" /></PmsFormField>
      <PmsFormField field-id="compact-name" label="项目名称" required :error="formError && !form.name.trim() ? '请输入项目名称' : ''"><PmsTextControl id="compact-name" v-model="form.name" aria-label="项目名称" :error="formError && !form.name.trim()" /></PmsFormField>
      <PmsFormField field-id="compact-customer" label="客户"><PmsTextControl id="compact-customer" v-model="form.customer" placeholder="输入客户" aria-label="客户" /></PmsFormField>
      <PmsFormField field-id="compact-product" label="产品线"><PmsSelectControl id="compact-product" v-model="form.product_line" :options="organizations" aria-label="产品线" /></PmsFormField>
      <PmsFormField field-id="compact-category" label="产品类别"><PmsSelectControl id="compact-category" v-model="form.category" :options="[{ value: 'Bench', label: 'Bench' }, { value: 'Single', label: 'Single' }]" aria-label="产品类别" /></PmsFormField>
      <PmsFormField field-id="compact-manager" label="负责人"><PmsTextControl id="compact-manager" v-model="form.manager" aria-label="负责人" /></PmsFormField>
      <h3 class="pms-form-drawer__section">合同与交付</h3>
      <PmsFormField field-id="compact-contract" label="合同签订日期" required :error="formError && !form.contract ? '请选择合同签订日期' : ''"><PmsDateControl id="compact-contract" v-model="form.contract" value-format="YYYY-MM-DD" aria-label="合同签订日期" /></PmsFormField>
      <PmsFormField field-id="compact-ship" label="合同出货日期" required :error="formError && !form.ship ? '请选择合同出货日期' : ''"><PmsDateControl id="compact-ship" v-model="form.ship" value-format="YYYY-MM-DD" aria-label="合同出货日期" /></PmsFormField>
      <PmsFormField field-id="compact-warranty" label="质保截止日期"><PmsDateControl id="compact-warranty" v-model="form.warranty" value-format="YYYY-MM-DD" aria-label="质保截止日期" /></PmsFormField>
      <h3 class="pms-form-drawer__section">项目联系信息</h3>
      <PmsFormField field-id="compact-province" label="项目地址"><div class="preview-address"><PmsSelectControl id="compact-province" v-model="form.province" :options="[{ value: '江苏省', label: '江苏省' }, { value: '浙江省', label: '浙江省' }]" placeholder="省" aria-label="省" @update:model-value="form.city = ''; form.address = ''" /><PmsSelectControl v-if="form.province" v-model="form.city" :options="(form.province === '江苏省' ? ['苏州市', '南京市'] : ['杭州市', '宁波市']).map(value => ({ value, label: value }))" placeholder="市" aria-label="市" @update:model-value="form.address = ''" /><PmsTextControl v-if="form.city" v-model="form.address" placeholder="详细地址" aria-label="详细地址" /></div></PmsFormField>
      <PmsFormField field-id="compact-contact" label="项目联系人"><PmsTextControl id="compact-contact" v-model="form.contact" aria-label="项目联系人" /></PmsFormField>
      <PmsFormField field-id="compact-phone" label="联系人手机"><PmsTextControl id="compact-phone" v-model="form.phone" aria-label="联系人手机" /></PmsFormField>
      </template>
      <template #footer><el-button @click="drawer = false">{{ selectedPurchase ? '关闭' : '取消' }}</el-button><el-button v-if="!selectedPurchase" type="primary" @click="saveForm">{{ edit ? '保存' : '创建' }}</el-button></template>
    </PmsFormDrawer>
  </div>
</template>

<style>
html, body, #app { margin: 0; height: 100%; }
.compact-preview { height: 100%; display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: 52px minmax(0, 1fr); font: 13px var(--pms-font); color: var(--pms-text); background: var(--pms-bg); }
.compact-preview.is-embedded { grid-template-columns: 184px minmax(0, 1fr); }
.preview-strip { grid-column: 1 / -1; display: flex; align-items: center; gap: 16px; padding: 0 14px; background: var(--pms-surface); border-bottom: 1px solid var(--pms-border); min-width: 0; }
.preview-strip strong { font-size: 13px; white-space: nowrap; }.preview-strip nav, .preview-comparison { display: flex; align-items: center; gap: 4px; }
.preview-strip button { height: 28px; padding: 0 10px; border: 1px solid transparent; background: transparent; color: var(--pms-text-secondary); border-radius: 4px; font: inherit; font-size: 12px; cursor: pointer; white-space: nowrap; }
.preview-strip button[aria-pressed="true"] { color: var(--pms-primary); background: var(--pms-primary-soft); }.preview-comparison { margin-left: auto; border: 1px solid var(--pms-border); padding: 2px; border-radius: 6px; }.embed-toggle { display: flex; gap: 4px; align-items: center; font-size: 12px; white-space: nowrap; }
.oa-reserved { display: flex; flex-direction: column; gap: 4px; padding: 20px 12px; background: var(--pms-surface-muted); border-right: 1px solid var(--pms-border); color: var(--pms-text-secondary); }.oa-reserved strong { padding: 8px; }.oa-reserved span { padding: 14px 12px; }.oa-reserved .oa-active { background: var(--pms-primary-soft); color: var(--pms-primary); border-radius: 4px; }.oa-reserved small { margin-top: auto; padding: 8px; color: var(--pms-text-muted); line-height: 1.8; font-size: 11px; }
.embedded-app { min-width: 0; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: 56px minmax(0, 1fr); position: relative; }
.has-menu .embedded-app { grid-template-columns: 184px minmax(0, 1fr); }
.workspace-header { grid-column: 1 / -1; display: flex; align-items: center; gap: 10px; padding: 0 18px; background: var(--pms-surface); border-bottom: 1px solid var(--pms-border-soft); }.workspace-header strong { font-size: 15px; font-weight: 650; }.menu-trigger { display: grid; place-items: center; width: 28px; height: 28px; border: 0; background: transparent; color: var(--pms-text-secondary); cursor: pointer; font-size: 18px; }.workspace-brand { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 5px; color: var(--pms-primary); background: var(--pms-primary-soft); font-weight: 700; }.workspace-user { margin-left: auto; color: var(--pms-text-secondary); font-size: 12px; }
.workspace-menu { background: var(--pms-surface); border-right: 1px solid var(--pms-border-soft); padding: 16px 8px; }.workspace-menu > strong { display: block; margin: 0 8px 20px; }.workspace-menu > div { color: var(--pms-text-muted); padding: 12px 8px 8px; font-size: 12px; }.workspace-menu button, .workspace-menu > span { display: flex; gap: 8px; align-items: center; height: 36px; width: 100%; padding: 0 12px; border: 0; border-radius: 4px; background: transparent; font: inherit; color: var(--pms-text-secondary); text-align: left; }.workspace-menu button { cursor: pointer; }.workspace-menu button[aria-current="page"] { color: var(--pms-primary); background: var(--pms-primary-soft); }
.workspace-main { min-width: 0; min-height: 0; padding: 16px; }.workspace-panel { height: 100%; min-height: 0; display: flex; flex-direction: column; padding: 16px; border: 1px solid var(--pms-border-soft); border-radius: 8px; background: var(--pms-surface); overflow: hidden; }
.workspace-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-bottom: 12px; border-bottom: 1px solid var(--pms-border-soft); }.workspace-toolbar > div { display: flex; gap: 8px; }
.workspace-filters { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 10px 0 12px; }.workspace-filters > .pms-form-control { width: 140px; }.workspace-filters > .pms-form-control:nth-child(2) { width: 112px; }.workspace-search { width: 220px; }
.workspace-shortcuts { display: flex; gap: 20px; align-items: center; min-height: 38px; border-bottom: 1px solid var(--pms-border-soft); margin-bottom: 8px; }.workspace-shortcuts button { height: 36px; border: 0; border-bottom: 2px solid transparent; padding: 0; background: transparent; font: inherit; font-size: 12px; color: var(--pms-text-secondary); cursor: pointer; white-space: nowrap; }.workspace-shortcuts button[aria-pressed="true"] { color: var(--pms-primary); border-bottom-color: var(--pms-primary); }.workspace-shortcuts > span { margin-left: auto; font-size: 11px; color: var(--pms-text-muted); white-space: nowrap; }
.workspace-grid-shell { position: relative; flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; }.workspace-grid-shell > .pms-ag-grid { flex: 1; min-height: 0; width: 100%; }.workspace-grid-shell .ag-header-cell-label, .workspace-grid-shell .ag-header-group-cell-label { justify-content: center; }.workspace-grid-shell .workspace-number { justify-content: flex-end; }.workspace-action { border: 0; padding: 0 5px; width: 40px; height: 24px; background: transparent; color: var(--pms-primary); font: inherit; font-size: 12px; cursor: pointer; }.workspace-grid-shell .ag-cell { font-size: 13px; }.workspace-empty { position: absolute; inset: 80px 0 24px; display: grid; place-items: center; pointer-events: none; color: var(--pms-text-muted); }
.workspace-grid-shell .ag-body-horizontal-scroll { height: 0 !important; min-height: 0 !important; max-height: 0 !important; opacity: 0; }
.compact-preview button:focus-visible { outline: 2px solid var(--pms-primary); outline-offset: -2px; }
/* Density changes are isolated to this prototype until user acceptance. */
.is-compact { --pms-form-control-height-compact: 24px; --pms-form-control-height-regular: 32px; --pms-form-control-padding-x: 6px; }
.is-compact :is(.workspace-toolbar, .workspace-filters, .pms-report-query-toolbar, .pms-report-query-fields) { --pms-font-size-base: 12px; --pms-form-control-line-height: 18px; }
.is-compact .embedded-app { grid-template-rows: 44px minmax(0, 1fr); }.is-compact .workspace-header { padding: 0 10px; }.is-compact .workspace-main { padding: 6px; }.is-compact .workspace-panel { padding: 8px; border-radius: 6px; }
.is-compact .workspace-toolbar { padding-bottom: 4px; }.is-compact .workspace-toolbar > div { gap: 6px; }.is-compact .workspace-toolbar .el-button, .is-compact .workspace-filters .el-button, .is-compact .workspace-header .el-button { height: 24px; min-height: 24px; padding: 0 8px; border-radius: 4px; font-size: 12px; margin: 0; }
.is-compact .workspace-filters { padding: 4px 0; gap: 6px; }.is-compact .workspace-search { width: 190px; }.is-compact .workspace-filters > .pms-form-control { width: 112px; }.is-compact .workspace-filters > .pms-form-control:nth-child(2) { width: 88px; }
.is-compact .pms-report-query-toolbar { padding-bottom: 4px; gap: 6px; }.is-compact .pms-report-query-fields { padding: 4px 0; gap: 6px; }.is-compact .pms-report-query-fields > .query-material { width: 180px; }.is-compact .pms-report-query-fields > .query-dates { width: 220px; }.is-compact .pms-report-query-fields > .pms-form-control { width: 112px; }.is-compact .pms-report-query-surface :is(.pms-report-query-toolbar,.pms-report-query-fields) .el-button { height: 24px; min-height: 24px; padding: 0 8px; border-radius: 4px; font-size: 12px; }.is-compact .pms-report-plans > .pms-form-control { width: 144px; }.is-compact .pms-report-plans, .is-compact .pms-report-query-tools { gap: 6px; }
.is-compact .workspace-shortcuts { min-height: 26px; margin-bottom: 2px; gap: 16px; }.is-compact .workspace-shortcuts button { height: 24px; }.is-compact .workspace-shortcuts span { font-size: 11px; }
.is-compact .custom-pagination { margin-top: 4px; padding-top: 4px; min-height: 32px; }.is-compact .custom-pagination .page-btn { min-width: 26px; height: 26px; padding: 0 6px; font-size: 12px; }.is-compact .custom-pagination .page-size-select { height: 26px; font-size: 12px; }.is-compact .custom-pagination .pagination-total { font-size: 12px; }
.is-compact .grid-horizontal-scrollbar { height: 14px; margin-top: 2px; }
.compact-preview-drawer .preview-form-note { font: 11px var(--pms-font); color: var(--pms-text-muted); padding-top: 8px; }.compact-preview-drawer .preview-address { display: flex; flex-wrap: wrap; gap: 6px; }.preview-address > .pms-form-control { flex: 1 1 110px; }.preview-address > .pms-form-control:last-child:nth-child(3) { flex-basis: 100%; }
.compact-preview-drawer.is-compact-drawer .el-drawer__header { padding: 12px 16px; }.compact-preview-drawer.is-compact-drawer .el-drawer__footer { padding: 8px 16px; }.compact-preview-drawer.is-compact-drawer .pms-form-drawer__content { padding: 0 16px 12px; }.compact-preview-drawer.is-compact-drawer .pms-form-field { padding: 5px 0; gap: 8px; }.compact-preview-drawer.is-compact-drawer .pms-form-field__label { padding-top: 5px; }.compact-preview-drawer.is-compact-drawer .pms-form-drawer__section { padding: 12px 0 8px; }.compact-preview-drawer.is-compact-drawer .el-button { height: 28px; min-height: 28px; font-size: 12px; }
@media (max-width: 900px) { .compact-preview.is-embedded { grid-template-columns: 100px minmax(0, 1fr); }.preview-strip { gap: 6px; padding: 0 8px; }.preview-strip > strong { display: none; }.oa-reserved { padding: 12px 6px; }.workspace-shortcuts { flex-wrap: wrap; gap: 12px; }.workspace-shortcuts > span { display: none; } }
@media (max-width: 600px) { .compact-preview { grid-template-rows: auto minmax(0, 1fr); }.compact-preview.is-embedded { grid-template-columns: minmax(0, 1fr); }.oa-reserved { display: none; }.preview-strip { flex-wrap: wrap; padding: 6px; }.preview-comparison { margin-left: 0; }.embed-toggle { margin-left: auto; }.has-menu .embedded-app { grid-template-columns: 140px minmax(0, 1fr); }.workspace-menu { padding: 8px 4px; }.workspace-user { display: none; }.is-compact .workspace-header > .el-button, .workspace-header > .el-button { margin-left: auto; }.workspace-filters > .pms-form-control, .workspace-search { flex: 1 1 120px; width: auto; }.workspace-toolbar > div { flex-wrap: wrap; }.workspace-grid-shell { overflow: auto; }.workspace-grid-shell > .pms-ag-grid { min-width: 850px; }.custom-pagination { flex-wrap: wrap; gap: 6px; }.custom-pagination .pagination-center { order: 3; width: 100%; justify-content: center; } }
</style>
