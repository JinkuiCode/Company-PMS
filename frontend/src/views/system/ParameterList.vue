<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import PmsQueryColumnHeader from '@/query-system/PmsQueryColumnHeader.vue'
import { useSystemQuery } from '@/query-system/system-adapter'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onBeforeRouteLeave } from 'vue-router'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { PmsTextControl, PmsFormField, PmsSelectControl } from '@/form-system'

interface Parameter { code: string; name: string; group: string; description: string; sensitive: boolean; configured: boolean; version: number; updated_at: string | null; value: string | null; value_type?: string; reveal_status?: string; reveal_message?: string | null }
const auth = useAuthStore()
const items = ref<Parameter[]>([])
const groups = computed(() => Array.from(new Set(items.value.map(item => item.group))).map(value => ({ label: value, value })))
const { fields: queryFields, defaults: queryDefaults, draft: queryDraft, submit: submitQuery, filterRows, clearColumns, columnContext, columnFilters, columnClass: queryColumnClass } = useSystemQuery(() => [
  { field: 'name', label: '参数名称', type: 'text' },
  { field: 'code', label: '参数编码', type: 'text' },
  { field: 'group', label: '分组', type: 'enum', options: groups.value },
  { field: 'description', label: '用途', type: 'text' },
  { field: 'configured', label: '设置状态', type: 'enum', options:[{value:1,label:'已设置'},{value:0,label:'未设置'}] },
], ['name', 'group'], {ready:()=>!loading.value})
function clearQueryColumns() { clearColumns() }
const loading = ref(false)
const failed = ref(false)
const editing = ref<Parameter | null>(null)
const value = ref('')
const revealSecret = ref(false)
const saving = ref(false)
const error = ref('')
const table = ref()
const filtered = computed(() => filterRows(items.value, row => ({ name: row.name, code: row.code, group: row.group, description: row.description, configured: Number(row.configured) })))
let active = true
let securityEpoch = 0
let loadSequence = 0
function resetDraft() {
  editing.value = null; value.value = ''; error.value = ''; revealSecret.value = false
}
function clearMemory() {
  securityEpoch++
  loadSequence++
  for (const item of items.value) if (item.sensitive) item.value = null
  items.value = []
  resetDraft()
}
function currentValue(row: Parameter) {
  if (!auth.hasPermission('system:parameter:view')) return ''
  if (!row.configured) return '未设置'
  if (row.sensitive) {
    if (row.code !== 'user.initial_password') return '已设置 · 不回显'
    if (row.reveal_status === 'available' && row.value !== null) return row.value
    return row.reveal_message || '已设置 · 需重新保存后回显'
  }
  return row.value_type === 'boolean' ? (row.value === 'true' ? '开启' : '关闭') : row.value
}
watch(() => auth.hasPermission('system:parameter:view'), allowed => {
  if (!allowed) clearMemory()
}, { flush: 'sync' })
watch(() => auth.hasPermission('system:parameter:edit'), allowed => {
  if (!allowed) resetDraft()
}, { flush: 'sync' })
async function focusFirstInvalid() {
  await nextTick()
  if (editing.value && error.value) document.getElementById(`parameter-${editing.value.code}`)?.focus()
}
async function load() {
  if (!active || !auth.hasPermission('system:parameter:view')) { clearMemory(); return }
  const epoch = securityEpoch
  const sequence = ++loadSequence
  loading.value = true
  failed.value = false
  try {
    const result = await request.get('/parameters') as any
    if (active && epoch === securityEpoch && sequence === loadSequence && auth.hasPermission('system:parameter:view')) {
      for (const item of items.value) if (item.sensitive) item.value = null
      items.value = result.items.map((item: Parameter) => item.sensitive && item.code !== 'user.initial_password' ? { ...item, value: null } : item)
    }
  } catch (e: any) {
    if (!active || epoch !== securityEpoch || sequence !== loadSequence) return
    if (e.response?.status === 401 || e.response?.status === 403) clearMemory()
    failed.value = true
  } finally { if (sequence === loadSequence || epoch !== securityEpoch) loading.value = false }
}
async function discard() {
  if (saving.value) return false
  if (editing.value && value.value) {
    try { await ElMessageBox.confirm('放弃尚未保存的参数修改？', '未保存修改', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' }) }
    catch { return false }
  }
  resetDraft()
  return true
}
async function edit(row: Parameter) {
  if (!auth.hasPermission('system:parameter:edit') || !await discard()) return
  if (!active || !auth.hasPermission('system:parameter:view') || !auth.hasPermission('system:parameter:edit')) return
  editing.value = row
  value.value = row.sensitive ? '' : row.value || ''
}
async function save() {
  if (!editing.value || saving.value || !active || !auth.hasPermission('system:parameter:view') || !auth.hasPermission('system:parameter:edit')) return
  if (!value.value) { error.value = '请输入参数值'; await focusFirstInvalid(); return }
  saving.value = true; error.value = ''
  const epoch = securityEpoch
  try {
    await request.put(`/parameters/${encodeURIComponent(editing.value.code)}`, { value: value.value, version: editing.value.version })
    if (!active || epoch !== securityEpoch || !auth.hasPermission('system:parameter:view')) return
    resetDraft()
    ElMessage.success('参数已保存')
    await load()
  } catch (e: any) {
    if (!active || epoch !== securityEpoch) return
    if (e.response?.status === 401 || e.response?.status === 403) { clearMemory(); return }
    if (!auth.hasPermission('system:parameter:edit')) return
    error.value = e.response?.status === 409 ? '参数已被其他管理员修改，请取消并刷新后重试' : '保存失败，请检查后重试'
  } finally { saving.value = false; await focusFirstInvalid() }
}
onBeforeRouteLeave(() => discard())
onBeforeUnmount(() => { active = false; clearMemory() })
onMounted(load)
</script>

<template>
  <div class="parameter-page pms-system-page pms-surface-section">
    <div class="pms-section-header"><span class="pms-section-title">参数设置</span></div>
    <PmsQueryWorkspace v-model="queryDraft" list-key="system-parameter" :fields="queryFields" :defaults="queryDefaults" :loading="loading" @query="submitQuery" @clear-columns="clearQueryColumns" />
    <div v-if="failed" class="parameter-error" role="alert">参数读取失败 <el-button link type="primary" @click="load">重试</el-button></div>
    <el-table ref="table" :data="filtered" row-key="code" class="pms-dense-table" border height="100%" v-loading="loading" :expand-row-keys="editing ? [editing.code] : []">
      <el-table-column type="expand" width="1"><template #default="{ row }">
        <form v-if="editing?.code === row.code" class="parameter-editor" @submit.prevent="save">
          <PmsFormField v-slot="{ describedBy, invalid }" :field-id="`parameter-${row.code}`" label="新参数值" required :error="error">
            <PmsSelectControl v-if="row.value_type === 'boolean'" :id="`parameter-${row.code}`" v-model="value" :options="[{value:'true',label:'开启'},{value:'false',label:'关闭'}]" :aria-describedby="describedBy" :aria-invalid="invalid" aria-required="true" :error="error" :disabled="saving" aria-label="新参数值" />
            <PmsTextControl v-else :id="`parameter-${row.code}`" v-model="value" :aria-describedby="describedBy" :aria-invalid="invalid" aria-required="true" :type="row.sensitive && !revealSecret ? 'password' : 'text'" :error="error" :disabled="saving" maxlength="64" autocomplete="new-password" aria-label="新参数值">
              <template v-if="row.sensitive" #suffix><el-button text :disabled="saving || !value" :aria-controls="`parameter-${row.code}`" :aria-pressed="revealSecret" :aria-label="revealSecret ? '隐藏新密码' : '显示新密码'" @click="revealSecret = !revealSecret">{{ revealSecret ? '隐藏' : '显示' }}</el-button></template>
            </PmsTextControl>
          </PmsFormField>
          <div class="parameter-editor__actions"><el-button :disabled="saving" @click="discard">取消</el-button><el-button type="primary" native-type="submit" :loading="saving">保存</el-button></div>
        </form>
      </template></el-table-column>
      <el-table-column label="参数名称" min-width="190" :class-name="queryColumnClass('name')" :label-class-name="queryColumnClass('name')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'name',displayName:'参数名称'}" /></template><template #default="{ row }"><div class="parameter-name">{{ row.name }}</div><div class="parameter-code">{{ row.code }}</div></template></el-table-column>
      <el-table-column prop="group" label="分组" width="120" :class-name="queryColumnClass('group')" :label-class-name="queryColumnClass('group')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'group',displayName:'分组'}" /></template></el-table-column>
      <el-table-column label="当前值" min-width="210" :class-name="queryColumnClass('configured')" :label-class-name="queryColumnClass('configured')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'configured',displayName:'当前值'}" /></template><template #default="{ row }"><span :class="['pms-status', 'parameter-current-value', row.configured ? 'pms-status-success' : 'pms-status-warning']">{{ currentValue(row) }}</span></template></el-table-column>
      <el-table-column prop="description" label="用途" min-width="280" show-overflow-tooltip :class-name="queryColumnClass('description')" :label-class-name="queryColumnClass('description')"><template #header><PmsQueryColumnHeader :params="{contextQuery:() => columnContext,field:'description',displayName:'用途'}" /></template></el-table-column>
      <el-table-column label="操作" width="88" fixed="right"><template #default="{ row }"><el-button v-if="auth.hasPermission('system:parameter:edit')" link type="primary" :disabled="saving" @click="edit(row)">修改</el-button></template></el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.parameter-page { display: flex; flex-direction: column; min-height: 0; height: 100%; }
.pms-section-header { flex: 0 0 auto; gap: var(--pms-query-gap); }
.pms-section-header { flex-wrap: wrap; }
.parameter-filters { display: flex; gap: var(--pms-query-gap); flex-wrap: wrap; max-width: 100%; }
.parameter-filters > :first-child { width: 160px; }
.parameter-filters > :last-child { width: 260px; max-width: 100%; }
.parameter-name { font-weight: 500; }
.parameter-code { font-size: 11px; color: var(--pms-text-muted); }
.parameter-current-value { max-width: 100%; height: auto; min-height: 24px; line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; }
.parameter-editor { display: flex; align-items: flex-end; gap: 16px; padding: 16px 24px; background: var(--pms-bg); flex-wrap: wrap; }
.parameter-editor > :first-child { width: 320px; max-width: 100%; }
.parameter-editor__actions { display: flex; gap: 8px; padding-bottom: 2px; }
.parameter-error { padding: 12px; color: var(--pms-danger); }
</style>
