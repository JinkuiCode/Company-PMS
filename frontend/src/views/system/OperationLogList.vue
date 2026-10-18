<template>
  <section class="operation-audit-layout" aria-label="操作审计">
  <PmsDataList class="pms-system-page operation-audit-list" :show-scrollbar="false" scrollbar-label="操作日志表格横向滚动条">
    <template #toolbar-left>
      <el-button class="pms-button-auxiliary" size="small" @click="fetchLogs">
        刷新
      </el-button>
    </template>
    <template #toolbar-right>
      <PmsPageGuide page="audit" />
    </template>

    <template #filters>
      <PmsQueryWorkspace entry-mode="document" v-model="queryDraft" list-key="system-operation-log" :fields="queryFields" :defaults="queryDefaults" :ready="querySupported" :loading="loading" :snapshot="() => ({pageSize})" @query="runQuery" @clear-columns="clearQueryColumns" />
      <p v-if="!querySupported" class="operation-log-hint" role="status">操作日志接口尚未声明查询 v2 支持，统一查询暂不可用；未执行当前页过滤。</p>
      <p v-if="queryError" role="alert">{{queryError}}</p>
    </template>

    <template #grid>
      <el-table
        v-loading="loading"
        class="pms-dense-table operation-log-table"
        :data="visibleLogs"
        row-key="id"
        :current-row-key="detailVisible ? selectedLog?.id : null"
        :highlight-current-row="detailVisible"
        @row-click="selectRow"
        border
        stripe
        height="100%"
        empty-text="暂无操作日志"
      >
        <el-table-column prop="created_at" label="时间" width="168" fixed :class-name="queryColumnClass('created_at')" :label-class-name="queryColumnClass('created_at')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'created_at',displayName:'时间'}" /><span v-else>时间</span></template>
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="104" :class-name="queryColumnClass('module')" :label-class-name="queryColumnClass('module')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'module',displayName:'模块'}" /><span v-else>模块</span></template></el-table-column>
        <el-table-column prop="action" label="动作" width="118" :class-name="queryColumnClass('action')" :label-class-name="queryColumnClass('action')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'action',displayName:'动作'}" /><span v-else>动作</span></template>
          <template #default="{ row }">{{ actionLabel(row.action) }}</template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作者" width="116" :class-name="queryColumnClass('operator_name')" :label-class-name="queryColumnClass('operator_name')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'operator_name',displayName:'操作者'}" /><span v-else>操作者</span></template>
          <template #default="{ row }">{{ row.operator_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="entity_name" label="对象" min-width="180" show-overflow-tooltip :class-name="queryColumnClass('entity_name')" :label-class-name="queryColumnClass('entity_name')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'entity_name',displayName:'对象'}" /><span v-else>对象</span></template>
          <template #default="{ row }">{{ row.entity_name || row.entity_id || '-' }}</template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip :class-name="queryColumnClass('summary')" :label-class-name="queryColumnClass('summary')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'summary',displayName:'摘要'}" /><span v-else>摘要</span></template></el-table-column>
        <el-table-column prop="status" label="状态" width="88" :class-name="queryColumnClass('status')" :label-class-name="queryColumnClass('status')"><template #header><PmsQueryColumnHeader v-if="querySupported" :params="{contextQuery:() => columnContext,field:'status',displayName:'状态'}" /><span v-else>状态</span></template>
          <template #default="{ row }">
            <span class="pms-status" :class="row.status === 'success' ? 'success' : 'danger'">
              <span class="pms-status-dot"></span>
              {{ row.status === 'success' ? '成功' : '失败' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="pmsActionColumn(1).width" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <template #pagination>
      <CustomPagination
        v-model="page"
        v-model:page-size="pageSize"
        :total="total"
      />
    </template>
  </PmsDataList>

  <aside v-if="detailVisible && selectedLog" ref="detailPanel" class="operation-audit-detail" role="dialog" aria-label="操作详情" tabindex="-1" @keydown.esc.stop.prevent="closeDetail">
    <header class="audit-detail-header"><h2>操作详情</h2><button class="audit-close" type="button" aria-label="关闭操作详情" @click="closeDetail"><Close /></button></header>
    <div class="audit-detail-body">
      <dl class="audit-meta"><dt>操作者</dt><dd>{{ selectedLog.operator_name || '-' }}</dd><dt>时间</dt><dd>{{ formatDateTime(selectedLog.created_at) }}</dd><dt>单据</dt><dd>{{ selectedLog.entity_name || selectedLog.entity_id || '-' }}</dd><dt>模块</dt><dd>{{ selectedLog.module }}</dd><dt>动作</dt><dd>{{ actionLabel(selectedLog.action) }}</dd><dt>结果</dt><dd>{{ selectedLog.status === 'success' ? '成功' : '失败' }}</dd></dl>
      <section class="audit-section"><h3>摘要</h3><p>{{ selectedLog.summary }}</p><p v-if="selectedLog.error_msg" class="detail-error">{{ selectedLog.error_msg }}</p></section>
      <section class="audit-section"><h3>字段变化</h3><table v-if="diffRows.length" class="audit-diff"><thead><tr><th scope="col">字段</th><th scope="col">变更前</th><th scope="col">变更后</th></tr></thead><tbody><tr v-for="row in diffRows" :key="row.field_key"><th scope="row">{{ row.field_label }}</th><td>{{ row.before_display }}</td><td>{{ row.after_display }}</td></tr></tbody></table><p v-else class="operation-log-hint">本次操作没有字段变化。</p></section>
      <details :key="selectedLog.id" class="audit-technical"><summary>技术信息</summary><p v-if="diffRows.some(row => row.before_name_source === 'current' || row.after_name_source === 'current')">旧记录未保存名称的负责人或产品线，显示当前关联名称；已保存的历史名称保持原样。</p><dl class="audit-meta"><dt>IP</dt><dd>{{ selectedLog.ip_address || '-' }}</dd><dt>路径</dt><dd>{{ selectedLog.request_method }} {{ selectedLog.request_path || '-' }}</dd><dt>记录ID</dt><dd>{{ selectedLog.id }}</dd></dl><h3>原始快照</h3><pre>{{ formatPrettyJson(selectedLog.before_data) }}</pre><pre>{{ formatPrettyJson(selectedLog.after_data) }}</pre></details>
    </div>
  </aside>
  </section>
</template>

<script setup lang="ts">
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import PmsQueryColumnHeader from '@/query-system/PmsQueryColumnHeader.vue'
import { useSystemQuery, serverQueryParams, requireServerQueryVersion } from '@/query-system/system-adapter'
import { toQueryFields } from '@/query-system/list-adapter'
import type { QueryCondition } from '@/query-system/core'
import type { ColumnQueryContext } from '@/query-system/column-filters'
import { usePageColumnFilter } from '@/query-system/page-column-filter'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { usePageLoad } from '@/composables/usePageLoad'
import { Close } from '@element-plus/icons-vue'
import { createDetailSwitch } from '@/utils/detailSwitch'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import { pmsActionColumn } from '@/config/listUi'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsDataList from '@/components/PmsDataList.vue'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from '@/config/listUi'
import { PmsDateControl, PmsSelectControl, PmsTextControl, type PmsOption } from '@/form-system'
import {
  type ListFilterField,
  type ListFilterOption,
} from '@/composables/useListFilters'
import request from '@/utils/request'

type OperationLog = {
  id: number
  module: string
  action: string
  entity_type: string
  entity_id?: string | null
  entity_name?: string | null
  operator_id?: number | null
  operator_name?: string | null
  ip_address?: string | null
  user_agent?: string | null
  request_path?: string | null
  request_method?: string | null
  status: 'success' | 'failed' | string
  summary: string
  error_msg?: string | null
  before_data?: string | null
  after_data?: string | null
  diff_data?: string | null
  diff_items?: OperationLogDiffItem[]
  created_at: string
}

type OperationLogDiffItem = {
  field_key: string
  field_label: string
  field_group?: string | null
  before?: unknown
  after?: unknown
  before_display: string
  after_display: string
  before_name_source?: string
  after_name_source?: string
}

type OperationLogListResponse = {
  total: number
  modules: ListFilterOption[]
  actions: ListFilterOption[]
  items: OperationLog[]
}

const moduleOptions = ref<ListFilterOption[]>([])

const actionOptions = ref<ListFilterOption[]>([])

const statusOptions: PmsOption[] = [
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

const customFilterFields: ListFilterField[] = [
  { field: 'module', label: '模块', type: 'select', options: () => moduleOptions.value },
  { field: 'action', label: '动作', type: 'select', options: () => actionOptions.value },
  { field: 'entity_type', label: '对象类型', type: 'text' },
  { field: 'entity_name', label: '对象名称', type: 'text' },
  { field: 'operator_name', label: '操作者', type: 'text' },
  { field: 'ip_address', label: 'IP', type: 'text' },
  { field: 'status', label: '状态', type: 'select', options: () => [{ label: '成功', value: 'success' }, { label: '失败', value: 'failed' }] },
  { field: 'created_at', label: '时间', type: 'date' },
]

const { fields: queryFields, defaults: queryDefaults, draft: queryDraft, applied: queryApplied, submit: submitQuery, clearColumns, columnContext: clientContext, columnFilters, columnClass: queryColumnClass } = useSystemQuery(() => [
  ...toQueryFields(customFilterFields),
  {field:'summary',label:'摘要',type:'text'},
  {field:'request_path',label:'路径',type:'text'},
], ['created_at','module','action','operator_name'], {requireQuery:true,ready:()=>querySupported.value && ['ready','empty'].includes(logListState.phase.value) && !queryError.value})
const querySupported = ref(false), queryError = ref('')
function clearQueryColumns() { clearColumns() }
function runQuery(conditions: QueryCondition[], preferences: object) {
  if (!querySupported.value) return
  submitQuery(conditions)
  const size = (preferences as {pageSize?:number}).pageSize
  if (size && PAGE_SIZE_OPTIONS.includes(size)) pageSize.value = size
  page.value = 1
}

const logListState = usePageLoad()
const loading = logListState.loading
const logs = ref<OperationLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const pageColumns = usePageColumnFilter(logs, () => queryFields.value, columnFilters, () => [page.value,pageSize.value], undefined, () => clientContext.ready?.() !== false)
const columnContext: ColumnQueryContext = pageColumns.context
const visibleLogs = pageColumns.visibleRows
const detailVisible = ref(false)
const selectedLog = ref<OperationLog | null>(null)

let logQueryTimer: ReturnType<typeof setTimeout> | undefined

const diffRows = computed(() => selectedLog.value?.diff_items || [])
const detailPanel = ref<HTMLElement>()
let returnFocus: HTMLElement | null = null
const detailSwitch = createDetailSwitch<OperationLog>(async () => true, async (row, current) => {
  if (current() && detailVisible.value) selectedLog.value = row
})
function selectRow(row: OperationLog) { if (detailVisible.value) void detailSwitch.select(row) }
function closeDetail() {
  detailSwitch.invalidate(); detailVisible.value = false; selectedLog.value = null
  if (returnFocus?.isConnected) returnFocus.focus()
  returnFocus = null
}

function toStartDate(date?: string) {
  return date ? `${date}T00:00:00` : undefined
}

function toEndDate(date?: string) {
  return date ? `${date}T23:59:59` : undefined
}

async function fetchLogs() {
  clearTimeout(logQueryTimer)
  const serial = logListState.begin()
  queryError.value = ''
  try {
    const params: Record<string, string | number | undefined> = {
      page: page.value,
      page_size: pageSize.value,
      ...serverQueryParams(queryApplied.value, []),
    }
    const data = await request.get('/operation-logs', { params }) as unknown as OperationLogListResponse
    if (!logListState.isCurrent(serial)) return
    querySupported.value = requireServerQueryVersion(data as {query_version?:number}, !!queryApplied.value.length || !!columnFilters.value.length)
    moduleOptions.value = data.modules || []
    actionOptions.value = data.actions || []
    logs.value = data.items || []
    if (detailVisible.value) {
      const latest = logs.value.find(row => row.id === selectedLog.value?.id)
      if (latest) await detailSwitch.select(latest); else closeDetail()
    }
    if (!logListState.isCurrent(serial)) return
    total.value = data.total || 0
    logListState.succeed(serial, logs.value.length === 0)
  } catch (error) {
    if (logListState.isCurrent(serial)) {
      closeDetail(); queryError.value = error instanceof Error ? error.message : '操作日志查询失败，请重试'; logs.value = []; total.value = 0
      logListState.fail(serial, error)
    }
  }
}

function handleBaseFilterChange() {
  page.value = 1
}

async function openDetail(row: OperationLog) {
  if (!detailVisible.value) returnFocus = document.activeElement as HTMLElement
  detailVisible.value = true
  await detailSwitch.select(row)
  await nextTick()
  detailPanel.value?.focus()
}

function actionLabel(action: string) { return actionOptions.value.find(item => item.value === action)?.label || '其他操作' }

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

function parseJson(value?: string | null) {
  if (!value) return null
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function formatJsonValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function formatPrettyJson(value?: string | null) {
  const parsed = parseJson(value)
  if (!parsed) return '-'
  return JSON.stringify(parsed, null, 2)
}

watch([queryApplied, pageSize], () => { page.value = 1; pageColumns.clear() }, { deep: true, flush: 'sync' })
watch([page, pageSize, queryApplied], () => {
  logListState.invalidate(true)
  clearTimeout(logQueryTimer)
  logQueryTimer = setTimeout(fetchLogs, 200)
}, { deep: true })
onUnmounted(() => { detailSwitch.invalidate(); logListState.invalidate(); clearTimeout(logQueryTimer) })

onMounted(fetchLogs)
</script>

<style scoped>

.operation-audit-layout { position: relative; display: flex; gap: 6px; flex: 1; min-width: 0; min-height: 0; height: 100%; font: var(--pms-font-size-base)/1.6 var(--pms-font); }
.operation-audit-list { flex: 1; width: 0; min-width: 0; }
.operation-audit-detail-button { --el-button-text-color: var(--pms-info); --el-button-hover-text-color: var(--pms-info); }
.gov-audit-state { display: flex; align-items: center; flex-direction: column; gap: 8px; padding: 24px 16px; color: var(--pms-text-secondary); line-height: 1.6; }
.gov-audit-state > svg { width: 24px; height: 24px; color: var(--pms-text-muted); }
.gov-audit-state strong { color: var(--pms-text); font-size: var(--pms-font-size-base); font-weight: 500; }
.gov-audit-state p { margin: 0; }
.operation-audit-detail { position: relative; display: flex; flex: 0 0 var(--pms-drawer-width); flex-direction: column; width: var(--pms-drawer-width); max-width: 48%; min-height: 0; border: 1px solid var(--pms-border); border-radius: var(--pms-radius-sm); background: var(--pms-surface); box-shadow: var(--pms-shadow-sm); }
.operation-audit-detail:focus { outline: none; }
.operation-audit-detail:focus-visible { outline: 2px solid var(--pms-primary); outline-offset: -2px; }
.audit-detail-header { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; min-height: 44px; padding: 0 12px; border-bottom: 1px solid var(--pms-border-soft); }
.audit-detail-header h2 { margin: 0; font-size: var(--pms-font-size-md); font-weight: 600; }
.audit-close { display: inline-grid; place-items: center; width: 28px; height: 28px; padding: 0; border: 0; border-radius: var(--pms-radius-sm); background: transparent; color: var(--pms-text-secondary); cursor: pointer; }
.audit-close:hover { background: var(--pms-primary-soft); color: var(--pms-primary); }
.audit-close svg { width: 16px; height: 16px; }
.audit-detail-body { padding: 12px; overflow: auto; min-height: 0; }
.audit-meta { display: grid; grid-template-columns: 52px minmax(0, 1fr); align-items: center; column-gap: 12px; row-gap: 8px; margin: 0; }
.audit-meta dt { color: var(--pms-text-secondary); }
.audit-meta dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
.audit-section { margin-top: 20px; }
.audit-section h3 { margin: 0 0 8px; font-size: var(--pms-font-size-base); font-weight: 600; }
.audit-section p { margin: 0; line-height: 1.8; }
.gov-audit-muted { color: var(--pms-text-secondary); }
.audit-diff { width: 100%; table-layout: fixed; border-collapse: collapse; }
.audit-diff th, .audit-diff td { padding: 6px 8px; border: 1px solid var(--pms-border-soft); text-align: left; font-weight: 400; overflow-wrap: anywhere; }
.audit-diff thead th { background: var(--pms-surface-muted); color: var(--pms-text-secondary); text-align: center; font-size: var(--pms-font-size-sm); }
.audit-diff tbody th { width: 28%; color: var(--pms-text-secondary); }
.audit-technical { margin-top: 20px; padding-top: 12px; border-top: 1px solid var(--pms-border-soft); color: var(--pms-text-secondary); }
.audit-technical summary { width: fit-content; cursor: pointer; }
.audit-technical summary:hover { color: var(--pms-primary); }
.audit-technical pre { margin: 8px 0 0; padding: 8px; border-radius: var(--pms-radius-sm); background: var(--pms-surface-muted); white-space: pre-wrap; overflow-wrap: anywhere; font: var(--pms-font-size-sm)/1.6 var(--pms-font-mono); }
@media(max-width:760px){.operation-audit-layout{flex-direction:column;overflow:auto}.operation-audit-list{flex:0 0 320px;width:100%}.operation-audit-detail{flex:1 0 320px;width:100%;max-width:100%}}

.operation-log-hint{font-size:12px;color:var(--pms-text-secondary)}
.detail-error{color:var(--pms-danger)}
</style>
