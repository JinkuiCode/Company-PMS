<template>
  <PmsDataList class="pms-system-page" :show-scrollbar="false" scrollbar-label="操作日志表格横向滚动条">
    <template #toolbar-left>
      <el-button size="small" @click="fetchLogs">
        刷新
      </el-button>
    </template>
    <template #toolbar-right>
      <span class="operation-log-hint">记录登录、同步和系统写操作</span>
    </template>

    <template #filters>
      <PmsListFilters
        v-model:filters="customFilters"
        :fields="customFilterFields"
        :active-count="activeCustomFilterCount"
      >
        <el-date-picker
          v-model="baseFilters.timeRange"
          type="daterange"
          size="small"
          value-format="YYYY-MM-DD"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          style="width: 228px;"
          @change="handleBaseFilterChange"
        />
        <el-select
          v-model="baseFilters.module"
          size="small"
          clearable
          placeholder="全部模块"
          style="width: 132px;"
          @change="handleBaseFilterChange"
        >
          <el-option v-for="item in moduleOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-model="baseFilters.action"
          size="small"
          clearable
          placeholder="全部动作"
          style="width: 132px;"
          @change="handleBaseFilterChange"
        >
          <el-option v-for="item in actionOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-model="baseFilters.status"
          size="small"
          clearable
          placeholder="全部状态"
          style="width: 116px;"
          @change="handleBaseFilterChange"
        >
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-input
          v-model="baseFilters.keyword"
          size="small"
          clearable
          placeholder="关键词 / 对象 / 操作者"
          style="width: 220px;"
          @change="handleBaseFilterChange"
          @clear="handleBaseFilterChange"
        />
      </PmsListFilters>
    </template>

    <template #grid>
      <el-table
        v-loading="loading"
        class="pms-dense-table operation-log-table"
        :data="filteredLogs"
        border
        stripe
        height="calc(100vh - 330px)"
        empty-text="暂无操作日志"
      >
        <el-table-column prop="created_at" label="时间" width="168" fixed>
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="104" />
        <el-table-column prop="action" label="动作" width="118">
          <template #default="{ row }">{{ actionLabel(row.action) }}</template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作者" width="116">
          <template #default="{ row }">{{ row.operator_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="entity_name" label="对象" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.entity_name || row.entity_id || '-' }}</template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" min-width="260" show-overflow-tooltip />
        <el-table-column prop="request_path" label="路径" min-width="220" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="88">
          <template #default="{ row }">
            <span class="pms-status" :class="row.status === 'success' ? 'success' : 'danger'">
              <span class="pms-status-dot"></span>
              {{ row.status === 'success' ? '成功' : '失败' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="82" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openDetail(row)">详情</el-button>
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

  <el-drawer
    v-model="detailVisible"
    title="操作日志详情"
    size="560px"
    append-to-body
    class="operation-log-drawer"
  >
    <template v-if="selectedLog">
      <div class="operation-log-detail">
        <div class="detail-meta">
          <div><span>模块</span><strong>{{ selectedLog.module }}</strong></div>
          <div><span>动作</span><strong>{{ actionLabel(selectedLog.action) }}</strong></div>
          <div><span>状态</span><strong>{{ selectedLog.status === 'success' ? '成功' : '失败' }}</strong></div>
          <div><span>时间</span><strong>{{ formatDateTime(selectedLog.created_at) }}</strong></div>
          <div><span>操作者</span><strong>{{ selectedLog.operator_name || '-' }}</strong></div>
          <div><span>IP</span><strong>{{ selectedLog.ip_address || '-' }}</strong></div>
        </div>

        <section>
          <h4>摘要</h4>
          <p>{{ selectedLog.summary }}</p>
          <p v-if="selectedLog.error_msg" class="detail-error">{{ selectedLog.error_msg }}</p>
        </section>

        <section class="diff-section">
          <div class="detail-section-heading">
            <h4>字段差异</h4>
            <span v-if="diffRows.length" class="pms-section-meta">{{ diffRows.length }} 项变更</span>
          </div>
          <div v-if="diffRows.length" class="diff-list">
            <article v-for="row in diffRows" :key="row.field_key" class="diff-item">
              <header class="diff-field">
                <div class="diff-field-name">
                  <strong>{{ row.field_label }}</strong>
                  <span v-if="row.field_group" class="pms-chip">{{ row.field_group }}</span>
                </div>
                <code class="pms-code">{{ row.field_key }}</code>
              </header>
              <div class="diff-values">
                <div class="diff-value-block is-before">
                  <span>变更前</span>
                  <div class="diff-value">{{ row.before_display }}</div>
                </div>
                <span class="diff-arrow" aria-hidden="true">→</span>
                <div class="diff-value-block is-after">
                  <span>变更后</span>
                  <div class="diff-value">{{ row.after_display }}</div>
                </div>
              </div>
            </article>
          </div>
          <el-empty v-else :image-size="48" description="无字段差异" />
        </section>

        <section class="detail-raw">
          <el-collapse>
            <el-collapse-item name="raw-snapshot" title="技术信息（原始快照）">
              <el-tabs>
                <el-tab-pane label="Before">
                  <pre>{{ formatPrettyJson(selectedLog.before_data) }}</pre>
                </el-tab-pane>
                <el-tab-pane label="After">
                  <pre>{{ formatPrettyJson(selectedLog.after_data) }}</pre>
                </el-tab-pane>
              </el-tabs>
            </el-collapse-item>
          </el-collapse>
        </section>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import {
  useListFilters,
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
}

type OperationLogListResponse = {
  total: number
  items: OperationLog[]
}

const moduleOptions: ListFilterOption[] = [
  { label: '认证', value: '认证' },
  { label: '项目档案', value: '项目档案' },
  { label: '项目进度', value: '项目进度' },
  { label: '系统管理', value: '系统管理' },
  { label: 'ERP同步', value: 'ERP同步' },
]

const actionOptions: ListFilterOption[] = [
  { label: '新增', value: 'create' },
  { label: '编辑', value: 'update' },
  { label: '删除', value: 'delete' },
  { label: '登录', value: 'login' },
  { label: '自动登录', value: 'auto_login' },
  { label: '退出', value: 'logout' },
  { label: 'SSO 登录', value: 'sso_login' },
  { label: 'ERP 同步', value: 'sync' },
  { label: '批量同步', value: 'batch_sync' },
]

const customFilterFields: ListFilterField[] = [
  { field: 'module', label: '模块', type: 'select', options: () => moduleOptions },
  { field: 'action', label: '动作', type: 'select', options: () => actionOptions },
  { field: 'entity_type', label: '对象类型', type: 'text' },
  { field: 'entity_name', label: '对象名称', type: 'text' },
  { field: 'operator_name', label: '操作者', type: 'text' },
  { field: 'ip_address', label: 'IP', type: 'text' },
  { field: 'status', label: '状态', type: 'select', options: () => [{ label: '成功', value: 'success' }, { label: '失败', value: 'failed' }] },
  { field: 'created_at', label: '时间', type: 'date' },
]

const { customFilters, activeCustomFilterCount, applyCustomFilters } = useListFilters<OperationLog>(
  customFilterFields as ListFilterField<OperationLog>[],
)

const loading = ref(false)
const logs = ref<OperationLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(15)
const detailVisible = ref(false)
const selectedLog = ref<OperationLog | null>(null)

const baseFilters = reactive({
  timeRange: [] as string[],
  module: '',
  action: '',
  status: '',
  keyword: '',
})

const filteredLogs = computed(() => applyCustomFilters(logs.value))

const diffRows = computed(() => {
  if (selectedLog.value?.diff_items?.length) return selectedLog.value.diff_items
  const diffData = parseJson(selectedLog.value?.diff_data)
  if (!diffData || typeof diffData !== 'object') return []
  return Object.entries(diffData).map(([field, value]) => {
    const item = value as { before?: unknown; after?: unknown }
    return {
      field_key: field,
      field_label: field,
      field_group: null,
      before: item.before,
      after: item.after,
      before_display: formatJsonValue(item.before),
      after_display: formatJsonValue(item.after),
    }
  })
})

function toStartDate(date?: string) {
  return date ? `${date}T00:00:00` : undefined
}

function toEndDate(date?: string) {
  return date ? `${date}T23:59:59` : undefined
}

async function fetchLogs() {
  loading.value = true
  try {
    const params: Record<string, string | number | undefined> = {
      page: page.value,
      page_size: pageSize.value,
      module: baseFilters.module || undefined,
      action: baseFilters.action || undefined,
      status: baseFilters.status || undefined,
      keyword: baseFilters.keyword || undefined,
      start_time: toStartDate(baseFilters.timeRange?.[0]),
      end_time: toEndDate(baseFilters.timeRange?.[1]),
    }
    const data = await request.get('/operation-logs', { params }) as unknown as OperationLogListResponse
    logs.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function handleBaseFilterChange() {
  page.value = 1
  fetchLogs()
}

function openDetail(row: OperationLog) {
  selectedLog.value = row
  detailVisible.value = true
}

function actionLabel(action: string) {
  const found = actionOptions.find(item => item.value === action)
  if (found) return found.label
  const extra: Record<string, string> = {
    sso_verify: 'SSO Token',
    sso_url_login: 'SSO URL',
    oa_login: 'OA 登录',
    oa_password_login: 'OA 账号登录',
  }
  return extra[action] || action
}

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

watch([page, pageSize], () => fetchLogs())

onMounted(fetchLogs)
</script>

<style scoped>
.operation-log-hint {
  color: var(--pms-text-secondary);
  font-size: 12px;
}

.operation-log-table {
  width: 100%;
  border-radius: var(--pms-radius);
}

.operation-log-detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.detail-meta div {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--pms-border-soft);
  border-radius: var(--pms-radius-sm);
  background: #f8fafc;
}

.detail-meta span {
  display: block;
  margin-bottom: 4px;
  color: var(--pms-text-secondary);
  font-size: 12px;
}

.detail-meta strong {
  color: var(--pms-text);
  font-size: 13px;
  font-weight: 700;
  word-break: break-all;
}

.operation-log-detail section h4 {
  margin: 0 0 8px;
  color: var(--pms-text);
  font-size: 14px;
}

.detail-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.detail-section-heading h4 {
  margin-bottom: 0 !important;
}

.diff-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.diff-item {
  overflow: hidden;
  border: 1px solid var(--pms-border-soft);
  border-radius: var(--pms-radius-sm);
  background: var(--pms-surface);
}

.diff-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--pms-border-soft);
  background: var(--pms-surface-muted);
}

.diff-field-name {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.diff-field-name strong {
  color: var(--pms-text);
  font-size: var(--pms-font-size-base);
  font-weight: 650;
}

.diff-field .pms-code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.diff-values {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 22px minmax(0, 1fr);
  align-items: stretch;
  padding: 10px;
}

.diff-value-block {
  min-width: 0;
  padding: 8px 9px;
  border-radius: var(--pms-radius-sm);
  background: var(--pms-neutral-soft);
}

.diff-value-block.is-after {
  background: var(--pms-success-soft);
}

.diff-value-block > span {
  display: block;
  margin-bottom: 5px;
  color: var(--pms-text-muted);
  font-size: var(--pms-font-size-xs);
}

.diff-value {
  color: var(--pms-text-secondary);
  font-size: var(--pms-font-size-base);
  line-height: 1.55;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.diff-value-block.is-after .diff-value {
  color: #08765b;
  font-weight: 550;
}

.diff-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--pms-text-muted);
  font-size: 15px;
}

.operation-log-detail section p {
  margin: 0;
  color: var(--pms-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.detail-error {
  margin-top: 8px !important;
  color: var(--pms-danger) !important;
}

.detail-raw pre {
  max-height: 220px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  border: 1px solid var(--pms-border-soft);
  border-radius: var(--pms-radius-sm);
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.6;
}

.detail-raw :deep(.el-collapse-item__header) {
  color: var(--pms-text-secondary);
  font-size: var(--pms-font-size-sm);
  font-weight: 600;
}

.detail-raw :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

code {
  color: var(--pms-text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
