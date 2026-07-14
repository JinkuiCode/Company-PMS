<template>
  <PmsDataList :show-scrollbar="false" class="pms-system-page field-policy-page">
    <template #toolbar-left>
      <el-segmented
        v-model="moduleCode"
        size="small"
        :options="moduleOptions"
        @change="fetchPolicies"
      />
      <span class="field-policy-count">{{ filteredRows.length }} 个字段</span>
    </template>
    <template #toolbar-right>
      <span v-if="dirtyKeys.size" class="field-policy-dirty">待保存 {{ dirtyKeys.size }} 项</span>
      <el-button v-if="canEdit" size="small" @click="restoreDefaults">恢复默认</el-button>
      <el-button
        v-if="canEdit"
        type="primary"
        size="small"
        :disabled="!dirtyKeys.size"
        :loading="saving"
        @click="savePolicies"
      >
        批量保存
      </el-button>
    </template>

    <template #filters>
      <div class="pms-filter-bar field-policy-filters">
        <el-input
          v-model="filters.keyword"
          size="small"
          clearable
          placeholder="搜索字段名称或编码"
          style="width: 230px"
        />
        <el-select v-model="filters.group" size="small" clearable placeholder="全部分组" style="width: 144px">
          <el-option v-for="group in groupOptions" :key="group.key" :label="group.label" :value="group.key" />
        </el-select>
        <el-select v-model="filters.source" size="small" clearable placeholder="全部来源" style="width: 132px">
          <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button size="small" text @click="resetFilters">清空筛选</el-button>
      </div>
    </template>

    <template #grid>
      <el-table
        v-loading="loading"
        :data="filteredRows"
        border
        stripe
        size="small"
        height="calc(100vh - 236px)"
        row-key="field_key"
        class="pms-dense-table field-policy-table"
        empty-text="暂无字段规则"
      >
        <el-table-column prop="label" label="字段名称" width="150" fixed />
        <el-table-column prop="field_key" label="字段编码" width="210" fixed show-overflow-tooltip>
          <template #default="{ row }"><code class="pms-code">{{ row.field_key }}</code></template>
        </el-table-column>
        <el-table-column prop="group_label" label="分组" width="112" />
        <el-table-column prop="source_type" label="来源" width="104">
          <template #default="{ row }">{{ sourceLabel(row.source_type) }}</template>
        </el-table-column>
        <el-table-column label="业务显示" width="104" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.visible"
              size="small"
              :disabled="!canEdit || row.visible_locked || row.required"
              @change="handleVisibleChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="允许编辑" width="104" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.editable"
              size="small"
              :disabled="!canEdit || row.editable_locked || !row.editable_cap || row.required"
              @change="handleEditableChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="必填" width="88" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.required"
              size="small"
              :disabled="!canEdit || row.required_locked || !row.required_cap || !row.visible || !row.editable"
              @change="handleRequiredChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="列表可选" width="104" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.list_available"
              size="small"
              :disabled="!canEdit || row.list_available_locked || !row.list_available_cap || !row.visible"
              @change="markDirty(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="约束说明" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ policyHint(row) }}</template>
        </el-table-column>
      </el-table>
    </template>
  </PmsDataList>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PmsDataList from '@/components/PmsDataList.vue'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'

type FieldPolicy = {
  field_key: string
  label: string
  group: string
  group_label: string
  value_type: string
  source_type: string
  visible: boolean
  editable: boolean
  required: boolean
  list_available: boolean
  visible_cap: boolean
  editable_cap: boolean
  required_cap: boolean
  list_available_cap: boolean
  visible_locked: boolean
  editable_locked: boolean
  required_locked: boolean
  list_available_locked: boolean
  required_effective_at?: string | null
  updated_at?: string | null
}

type FieldPolicyResponse = {
  module_code: string
  groups: Array<{ key: string; label: string }>
  items: FieldPolicy[]
}

const authStore = useAuthStore()
const canEdit = computed(() => authStore.hasPermission('system:field-policy:edit'))
const moduleCode = ref('project_archive')
const moduleOptions = [
  { label: '项目档案', value: 'project_archive' },
  { label: '项目进度', value: 'project_progress' },
]
const sourceOptions = [
  { label: '人工维护', value: 'detail' },
  { label: '项目主表', value: 'project' },
  { label: '档案引用', value: 'archive' },
  { label: '自动计算', value: 'computed' },
  { label: '系统维护', value: 'system' },
]
const sourceLabelMap = Object.fromEntries(sourceOptions.map(item => [item.value, item.label]))

const loading = ref(false)
const saving = ref(false)
const rows = ref<FieldPolicy[]>([])
const groupOptions = ref<Array<{ key: string; label: string }>>([])
const dirtyKeys = reactive(new Set<string>())
const filters = reactive({ keyword: '', group: '', source: '' })

const filteredRows = computed(() => rows.value.filter((field) => {
  const keyword = filters.keyword.trim().toLowerCase()
  if (keyword && !field.label.toLowerCase().includes(keyword) && !field.field_key.toLowerCase().includes(keyword)) return false
  if (filters.group && field.group !== filters.group) return false
  if (filters.source && field.source_type !== filters.source) return false
  return true
}))

function sourceLabel(source: string) {
  return sourceLabelMap[source] || source
}

function policyHint(field: FieldPolicy) {
  if (!field.editable_cap) return field.source_type === 'computed' ? '计算字段，不能人工修改' : '引用或系统字段，不能人工修改'
  if (field.required_locked) return '核心结构字段，必填规则由系统锁定'
  if (field.required && field.required_effective_at) return `仅约束 ${field.required_effective_at.slice(0, 10)} 后新建的数据`
  return '可由业务管理员配置'
}

function markDirty(field: FieldPolicy) {
  dirtyKeys.add(field.field_key)
}

function handleVisibleChange(field: FieldPolicy) {
  if (!field.visible) {
    field.required = false
    field.list_available = false
  }
  markDirty(field)
}

function handleEditableChange(field: FieldPolicy) {
  if (!field.editable) field.required = false
  markDirty(field)
}

function handleRequiredChange(field: FieldPolicy) {
  if (field.required) {
    field.visible = true
    field.editable = true
  }
  markDirty(field)
}

function resetFilters() {
  Object.assign(filters, { keyword: '', group: '', source: '' })
}

async function fetchPolicies() {
  loading.value = true
  dirtyKeys.clear()
  try {
    const response = await request.get('/field-policies', { params: { module: moduleCode.value } }) as unknown as FieldPolicyResponse
    rows.value = response.items.map(field => ({ ...field }))
    groupOptions.value = response.groups || []
  } finally {
    loading.value = false
  }
}

async function savePolicies() {
  if (!canEdit.value || !dirtyKeys.size) return
  saving.value = true
  try {
    const items = rows.value
      .filter(field => dirtyKeys.has(field.field_key))
      .map(field => ({
        field_key: field.field_key,
        visible: field.visible,
        editable: field.editable,
        required: field.required,
        list_available: field.list_available,
        expected_updated_at: field.updated_at || null,
      }))
    await request.put(`/field-policies/${moduleCode.value}`, { items })
    ElMessage.success(`已保存 ${items.length} 项字段规则`)
    await fetchPolicies()
  } finally {
    saving.value = false
  }
}

async function restoreDefaults() {
  if (!canEdit.value) return
  await ElMessageBox.confirm('将当前模块恢复为代码默认字段规则？', '恢复默认', { type: 'warning' })
  await request.post(`/field-policies/${moduleCode.value}/reset`)
  ElMessage.success('已恢复代码默认值')
  await fetchPolicies()
}

onMounted(fetchPolicies)
</script>

<style scoped>
.field-policy-page {
  display: flex;
  height: calc(100vh - 88px);
  min-height: 520px;
  flex-direction: column;
}

.field-policy-page :deep(.pms-data-list-grid-shell) {
  min-height: 0;
  flex: 1;
}

.field-policy-count,
.field-policy-dirty {
  color: var(--pms-text-secondary);
  font-size: 12px;
}

.field-policy-dirty {
  color: var(--pms-warning);
  font-weight: 600;
}

.field-policy-filters {
  gap: 8px;
  margin-bottom: 10px;
}

.field-policy-table :deep(.el-switch) {
  height: 24px;
}

.field-policy-table code {
  color: var(--pms-text-secondary);
  font-family: var(--pms-font-mono);
  font-size: 12px;
}
</style>
