<template>
  <div class="pms-page pms-system-page enum-page">
    <aside class="enum-master">
      <div class="enum-master-head">
        <div>
          <strong>枚举管理</strong>
          <span>{{ filteredDicts.length }} 项</span>
        </div>
        <PmsTextControl v-model="searchText" size="compact" clearable placeholder="搜索枚举" aria-label="搜索枚举" />
      </div>
      <div class="enum-master-list">
        <button
          v-for="item in filteredDicts"
          :key="item.id"
          type="button"
          class="enum-master-item"
          :class="{ active: selectedDictId === item.id }"
          @click="selectDict(item.id)"
        >
          <span class="enum-master-name">{{ item.dict_name }}</span>
          <span class="enum-master-meta">{{ item.item_count }} 个值</span>
          <span class="enum-mode" :class="item.mode">{{ item.mode === 'configurable' ? '可配置' : '固定流程' }}</span>
        </button>
        <el-empty v-if="!filteredDicts.length" :image-size="48" description="暂无已注册枚举" />
      </div>
    </aside>

    <section class="enum-detail">
      <template v-if="selectedDict">
        <header class="enum-detail-head">
          <div class="enum-identity">
            <div class="enum-title-line">
              <h2>{{ selectedDict.dict_name }}</h2>
              <code>{{ selectedDict.dict_code }}</code>
            </div>
            <p>{{ selectedDict.description || '开发注册的业务枚举' }}</p>
            <div class="enum-bindings">
              <span v-for="binding in selectedDict.bindings" :key="binding">{{ binding }}</span>
            </div>
          </div>
          <el-button
            v-if="selectedDict.allow_add && hasPermission('system:enum:add')"
            type="primary"
            size="small"
            @click="openItemDialog()"
          >
            新增值
          </el-button>
        </header>

        <el-table
          v-loading="itemsLoading"
          :data="dictItems"
          border
          stripe
          size="small"
          height="100%"
          empty-text="暂无枚举值"
          class="pms-dense-table enum-value-table"
        >
          <el-table-column prop="item_value" label="存储值" min-width="140" fixed>
            <template #default="{ row }"><code class="pms-code">{{ row.item_value }}</code></template>
          </el-table-column>
          <el-table-column prop="item_label" label="显示名称" min-width="180" />
          <el-table-column prop="sort" label="排序" width="76" align="center" />
          <el-table-column prop="reference_count" label="引用数" width="86" align="center">
            <template #default="{ row }">
              <span :class="{ 'has-reference': row.reference_count > 0 }">{{ row.reference_count }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="92" align="center">
            <template #default="{ row }">
              <span class="pms-status" :class="row.status === 1 ? 'success' : 'neutral'">
                <span class="pms-status-dot"></span>{{ row.status === 1 ? '启用' : '禁用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="194" align="center" fixed="right">
            <template #default="{ row }">
              <el-button v-if="hasPermission('system:enum:edit')" link type="primary" size="small" @click="openItemDialog(row)">编辑</el-button>
              <el-button
                v-if="hasPermission('system:enum:edit')"
                link
                :type="row.status === 1 ? 'warning' : 'success'"
                size="small"
                @click="handleToggleStatus(row)"
              >
                {{ row.status === 1 ? '禁用' : '启用' }}
              </el-button>
              <el-tooltip :content="deleteTooltip(row)" placement="top">
                <span>
                  <el-button
                    v-if="hasPermission('system:enum:delete')"
                    link
                    type="danger"
                    size="small"
                    :disabled="!row.deletable"
                    @click="handleDeleteItem(row)"
                  >删除</el-button>
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="暂无可维护的业务枚举" />
    </section>

    <PmsFormDrawer v-model="itemDialogVisible" :title="isItemEdit ? '编辑枚举值' : '新增枚举值'" :busy="itemSaving">
      <h3 class="pms-form-drawer__section">{{ itemDict?.dict_name }}</h3>
      <el-form id="pms-enum-form" ref="itemFormRef" :model="itemForm" :rules="itemRules" label-position="top" class="pms-standard-dialog-form" @submit.prevent="handleItemSubmit">
        <el-form-item>
          <PmsFormField field-id="enum-storage-value" label="存储值">
            <div id="enum-storage-value" class="enum-generated-value">
              <code v-if="isItemEdit" class="pms-code">{{ itemForm.item_value }}</code>
              <span v-else>保存后由系统自动分配数字流水</span>
            </div>
          </PmsFormField>
        </el-form-item>
        <el-form-item prop="item_label">
          <PmsFormField field-id="enum-item-label" label="显示名称" required>
            <PmsTextControl id="enum-item-label" v-model="itemForm.item_label" :disabled="itemSaving" placeholder="页面展示文字" aria-label="显示名称" />
          </PmsFormField>
        </el-form-item>
        <el-form-item>
          <PmsFormField field-id="enum-item-sort" label="排序">
            <PmsNumberControl id="enum-item-sort" v-model="itemForm.sort" :min="0" :disabled="itemSaving" controls-position="right" aria-label="枚举排序" />
          </PmsFormField>
        </el-form-item>
        <el-form-item>
          <PmsFormField field-id="enum-item-status" label="状态">
            <PmsSwitchControl
              id="enum-item-status"
              :model-value="itemForm.status === 1"
              aria-label="枚举状态"
              :disabled="itemSaving"
              @update:model-value="itemForm.status = $event ? 1 : 0"
            />
          </PmsFormField>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="itemSaving" @click="itemDialogVisible = false">取消</el-button>
        <el-button v-if="hasPermission(isItemEdit ? 'system:enum:edit' : 'system:enum:add')" type="primary" :loading="itemSaving" native-type="submit" form="pms-enum-form">保存</el-button>
      </template>
    </PmsFormDrawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { loadEnumOptions } from '@/composables/useEnumOptions'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'
import { PmsFormDrawer, PmsFormField, PmsNumberControl, PmsSwitchControl, PmsTextControl } from '@/form-system'

type EnumDefinition = {
  id: number
  dict_code: string
  dict_name: string
  description?: string
  mode: 'configurable' | 'workflow'
  allow_add: boolean
  allow_value_edit: boolean
  bindings: string[]
  item_count: number
}

type EnumItem = {
  id: number
  item_value: string
  item_label: string
  sort: number
  status: number
  reference_count: number
  value_locked: boolean
  deletable: boolean
}

const authStore = useAuthStore()
const hasPermission = authStore.hasPermission
const dictList = ref<EnumDefinition[]>([])
const selectedDictId = ref<number | null>(null)
const dictItems = ref<EnumItem[]>([])
const searchText = ref('')
const itemsLoading = ref(false)

const selectedDict = computed(() => dictList.value.find(item => item.id === selectedDictId.value) || null)
const filteredDicts = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return dictList.value
  return dictList.value.filter(item =>
    item.dict_name.toLowerCase().includes(keyword)
    || item.dict_code.toLowerCase().includes(keyword),
  )
})

function selectFirstDict() {
  if (!dictList.value.length) {
    selectedDictId.value = null
    dictItems.value = []
    return
  }
  if (!dictList.value.some(item => item.id === selectedDictId.value)) {
    selectedDictId.value = dictList.value[0].id
  }
  fetchItems()
}

async function fetchDicts() {
  dictList.value = (await request.get('/dicts')) as EnumDefinition[]
  selectFirstDict()
}

function selectDict(id: number) {
  selectedDictId.value = id
  fetchItems()
}

async function fetchItems() {
  if (!selectedDictId.value) return
  itemsLoading.value = true
  try {
    dictItems.value = (await request.get(`/dicts/${selectedDictId.value}/items`)) as EnumItem[]
  } finally {
    itemsLoading.value = false
  }
}

async function refreshSelectedEnumCache() {
  if (!selectedDict.value) return
  await loadEnumOptions(selectedDict.value.dict_code, true)
}

const itemDialogVisible = ref(false)
const isItemEdit = ref(false)
const itemFormRef = ref<FormInstance>()
const itemSaving = ref(false)
const itemDict = ref<EnumDefinition | null>(null)
const itemForm = reactive({ id: 0, item_value: '', item_label: '', sort: 0, status: 1 })
const itemRules: FormRules = {
  item_label: [{ required: true, message: '请输入显示名称' }],
}

function openItemDialog(row?: EnumItem) {
  if (itemSaving.value || !selectedDict.value) return
  if (!hasPermission(row ? 'system:enum:edit' : 'system:enum:add')) return
  itemDict.value = selectedDict.value
  isItemEdit.value = Boolean(row)
  Object.assign(itemForm, row
    ? { id: row.id, item_value: row.item_value, item_label: row.item_label, sort: row.sort, status: row.status }
    : { id: 0, item_value: '', item_label: '', sort: dictItems.value.length + 1, status: 1 })
  itemDialogVisible.value = true
}

async function handleItemSubmit() {
  if (itemSaving.value || !hasPermission(isItemEdit.value ? 'system:enum:edit' : 'system:enum:add')) return
  const valid = await itemFormRef.value?.validate().catch(() => false)
  if (!valid || !itemDict.value || itemSaving.value) return
  const payload = {
    item_label: itemForm.item_label,
    sort: itemForm.sort,
    status: itemForm.status,
  }
  itemSaving.value = true
  try {
    if (isItemEdit.value) {
      await request.put(`/dicts/items/${itemForm.id}`, payload)
      ElMessage.success('枚举值已更新')
    } else {
      await request.post(`/dicts/${itemDict.value.id}/items`, payload)
      ElMessage.success('枚举值已新增')
    }
    itemDialogVisible.value = false
    await loadEnumOptions(itemDict.value.dict_code, true)
    await Promise.all([fetchItems(), fetchDicts()])
  } catch {
    // Request interceptor reports the error; keep the draft available for retry.
  } finally {
    itemSaving.value = false
  }
}

async function handleToggleStatus(row: EnumItem) {
  await request.put(`/dicts/items/${row.id}`, { status: row.status === 1 ? 0 : 1 })
  ElMessage.success(row.status === 1 ? '已禁用，历史数据仍保留显示' : '已启用')
  await refreshSelectedEnumCache()
  await fetchItems()
}

function deleteTooltip(row: EnumItem) {
  if (row.deletable) return '删除未被引用的可配置值'
  if (selectedDict.value?.mode !== 'configurable') return '固定流程枚举不可删除'
  return `已被 ${row.reference_count} 条数据引用，只能禁用`
}

async function handleDeleteItem(row: EnumItem) {
  if (!row.deletable) return
  await ElMessageBox.confirm(`确定删除“${row.item_label}”吗？`, '删除枚举值', { type: 'warning' })
  await request.delete(`/dicts/items/${row.id}`)
  ElMessage.success('枚举值已删除')
  await refreshSelectedEnumCache()
  await Promise.all([fetchItems(), fetchDicts()])
}

onMounted(fetchDicts)
</script>

<style scoped>
.enum-page {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  height: 100%;
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

.enum-master {
  display: flex;
  min-width: 0;
  flex-direction: column;
  border-right: 1px solid var(--pms-border);
  background: #f8fafc;
}

.enum-master-head {
  display: grid;
  gap: 10px;
  padding: 14px 12px 12px;
  border-bottom: 1px solid var(--pms-border);
}

.enum-master-head > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.enum-master-head strong {
  color: var(--pms-text);
  font-size: 14px;
}

.enum-master-head span {
  color: var(--pms-text-secondary);
  font-size: 12px;
}

.enum-master-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.enum-master-item {
  position: relative;
  display: grid;
  width: 100%;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px 8px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--pms-text);
  cursor: pointer;
  text-align: left;
}

.enum-master-item:hover {
  background: #fff;
}

.enum-master-item.active {
  border-color: #c7d2fe;
  background: #eef2ff;
}

.enum-master-name {
  overflow: hidden;
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.enum-master-meta {
  color: var(--pms-text-secondary);
  font-size: 11px;
}

.enum-mode {
  grid-row: 1 / span 2;
  grid-column: 2;
  align-self: center;
  padding: 2px 5px;
  border-radius: 4px;
  background: #e2e8f0;
  color: #64748b;
  font-size: 10px;
}

.enum-mode.configurable {
  background: #dcfce7;
  color: #047857;
}

.enum-detail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  padding: 14px;
  background: var(--pms-surface);
}

.enum-detail-head {
  flex-shrink: 0;
  display: flex;
  min-height: 74px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
}

.enum-title-line {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.enum-title-line h2 {
  margin: 0;
  color: var(--pms-text);
  font-size: 16px;
}

.enum-title-line code,
.enum-value-table code {
  color: var(--pms-text-secondary);
  font-family: var(--pms-font-mono);
  font-size: 12px;
}

.enum-identity p {
  margin: 5px 0 7px;
  color: var(--pms-text-secondary);
  font-size: 12px;
}

.enum-bindings {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.enum-bindings span {
  padding: 2px 6px;
  border: 1px solid var(--pms-border);
  border-radius: 4px;
  color: var(--pms-text-secondary);
  font-size: 11px;
}

.enum-generated-value {
  display: flex;
  min-height: 30px;
  align-items: center;
  color: var(--pms-text-secondary);
  font-size: 12px;
}

.has-reference {
  color: #b45309;
  font-weight: 650;
}

@media (max-width: 900px) {
  .enum-page {
    grid-template-columns: 180px minmax(560px, 1fr);
    overflow-x: auto;
  }
}
</style>
