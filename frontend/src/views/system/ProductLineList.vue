<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import PmsDataList from '@/components/PmsDataList.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import { PmsFormDrawer, PmsFormField, PmsTextControl, PmsSelectControl, PmsNumberControl, PmsSwitchControl } from '@/form-system'
import { getProductLines, getOrganizations, type ProductLine, type Organization } from '@/api/productLine'

const auth = useAuthStore()
const items = ref<ProductLine[]>([])
const total = ref(0), page = ref(1), pageSize = ref(50), keyword = ref('')
const loading = ref(false), failed = ref(false), saving = ref(false), opened = ref(false)
const editing = ref<ProductLine | null>(null)
const organizations = ref<Organization[]>([]), organizationSearch = ref(''), organizationPage = ref(1), organizationTotal = ref(0)
const organizationsLoading = ref(false), organizationFailed = ref(false), error = ref('')
const form = reactive({ organization_id: null as number | null, display_name: '', sort: 0, is_enabled: true })
let listVersion = 0, organizationVersion = 0, baseline = ''
const dirty = computed(() => JSON.stringify(form) !== baseline)
const organizationOptions = computed(() => organizations.value.map(row => ({ value: row.organization_id, label: `${row.code} · ${row.name}` })))
async function load() {
  const version = ++listVersion
  loading.value = true; failed.value = false
  try {
    const data = await getProductLines({ keyword: keyword.value, page: page.value, page_size: pageSize.value })
    if (version !== listVersion) return
    items.value = data.items; total.value = data.total
    if (page.value > 1 && !items.value.length) page.value = Math.max(1, Math.ceil(total.value / pageSize.value))
  } catch { if (version === listVersion) failed.value = true }
  finally { if (version === listVersion) loading.value = false }
}
async function loadOrganizations() {
  const version = ++organizationVersion
  organizationsLoading.value = true; organizationFailed.value = false
  try {
    const data = await getOrganizations({ keyword: organizationSearch.value, page: organizationPage.value, page_size: 50 })
    if (version !== organizationVersion) return
    organizations.value = data.items; organizationTotal.value = data.total
  } catch { if (version === organizationVersion) organizationFailed.value = true }
  finally { if (version === organizationVersion) organizationsLoading.value = false }
}
async function close() {
  if (saving.value) return false
  if (opened.value && dirty.value) {
    try { await ElMessageBox.confirm('放弃尚未保存的产品线修改？', '未保存修改', { type: 'warning' }) }
    catch { return false }
  }
  opened.value = false; ++organizationVersion
  return true
}
async function open(row?: ProductLine) {
  if (!auth.hasPermission(row ? 'system:product-line:edit' : 'system:product-line:add') || !await close()) return
  editing.value = row || null; error.value = ''
  Object.assign(form, { organization_id: row?.organization_id ?? null, display_name: row?.display_name || '', sort: row?.sort || 0, is_enabled: row ? !!row.is_enabled : true })
  baseline = JSON.stringify(form); opened.value = true
  if (!row) { organizationSearch.value = ''; organizationPage.value = 1; await loadOrganizations() }
}
function selectOrganization(value: unknown) {
  form.organization_id = value ? Number(value) : null
  const selected = organizations.value.find(row => row.organization_id === form.organization_id)
  if (selected && !form.display_name) form.display_name = selected.name.slice(0, 128)
}
async function save() {
  if (saving.value || !auth.hasPermission(editing.value ? 'system:product-line:edit' : 'system:product-line:add')) return
  if (!form.organization_id || !form.display_name.trim()) { error.value = '请选择金蝶组织并填写产品线名称'; return }
  saving.value = true; error.value = ''
  try {
    const fields = { display_name: form.display_name.trim(), sort: form.sort }
    if (editing.value) await request.put(`/product-lines/${editing.value.id}`, { ...fields, is_enabled: form.is_enabled, expected_updated_at: editing.value.updated_at })
    else await request.post('/product-lines', { ...fields, organization_id: form.organization_id })
    opened.value = false; ElMessage.success('产品线已保存'); await load()
  } catch (e: any) { error.value = e.response?.status === 409 ? '名称、组织冲突或记录已被修改，请关闭并刷新后重试' : '保存失败，请检查后重试' }
  finally { saving.value = false }
}
async function remove(row: ProductLine) {
  if (!auth.hasPermission('system:product-line:delete') || saving.value) return
  try { await ElMessageBox.confirm(`删除产品线“${row.display_name}”？已被引用的产品线不能删除。`, '删除产品线', { type: 'warning' }) } catch { return }
  saving.value = true
  try { await request.delete(`/product-lines/${row.id}`); ElMessage.success('已删除'); await load() }
  catch { /* The shared request handler displays the rejection; keep the row. */ }
  finally { saving.value = false }
}
function search() { if (page.value !== 1) page.value = 1; else void load() }
function searchOrganizations() { organizationPage.value = 1; void loadOrganizations() }
watch([page, pageSize], load)
onBeforeRouteLeave(close)
onMounted(load)
</script>

<template>
  <PmsDataList :show-scrollbar="false" class="pms-system-page">
    <template #toolbar-left><el-button v-if="auth.hasPermission('system:product-line:add')" type="primary" size="small" :icon="Plus" @click="open()">新增产品线</el-button></template>
    <template #toolbar-right><el-tooltip content="刷新"><el-button :icon="Refresh" size="small" aria-label="刷新产品线" @click="load" /></el-tooltip></template>
    <template #filters><form class="pms-filter-bar product-line-filters" @submit.prevent="search"><PmsTextControl v-model="keyword" size="compact" placeholder="产品线 / 金蝶组织名称或编码" aria-label="搜索产品线" clearable /><el-button size="small" native-type="submit">查询</el-button></form><div v-if="failed" role="alert">产品线读取失败 <el-button link @click="load">重试</el-button></div></template>
    <template #grid>
      <el-table v-loading="loading" :data="items" height="100%" row-key="id" border stripe class="pms-dense-table">
        <el-table-column prop="display_name" label="产品线名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="organization_code" label="金蝶组织编码" width="160" />
        <el-table-column prop="organization_name" label="金蝶组织名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="sort" label="排序" width="80" align="center" />
        <el-table-column label="状态" width="100"><template #default="{ row }"><span class="pms-status" :class="row.is_enabled ? 'pms-status-success' : 'pms-status-neutral'">{{ row.is_enabled ? '启用' : '禁用' }}</span></template></el-table-column>
        <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button v-if="auth.hasPermission('system:product-line:edit')" link type="primary" :disabled="saving" @click="open(row)">编辑</el-button><el-button v-if="auth.hasPermission('system:product-line:delete')" link type="danger" :disabled="saving" @click="remove(row)">删除</el-button></template></el-table-column>
      </el-table>
    </template>
    <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" /></template>
  </PmsDataList>
  <PmsFormDrawer v-model="opened" :title="editing ? '编辑产品线' : '新增产品线'" :busy="saving" :before-close="done => { void close().then(ok => { if (ok) done() }) }">
    <form id="product-line-form" :inert="saving" @submit.prevent="save">
      <h3 class="pms-form-drawer__section">组织归属</h3>
      <template v-if="!editing">
        <PmsFormField field-id="organization-search" label="查找组织"><PmsTextControl id="organization-search" v-model="organizationSearch" aria-label="查找金蝶组织" @keydown.enter.prevent="searchOrganizations" /><el-button size="small" :loading="organizationsLoading" @click="searchOrganizations">查询</el-button></PmsFormField>
        <div v-if="organizationFailed" role="alert">金蝶组织读取失败 <el-button link @click="loadOrganizations">重试</el-button></div>
        <PmsFormField field-id="organization" label="金蝶组织" required><PmsSelectControl id="organization" :model-value="form.organization_id" :options="organizationOptions" :disabled="organizationsLoading || organizationFailed" aria-label="金蝶组织" @update:model-value="selectOrganization" /></PmsFormField>
        <div v-if="organizationTotal > 50" class="product-line-org-pager"><el-button :disabled="organizationPage <= 1 || organizationsLoading" @click="organizationPage--; loadOrganizations()">上一页</el-button><span>{{ organizationPage }} / {{ Math.ceil(organizationTotal / 50) }}</span><el-button :disabled="organizationPage * 50 >= organizationTotal || organizationsLoading" @click="organizationPage++; loadOrganizations()">下一页</el-button></div>
      </template>
      <PmsFormField v-else field-id="organization" label="金蝶组织" hint="组织绑定创建后不可更改"><PmsTextControl id="organization" :model-value="`${editing.organization_code} · ${editing.organization_name}`" readonly aria-label="金蝶组织" /></PmsFormField>
      <h3 class="pms-form-drawer__section">显示设置</h3>
      <PmsFormField field-id="line-name" label="产品线名称" required :error="error"><PmsTextControl id="line-name" v-model="form.display_name" maxlength="128" aria-label="产品线名称" :error="error" /></PmsFormField>
      <PmsFormField field-id="line-sort" label="排序"><PmsNumberControl id="line-sort" v-model="form.sort" :min="0" :max="1000000" :precision="0" aria-label="产品线排序" /></PmsFormField>
      <PmsFormField v-if="editing" field-id="line-enabled" label="启用" hint="禁用后不再用于新建，已授权的历史记录仍可查看"><PmsSwitchControl id="line-enabled" v-model="form.is_enabled" aria-label="启用产品线" /></PmsFormField>
    </form>
    <template #footer><el-button :disabled="saving" @click="close">取消</el-button><el-button type="primary" native-type="submit" form="product-line-form" :loading="saving">保存</el-button></template>
  </PmsFormDrawer>
</template>

<style scoped>
.product-line-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.product-line-filters > :first-child { width: 280px; max-width: 100%; }
.product-line-org-pager { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
</style>
