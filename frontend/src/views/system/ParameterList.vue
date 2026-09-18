<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onBeforeRouteLeave } from 'vue-router'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { PmsTextControl, PmsFormField, PmsSelectControl } from '@/form-system'

interface Parameter { code: string; name: string; group: string; description: string; sensitive: boolean; configured: boolean; version: number; updated_at: string | null; value: string | null }
const auth = useAuthStore()
const items = ref<Parameter[]>([])
const search = ref('')
const group = ref('')
const groups = computed(() => [{ label: '全部分组', value: '' }, ...Array.from(new Set(items.value.map(item => item.group))).map(value => ({ label: value, value }))])
const loading = ref(false)
const failed = ref(false)
const editing = ref<Parameter | null>(null)
const value = ref('')
const revealSecret = ref(false)
const saving = ref(false)
const error = ref('')
const table = ref()
const filtered = computed(() => items.value.filter(item => (!group.value || item.group === group.value) && `${item.name} ${item.code} ${item.group}`.toLowerCase().includes(search.value.trim().toLowerCase())))
async function focusFirstInvalid() {
  await nextTick()
  if (editing.value && error.value) document.getElementById(`parameter-${editing.value.code}`)?.focus()
}
async function load() {
  loading.value = true
  failed.value = false
  try { const result = await request.get('/parameters') as any; items.value = result.items }
  catch { failed.value = true }
  finally { loading.value = false }
}
async function discard() {
  if (saving.value) return false
  if (editing.value && value.value) {
    try { await ElMessageBox.confirm('放弃尚未保存的参数修改？', '未保存修改', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' }) }
    catch { return false }
  }
  editing.value = null; value.value = ''; error.value = ''; revealSecret.value = false
  return true
}
async function edit(row: Parameter) {
  if (!auth.hasPermission('system:parameter:edit') || !await discard()) return
  editing.value = row
  value.value = row.sensitive ? '' : row.value || ''
}
async function save() {
  if (!editing.value || saving.value || !auth.hasPermission('system:parameter:edit')) return
  if (!value.value) { error.value = '请输入参数值'; await focusFirstInvalid(); return }
  saving.value = true; error.value = ''
  try {
    await request.put(`/parameters/${encodeURIComponent(editing.value.code)}`, { value: value.value, version: editing.value.version })
    value.value = ''; editing.value = null; revealSecret.value = false
    ElMessage.success('参数已保存')
    await load()
  } catch (e: any) {
    error.value = e.response?.status === 409 ? '参数已被其他管理员修改，请取消并刷新后重试' : '保存失败，请检查后重试'
  } finally { saving.value = false; await focusFirstInvalid() }
}
onBeforeRouteLeave(() => discard())
onMounted(load)
</script>

<template>
  <div class="parameter-page pms-system-page pms-surface-section">
    <div class="pms-section-header"><span class="pms-section-title">参数设置</span><div class="parameter-filters"><PmsSelectControl :model-value="group" :options="groups" aria-label="参数分组" :disabled="!!editing" @update:model-value="group = String($event ?? '')" /><PmsTextControl v-model="search" placeholder="搜索参数名称 / 编码" aria-label="搜索参数" clearable :disabled="!!editing" /></div></div>
    <div v-if="failed" class="parameter-error" role="alert">参数读取失败 <el-button link type="primary" @click="load">重试</el-button></div>
    <el-table ref="table" :data="filtered" row-key="code" class="pms-dense-table" border height="100%" v-loading="loading" :expand-row-keys="editing ? [editing.code] : []">
      <el-table-column type="expand" width="1"><template #default="{ row }">
        <form v-if="editing?.code === row.code" class="parameter-editor" @submit.prevent="save">
          <PmsFormField v-slot="{ describedBy, invalid }" :field-id="`parameter-${row.code}`" label="新参数值" required :error="error">
            <PmsTextControl :id="`parameter-${row.code}`" v-model="value" :aria-describedby="describedBy" :aria-invalid="invalid" aria-required="true" :type="row.sensitive && !revealSecret ? 'password' : 'text'" :error="error" :disabled="saving" maxlength="64" autocomplete="new-password" aria-label="新参数值">
              <template v-if="row.sensitive" #suffix><el-button text :disabled="saving || !value" :aria-controls="`parameter-${row.code}`" :aria-pressed="revealSecret" :aria-label="revealSecret ? '隐藏新密码' : '显示新密码'" @click="revealSecret = !revealSecret">{{ revealSecret ? '隐藏' : '显示' }}</el-button></template>
            </PmsTextControl>
          </PmsFormField>
          <div class="parameter-editor__actions"><el-button :disabled="saving" @click="discard">取消</el-button><el-button type="primary" native-type="submit" :loading="saving">保存</el-button></div>
        </form>
      </template></el-table-column>
      <el-table-column label="参数名称" min-width="190"><template #default="{ row }"><div class="parameter-name">{{ row.name }}</div><div class="parameter-code">{{ row.code }}</div></template></el-table-column>
      <el-table-column prop="group" label="分组" width="120" />
      <el-table-column label="当前值" width="150"><template #default="{ row }"><span :class="['pms-status', row.configured ? 'pms-status-success' : 'pms-status-warning']">{{ row.configured ? (row.sensitive ? '已设置 · 不回显' : row.value) : '未设置' }}</span></template></el-table-column>
      <el-table-column prop="description" label="用途" min-width="280" show-overflow-tooltip />
      <el-table-column label="操作" width="88" fixed="right"><template #default="{ row }"><el-button v-if="auth.hasPermission('system:parameter:edit')" link type="primary" :disabled="saving" @click="edit(row)">修改</el-button></template></el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.parameter-page { display: flex; flex-direction: column; min-height: 0; height: 100%; }
.pms-section-header { flex: 0 0 auto; gap: 24px; }
.pms-section-header { flex-wrap: wrap; }
.parameter-filters { display: flex; gap: 12px; flex-wrap: wrap; max-width: 100%; }
.parameter-filters > :first-child { width: 160px; }
.parameter-filters > :last-child { width: 260px; max-width: 100%; }
.parameter-name { font-weight: 500; }
.parameter-code { font-size: 11px; color: var(--pms-text-muted); }
.parameter-editor { display: flex; align-items: flex-end; gap: 16px; padding: 16px 24px; background: var(--pms-bg); flex-wrap: wrap; }
.parameter-editor > :first-child { width: 320px; max-width: 100%; }
.parameter-editor__actions { display: flex; gap: 8px; padding-bottom: 2px; }
.parameter-error { padding: 12px; color: var(--pms-danger); }
</style>
