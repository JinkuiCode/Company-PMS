<template>
  <section
    class="project-archive-workbench"
  >
    <div class="archive-list-shell">
      <PmsDataList
        v-if="archiveView === 'archives'"
        ref="archiveListRef"
        class="project-archive-page"
        scrollbar-label="项目档案表格横向滚动条"
      >
    <template #toolbar-left>
        <el-button type="primary" plain size="small" @click="showArchiveChanges">变更审批</el-button>
        <el-button v-if="hasPermission('project:archive:add')" type="primary" size="small" @click="openCreateDialog">
          <el-icon style="margin-right:4px;"><Plus /></el-icon>
          新增档案
        </el-button>
        <el-button class="pms-button-auxiliary" v-if="hasPermission('project:archive:toggle')" size="small" :disabled="selectedRows.length === 0" @click="handleBatchEnabledChange(true)">
          批量启用
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
        <el-button class="pms-button-auxiliary" v-if="hasPermission('project:archive:toggle')" size="small" :disabled="selectedRows.length === 0" @click="handleBatchEnabledChange(false)">
          批量禁用
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
    </template>
    <template #toolbar-right>
        <BusinessExportControl :resource="{kind:'archives'}" :snapshot="archiveExportSnapshot" :disabled="archiveListLoading || !archiveHasQueried || !total" />
        <PmsListColumnPicker
          :model-value="selectedArchiveColumnKeys"
          :groups="archiveColumnGroups"
          :column-definitions="columnDefs"
          :default-keys="defaultArchiveColumnKeys"
          aria-label="项目档案列设置"
          :get-grid-api="() => gridApi"
          @layout-changed="handleArchiveGridStructureChanged"
          @update:model-value="handleArchiveColumnSelection"
          @restore-defaults="restoreArchiveColumnDefaults"
        />
        <PmsPageGuide page="archive" />
        <OfflineArchiveTools :selected-rows="selectedRows" @changed="fetchList" />
    </template>

    <template #filters>
      <PmsQueryWorkspace entry-mode="document" v-model="customFilters" list-key="project-archive" :fields="archiveQueryFields" :defaults="archiveQueryDefaults" :ready="archiveWorkspaceReady" :loading="archiveListLoading" :snapshot="archivePlanSnapshot" :legacy-schemes="legacyArchiveSchemes" @query="submitArchiveQuery" @clear-columns="clearArchiveColumnFilters" />
    </template>

    <template #grid>
      <div v-if="archiveListError" class="pms-list-load-error" role="alert">加载失败，请重试 <el-button size="small" @click="fetchList">重试</el-button></div>
      <ag-grid-vue
        ref="agGridRef"
        class="ag-theme-alpine wechat-table pms-ag-grid"
        :rowData="visibleArchiveRows"
        :loading="archiveListLoading"
        :columnDefs="columnDefs"
        :defaultColDef="defaultColDef"
        :localeText="localeText"
        :theme="'legacy'"
        :pagination="false"
        :rowSelection="'multiple'"
        :getRowClass="getArchiveRowClass"
        :enableCellTextSelection="true"
        :alwaysShowHorizontalScroll="true"
        @grid-ready="onGridReady"
        @first-data-rendered="scheduleArchiveScrollbarMetrics"
        @grid-size-changed="scheduleArchiveScrollbarMetrics"
        @column-resized="handleArchiveColumnResized"
        @column-moved="handleArchiveGridStructureChanged"
        @column-pinned="handleArchiveGridStructureChanged"
        @displayed-columns-changed="handleArchiveGridStructureChanged"
        @selection-changed="onSelectionChanged"
        @row-clicked="onArchiveRowClicked"
        @sort-changed="handleArchiveSortChanged"
      />
    </template>

    <template #pagination>
      <CustomPagination
        v-if="total > 0"
        v-model="page"
        v-model:page-size="pageSize"
        :total="total"
        @update:model-value="fetchList"
        @update:page-size="() => { page = 1; fetchList() }"
      />
    </template>

        <PmsFormDrawer v-model="dialogVisible" title="新增项目档案" :busy="archiveCreateSaving" :before-close="beforeCloseArchiveCreate">
          <ArchiveRecordForm ref="formRef" class="archive-create-form" :model="form" :groups="archiveCreateGroups" :rules="rules"
            :required="field => archiveFieldRequired(field.key, undefined, form)"
            :editable="field => !archiveCreateSaving && archiveFieldEditable(field.key)"
            :options="key => archiveDrawerSelectOptions(key, form)" :errors="archiveCreateServerErrors" id-prefix="archive-create"
            @field-change="updateArchiveCreateField" />
          <template #footer>
            <el-button type="warning" plain :disabled="archiveCreateSaving" @click="beforeCloseArchiveCreate(() => { dialogVisible = false })">取消</el-button>
            <el-button v-if="hasPermission('project:archive:add')" type="success" :loading="archiveCreateSaving" @click="handleSubmit">新增保存</el-button>
          </template>
        </PmsFormDrawer>
      </PmsDataList>
      <ArchiveChangeList v-else @back="archiveView = 'archives'" @changed="fetchList" />
    </div>

    <PmsFormDrawer v-if="selectedArchive" :model-value="true" :title="selectedArchive.can_edit ? '编辑项目档案' : '查看项目档案'" :busy="archiveDrawerSaving" penetrable :before-close="beforeCloseArchiveDetail">
      <p class="archive-governance-route">{{ selectedArchive.can_edit ? selectedArchive.change_mode === 'direct' ? '部门负责人修改，保存后直接生效' : '项目负责人修改，提交后等待部门负责人审批' : selectedArchive.edit_reason || '当前档案仅供查看' }}</p>
      <ArchiveRecordForm ref="archiveDrawerFormRef" :model="archiveDrawerForm" :groups="archiveDrawerGroups" :rules="archiveDrawerRules"
        :required="archiveDrawerFieldRequired" :editable="archiveDrawerFieldEditable" :options="key => archiveDrawerSelectOptions(key)"
        :format="formatArchiveDrawerValue" :errors="archiveDrawerServerErrors" id-prefix="archive-drawer"
        @field-change="updateArchiveDetailField">
        <OfflineArchiveSource :archive-id="selectedArchive.id" />
      </ArchiveRecordForm>
      <template #secondary><el-button v-if="hasPermission('project:archive:sync')" class="pms-button-navigation" :disabled="archivePendingChangeCount > 0 || ['queued','pending','review'].includes(selectedArchive.erp_sync_status)" :loading="manualSyncBusy" @click="submitArchiveSync">同步金蝶</el-button></template>
      <template #footer>
        <el-button type="warning" plain :disabled="archiveDrawerSaving" @click="closeArchiveDrawer">取消</el-button>
        <el-button v-if="selectedArchive.can_edit && !archiveDrawerReadOnly" :type="selectedArchive.change_mode === 'direct' ? 'success' : 'primary'" :disabled="!archivePendingChangeCount" :loading="archiveDrawerSaving" @click="saveArchiveDrawer()">{{ selectedArchive.change_mode === 'direct' ? '保存生效' : '提交变更' }}</el-button>
      </template>
    </PmsFormDrawer>
    <el-dialog v-model="archiveChangeConfirmOpen" title="确认档案变更" width="min(760px,94vw)" align-center :close-on-click-modal="false" :show-close="!archiveChangeSubmitting" :close-on-press-escape="!archiveChangeSubmitting" @closed="cancelArchiveChangeConfirmation">
      <p class="archive-governance-route">审批人：{{ archiveChangePreview?.approver_name }} · 按原负责人所属部门确定</p>
      <el-table :data="archiveChangePreview?.differences || []" border class="pms-dense-table">
        <el-table-column prop="field_label" label="字段" width="130" />
        <el-table-column prop="before_display" label="修改前" />
        <el-table-column prop="after_display" label="修改后" />
      </el-table>
      <PmsFormField field-id="archive-change-reason" label="变更原因" required :error="archiveChangeReasonError">
        <PmsTextareaControl id="archive-change-reason" v-model="archiveChangeReason" aria-label="变更原因" :rows="3" :maxlength="1024" :disabled="archiveChangeSubmitting" />
      </PmsFormField>
      <template #footer><el-button type="warning" plain :disabled="archiveChangeSubmitting" @click="archiveChangeConfirmOpen = false">返回修改</el-button><el-button type="primary" :loading="archiveChangeSubmitting" @click="submitArchiveChangeRequest">提交审批</el-button></template>
    </el-dialog>
    <SyncLogDrawer v-model="syncLogVisible" :archive-id="syncLogArchiveId" />
  </section>
</template>

<script setup lang="ts">
import OfflineArchiveSource from './OfflineArchiveSource.vue'
import OfflineArchiveTools from './OfflineArchiveTools.vue'
import ArchiveRecordForm from './ArchiveRecordForm.vue'
import { newSubmissionId } from '@/utils/submissionId'
import ArchiveChangeList from './ArchiveChangeList.vue'
import { orderArchiveGroups, governanceFieldVisible, governanceFieldRequired } from './archiveGovernance'
import { offlineArchiveFields, offlineEnumCodes, normalizeOfflineValue } from './offlineArchiveFields'
import { createDetailSwitch } from '@/utils/detailSwitch'
import { confirmDetailSwitch } from '@/composables/confirmDetailSwitch'
import { ref, reactive, computed, defineComponent, h, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Delete, Search, Close } from '@element-plus/icons-vue'
import BusinessExportControl from '@/business-export/BusinessExportControl.vue'
import { businessExportSnapshot } from '@/business-export/snapshot'
import SyncLogDrawer from '@/components/SyncLogDrawer.vue'
import { archiveSyncLabel } from '@/config/syncUi'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef, type ColumnState } from 'ag-grid-community'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsDataList from '@/components/PmsDataList.vue'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, PMS_SINGLE_ACTION_COLUMN as PMS_ACTION_COLUMN } from '@/config/listUi'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import { legacyArchiveSchemes } from '@/query-system/archive-schemes'
import type { QueryDefinition } from '@/query-system/workspace'
import { decorateQueryColumns } from '@/query-system/column-grid'
import type { ColumnFilter, ColumnQueryContext } from '@/query-system/column-filters'
import { usePageColumnFilter } from '@/query-system/page-column-filter'
import { adaptConditions, validateConditions, cloneQuery, type QueryCondition } from '@/query-system/core'
import { toQueryFields, toQueryRecord } from '@/query-system/list-adapter'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import {
  PmsNumberControl,
  PmsDateControl,
  PmsFormField,
  PmsFormDrawer,
  PmsSelectControl,
  PmsTextControl,
  PmsTextareaControl,
  type PmsOption,
} from '@/form-system'
import { type ListFilterField, type ListFilterOption, useListFilters } from '@/composables/useListFilters'
import { loadEnumOptions } from '@/composables/useEnumOptions'
import { useProductLineOptions } from '@/composables/useProductLineOptions'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'
import { getArchiveRegions, type ArchiveRegion } from '@/api/project'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'
import { archiveReference } from '@/query-system/archive-reference'

const localeText = chineseLocaleText
const authStore = useAuthStore()
const productLines = useProductLineOptions()
const syncLogVisible = ref(false)
const syncLogArchiveId = ref<number | null>(null)
const manualSyncBusy = ref(false)
async function submitArchiveSync() {
  const archive = selectedArchive.value
  if (!archive || manualSyncBusy.value || !hasPermission('project:archive:sync')) return
  manualSyncBusy.value = true
  try {
    const result: any = await request.post('/erp/archives/' + archive.id + '/submit')
    ElMessage.success(result.msg)
    if (selectedArchive.value?.id === archive.id) selectedArchive.value.erp_sync_status = 'queued'
    await fetchList()
  } catch { /* 统一请求层显示同步失败原因，保留当前档案供用户处理。 */ }
  finally { manualSyncBusy.value = false }
}
function openSyncLog(id: number) { syncLogArchiveId.value = id; syncLogVisible.value = true }
const hasPermission = authStore.hasPermission

type ArchiveColumnPreferenceState = {
  selected_column_keys: string[]
  columnState: ColumnState[]
}

type EffectiveArchiveField = {
  field_key: string
  label: string
  visible: boolean
  editable: boolean
  required: boolean
  required_effective_at?: string | null
  required_when?: { field: string; values: Array<string | number> } | null
  governance_required?: boolean
  list_available: boolean
}

type ArchiveDrawerValueType = 'number' | 'text' | 'select' | 'user' | 'date' | 'datetime' | 'long_text'

type ArchiveDrawerField = {
  key: string
  label: string
  value_type: ArchiveDrawerValueType
  source_type: 'archive' | 'system'
}

type ArchivePendingChange = {
  value: unknown
  originalValue: unknown
}

const ARCHIVE_COLUMN_STORAGE_KEY = 'pms_project_archive_list_columns_v2'
const LEGACY_ARCHIVE_LAYOUT_KEY = 'pms_archive_grid_layout_v2'

const ARCHIVE_EXPANSION_GROUPS: Array<{ key: string; label: string; fields: ArchiveDrawerField[] }> = [
  { key: 'product', label: '基础信息', fields: [
    { key: 'product_line_id', label: '产品线', value_type: 'select', source_type: 'archive' },
  ] },
  { key: 'delivery', label: '合同与交付', fields: [
    { key: 'contract_signed_date', label: '合同签订日期', value_type: 'date', source_type: 'archive' },
    { key: 'contract_ship_date', label: '合同出货日期', value_type: 'date', source_type: 'archive' },
    { key: 'actual_ship_date', label: '实际出货日期', value_type: 'date', source_type: 'archive' },
    { key: 'warranty_end_date', label: '质保截止日期', value_type: 'date', source_type: 'archive' },
  ] },
  { key: 'contact', label: '收货信息', fields: [
    { key: 'address_province', label: '省份', value_type: 'select', source_type: 'archive' },
    { key: 'address_city', label: '城市', value_type: 'select', source_type: 'archive' },
    { key: 'address_detail', label: '详细地址', value_type: 'long_text', source_type: 'archive' },
    { key: 'project_contact', label: '收货联系人', value_type: 'text', source_type: 'archive' },
    { key: 'contact_phone', label: '联系人手机', value_type: 'text', source_type: 'archive' },
  ] },
]
ARCHIVE_EXPANSION_GROUPS.push({ key: 'offline', label: '档案补充信息', fields: offlineArchiveFields })
const archiveExpansionFields = ARCHIVE_EXPANSION_GROUPS.flatMap(group => group.fields)
const archiveExpansionKeys = new Set(archiveExpansionFields.map(field => field.key))

const ARCHIVE_COLUMN_GROUP_DEFINITIONS = [
  {
    key: 'business',
    label: '业务信息',
    fields: [
      { key: 'customer', label: '客户', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'product_category', label: '产品类别', value_type: 'select', list_available: true, quick_addable: false },
      { key: 'is_enabled', label: '启用状态', value_type: 'select', list_available: true, quick_addable: false },
      { key: 'manager_name', label: '负责人', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'equipment_series', label: '设备系列', value_type: 'select', list_available: true, quick_addable: false },
      { key: 'serial_no', label: '序列号', value_type: 'text', list_available: true, quick_addable: false },
      ...ARCHIVE_EXPANSION_GROUPS[0]!.fields.map(field => ({ ...field, list_available: true, quick_addable: false })),
    ],
  },
  {
    key: 'audit',
    label: '维护信息',
    fields: [
      { key: 'data_origin', label: '档案来源', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'created_by_name', label: '创建人', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'updated_by_name', label: '最后编辑人', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'updated_at', label: '最后编辑时间', value_type: 'datetime', list_available: true, quick_addable: false },
    ],
  },
  {
    key: 'erp',
    label: 'ERP 同步',
    fields: [
      { key: 'erp_sync_time', label: '最后同步时间', value_type: 'datetime', list_available: true, quick_addable: false },
      { key: 'erp_sync_by_name', label: '最后同步人', value_type: 'text', list_available: true, quick_addable: false },
      { key: 'erp_sync_status', label: '同步状态', value_type: 'select', list_available: true, quick_addable: false },
    ],
  },
]

const ARCHIVE_DRAWER_GROUP_DEFINITIONS: Array<{
  key: string
  label: string
  fields: ArchiveDrawerField[]
}> = [
  {
    key: 'basic',
    label: '基础信息',
    fields: [
      { key: 'project_code', label: '项目编号', value_type: 'text', source_type: 'archive' },
      { key: 'project_name', label: '项目名称', value_type: 'text', source_type: 'archive' },
      { key: 'customer', label: '客户', value_type: 'text', source_type: 'archive' },
      { key: 'product_category', label: '产品类别', value_type: 'select', source_type: 'archive' },
      { key: 'manager_id', label: '负责人', value_type: 'user', source_type: 'archive' },
      { key: 'equipment_series', label: '设备系列', value_type: 'select', source_type: 'archive' },
      { key: 'serial_no', label: '序列号', value_type: 'text', source_type: 'archive' },
      ...ARCHIVE_EXPANSION_GROUPS[0]!.fields,
    ],
  },
  {
    key: 'erp',
    label: 'ERP 同步',
    fields: [
      { key: 'erp_sync_status', label: '同步状态', value_type: 'select', source_type: 'system' },
      { key: 'erp_sync_time', label: '最后同步时间', value_type: 'datetime', source_type: 'system' },
      { key: 'erp_sync_by_name', label: '最后同步人', value_type: 'text', source_type: 'system' },
      { key: 'erp_error_msg', label: '同步异常', value_type: 'long_text', source_type: 'system' },
    ],
  },
  {
    key: 'system',
    label: '维护信息',
    fields: [
      { key: 'data_origin', label: '档案来源', value_type: 'text', source_type: 'system' },
      { key: 'created_by_name', label: '创建人', value_type: 'text', source_type: 'system' },
      { key: 'created_at', label: '创建时间', value_type: 'datetime', source_type: 'system' },
      { key: 'updated_by_name', label: '最后编辑人', value_type: 'text', source_type: 'system' },
      { key: 'updated_at', label: '最后编辑时间', value_type: 'datetime', source_type: 'system' },
    ],
  },
]

ARCHIVE_COLUMN_GROUP_DEFINITIONS.splice(1, 0, ...ARCHIVE_EXPANSION_GROUPS.slice(1).map(group => ({
  ...group, fields: group.fields.map(field => ({ ...field, list_available: true, quick_addable: false })),
})))
ARCHIVE_DRAWER_GROUP_DEFINITIONS.splice(1, 0, ...ARCHIVE_EXPANSION_GROUPS.slice(1))
const archiveOrderedGroups = orderArchiveGroups(ARCHIVE_DRAWER_GROUP_DEFINITIONS)

const archiveColumnPolicyKey: Record<string, string> = {
  manager_name: 'manager_id',
}
const baseArchiveColumnKeys = ARCHIVE_COLUMN_GROUP_DEFINITIONS.flatMap(group => group.fields.map(field => field.key))
const effectiveArchiveFields = ref<EffectiveArchiveField[]>([])
const effectiveArchiveFieldMap = computed(() => new Map(
  effectiveArchiveFields.value.map(field => [field.field_key, field]),
))
const legacyArchiveRequiredFields = new Set([
  'project_code',
  'project_name',
  'archive_category', 'machine_model', 'quantity', 'quantity_unit', 'manager_id', 'product_line_id',
  'contract_signed_date',
  'contract_ship_date',
])

function archiveFieldPolicy(fieldKey: string) {
  return effectiveArchiveFieldMap.value.get(fieldKey)
}

function archiveFieldVisible(fieldKey: string) {
  if (fieldKey === 'product_category') return false
  const field = archiveFieldPolicy(fieldKey)
  return field?.visible !== false
}

function archiveFieldEditable(fieldKey: string) {
  if (['product_category', 'customer_full_name'].includes(fieldKey)) return false
  return archiveFieldPolicy(fieldKey)?.editable !== false
}

function archiveFieldRequired(fieldKey: string, createdAt?: string, values: Record<string, any> = form) {
  const field = archiveFieldPolicy(fieldKey)
  if (field) return governanceFieldRequired(field, { ...values, created_at: createdAt,
    governance_legacy: selectedArchive.value?.governance_legacy }, !createdAt, selectedArchive.value || undefined)
  return legacyArchiveRequiredFields.has(fieldKey)
}

function archiveColumnListAvailable(columnKey: string) {
  if (columnKey === 'product_category') return false
  const field = archiveFieldPolicy(archiveColumnPolicyKey[columnKey] || columnKey)
  return field ? field.visible && field.list_available : true
}

const archiveColumnGroups = computed(() => ARCHIVE_COLUMN_GROUP_DEFINITIONS.map(group => ({
  ...group,
  fields: group.fields.filter(field => archiveColumnListAvailable(field.key)),
})).filter(group => group.fields.length > 0))
const defaultArchiveColumnKeys = computed(() => baseArchiveColumnKeys.filter(key => !archiveExpansionKeys.has(key)).filter(archiveColumnListAvailable))
const availableArchiveColumnKeys = computed(() => new Set(baseArchiveColumnKeys.filter(archiveColumnListAvailable)))
const fixedArchiveColumnKeys = new Set(['archive_selection', 'archive_actions'])
const selectedArchiveColumnKeys = ref<string[]>([...defaultArchiveColumnKeys.value])
const archiveColumnPreferenceOwnerId = ref<number | null>(null)
const archiveColumnPreferencesReady = ref(false)
const archiveColumnPreferenceWritesEnabled = ref(false)
const archiveColumnStateRestored = ref(false)
const restoringArchiveColumnState = ref(false)
let gridApi: any = null

function onGridReady(params: any) {
  gridApi = params.api
  completeArchiveColumnPreferenceRestore()
  scheduleArchiveScrollbarMetrics()
}

function archiveColumnPreferenceStorageKey() {
  if (archiveColumnPreferenceOwnerId.value == null) return null
  return `${ARCHIVE_COLUMN_STORAGE_KEY}:${archiveColumnPreferenceOwnerId.value}`
}

async function resolveArchiveColumnPreferenceOwner() {
  if (!authStore.user) {
    try {
      await authStore.fetchUser()
    } catch {
      return
    }
  }
  archiveColumnPreferenceOwnerId.value = authStore.user?.id ?? null
}

function normalizeArchiveColumnKeys(keys: unknown) {
  if (!Array.isArray(keys)) return [...defaultArchiveColumnKeys.value]
  return keys.filter((key): key is string => typeof key === 'string' && availableArchiveColumnKeys.value.has(key))
}

function readArchiveColumnPreferences(): ArchiveColumnPreferenceState | null {
  const storageKey = archiveColumnPreferenceStorageKey()
  if (!storageKey) return null

  const raw = localStorage.getItem(storageKey)
  if (raw) {
    try {
      const parsed = JSON.parse(raw)
      return {
        selected_column_keys: normalizeArchiveColumnKeys(parsed?.selected_column_keys),
        columnState: Array.isArray(parsed?.columnState) ? parsed.columnState : [],
      }
    } catch { /* 忽略损坏的当前版本缓存 */ }
  }

  const legacyRaw = localStorage.getItem(LEGACY_ARCHIVE_LAYOUT_KEY)
  if (!legacyRaw) return null
  try {
    const legacyState = JSON.parse(legacyRaw)
    if (!Array.isArray(legacyState)) return null
    const visibleKeys = defaultArchiveColumnKeys.value.filter((key) => {
      const state = legacyState.find((item: ColumnState) => item.colId === key)
      return state?.hide !== true
    })
    return { selected_column_keys: visibleKeys, columnState: legacyState }
  } catch {
    return null
  }
}

function persistArchiveColumnPreferences() {
  if (!archiveColumnPreferencesReady.value || !archiveColumnPreferenceWritesEnabled.value) return
  const storageKey = archiveColumnPreferenceStorageKey()
  if (!storageKey) return
  const state: ArchiveColumnPreferenceState = {
    selected_column_keys: [...selectedArchiveColumnKeys.value],
    columnState: gridApi?.getColumnState?.() || [],
  }
  localStorage.setItem(storageKey, JSON.stringify(state))
  localStorage.removeItem(LEGACY_ARCHIVE_LAYOUT_KEY)
}

function restoreSelectedArchiveColumnKeys() {
  const saved = readArchiveColumnPreferences()
  selectedArchiveColumnKeys.value = saved
    ? normalizeArchiveColumnKeys(saved.selected_column_keys)
    : [...defaultArchiveColumnKeys.value]
}

function restoreArchiveColumnState() {
  if (!archiveColumnPreferencesReady.value || !gridApi || archiveColumnStateRestored.value) return
  archiveColumnStateRestored.value = true
  const saved = readArchiveColumnPreferences()
  if (!saved?.columnState.length) return
  restoringArchiveColumnState.value = true
  try {
    const selectedKeys = new Set(selectedArchiveColumnKeys.value)
    const reconciledState = saved.columnState.map((state) => {
      if (fixedArchiveColumnKeys.has(state.colId)) {
        return {
          ...state,
          hide: false,
          pinned: state.colId === 'archive_actions' ? 'right' : 'left',
          ...(state.colId === 'archive_actions' ? { width: PMS_ACTION_COLUMN.width, flex: null } : {}),
        }
      }
      if (state.colId === 'project_code' || state.colId === 'project_name') {
        return { ...state, hide: !archiveColumnListAvailable(state.colId) || state.hide === true }
      }
      if (availableArchiveColumnKeys.value.has(state.colId)) return { ...state, hide: !selectedKeys.has(state.colId) }
      if (state.colId && baseArchiveColumnKeys.includes(state.colId)) return null
      return state
    }).filter((state): state is ColumnState => Boolean(state))
    gridApi.applyColumnState({ state: reconciledState, applyOrder: true })
  } finally {
    restoringArchiveColumnState.value = false
  }
  scheduleArchiveScrollbarMetrics()
}

let archiveInitialSortApplied = false
function completeArchiveColumnPreferenceRestore() {
  if (!archiveColumnPreferencesReady.value || !gridApi) return
  restoreArchiveColumnState()
  if (!archiveInitialSortApplied) {
    archiveInitialSortApplied = true
    gridApi.applyColumnState({
      state: [{ colId: 'project_code', sort: 'desc', sortIndex: 0 }],
      defaultState: { sort: null, sortIndex: null },
    })
  }
  archiveColumnPreferenceWritesEnabled.value = true
}

function handleArchiveColumnSelection(keys: string[]) {
  selectedArchiveColumnKeys.value = normalizeArchiveColumnKeys(keys)
  nextTick(() => {
    scheduleArchiveScrollbarMetrics()
    persistArchiveColumnPreferences()
  })
}

function handleArchiveGridStructureChanged() {
  scheduleArchiveScrollbarMetrics()
  if (!archiveColumnPreferenceWritesEnabled.value || restoringArchiveColumnState.value) return
  persistArchiveColumnPreferences()
}

function handleArchiveColumnResized(event: any) {
  scheduleArchiveScrollbarMetrics()
  if (!event?.finished || !archiveColumnPreferenceWritesEnabled.value || restoringArchiveColumnState.value) return
  persistArchiveColumnPreferences()
}

function restoreArchiveColumnDefaults() {
  const storageKey = archiveColumnPreferenceStorageKey()
  if (storageKey) localStorage.removeItem(storageKey)
  localStorage.removeItem(LEGACY_ARCHIVE_LAYOUT_KEY)
  selectedArchiveColumnKeys.value = [...defaultArchiveColumnKeys.value]
  nextTick(() => {
    gridApi?.resetColumnState?.()
    gridApi?.applyColumnState?.({
      state: [
        { colId: 'archive_selection', hide: false, pinned: 'left' },
        { colId: 'archive_actions', hide: false, pinned: 'right' },
      ],
    })
    scheduleArchiveScrollbarMetrics()
    persistArchiveColumnPreferences()
  })
}

// ========== 数据状态 ==========
const rowData = ref<any[]>([])
const userList = ref<any[]>([])
const total = ref(0)
const selectedRows = ref<any[]>([])
const agGridRef = ref()
const archiveListRef = ref<InstanceType<typeof PmsDataList>>()
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)

// 字典选项
const dictOptions = reactive<Record<string, any[]>>({
  product_category: [],
  equipment_series: [],
})
const dictLabelMaps = reactive<Record<string, Record<string, string>>>({})

function enumLabel(code: string, value: unknown) {
  if (code === 'product_line') return productLines.label(value)
  if (value === null || value === undefined || value === '') return '-'
  const labelMap = dictLabelMaps[code]
  if (!labelMap) return '-'
  return labelMap[String(value)] || String(value)
}


async function fetchEffectiveArchiveFields() {
  try {
    const response: any = await request.get('/projects/archives/fields')
    effectiveArchiveFields.value = Array.isArray(response?.items) ? response.items : []
  } catch {
    effectiveArchiveFields.value = []
  }
}

const filteredProductCategoryOptions = computed(() => dictOptions.product_category || [])

const archiveCategoryFilterOptions = computed<PmsOption[]>(() =>
  Object.entries(dictLabelMaps.archive_category || {}).map(([value, label]) => ({
    value: Number(value),
    label: String(label),
  })),
)

const archiveProductCategoryOptions = computed<PmsOption[]>(() => filteredProductCategoryOptions.value.map(item => ({
  value: Number(item.value),
  label: String(item.label),
  disabled: Boolean(item.disabled),
})))

const archiveEquipmentSeriesOptions = computed<PmsOption[]>(() => (dictOptions.equipment_series || []).map(item => ({
  value: Number(item.value),
  label: String(item.label),
  disabled: Boolean(item.disabled),
})))

const archiveUserOptions = computed<PmsOption[]>(() => userList.value.map(user => ({
  value: Number(user.id),
  label: String(user.real_name || user.username || user.id),
})))

const archiveRegions = ref<ArchiveRegion[]>([])
async function fetchArchiveRegions() {
  archiveRegions.value = await getArchiveRegions()
  agGridRef.value?.api?.refreshCells({ columns: ['address_province', 'address_city'], force: true })
}

function archiveRegionLabel(fieldKey: string, value: unknown) {
  const options = fieldKey === 'address_province'
    ? archiveRegions.value : archiveRegions.value.flatMap(region => region.children)
  return options.find(option => option.value === value)?.label || '-'
}

function archiveDrawerSelectOptions(fieldKey: string, values = archiveDrawerForm): PmsOption[] {
  if (offlineEnumCodes[fieldKey]) return (dictOptions[offlineEnumCodes[fieldKey]!] || []).map(option => ({ ...option, value: Number(option.value) }))
  if (fieldKey === 'product_line_id') return productLines.options.value
  if (fieldKey === 'address_province') return archiveRegions.value
  if (fieldKey === 'address_city') return archiveRegions.value.find(region => region.value === values.address_province)?.children || []
  if (fieldKey === 'product_category') return archiveProductCategoryOptions.value
  if (fieldKey === 'manager_id') return archiveUserOptions.value
  if (fieldKey === 'equipment_series') return archiveEquipmentSeriesOptions.value
  return []
}

function archiveDrawerSelectPlaceholder(fieldKey: string) {
  return `选择${archiveDrawerFieldByKey(fieldKey)?.label || ''}`
}

function changeArchiveProvince(values: Record<string, any>) {
  values.address_city = ''
  values.address_detail = ''
}

function changeArchiveCreateSelect(fieldKey: string) {
  clearArchiveServerError(archiveCreateServerErrors, fieldKey)
  if (fieldKey === 'address_province') changeArchiveProvince(form)
  if (fieldKey === 'address_city') form.address_detail = ''
}

function changeArchiveDrawerSelect(fieldKey: string) {
  if (fieldKey === 'address_province') {
    changeArchiveProvince(archiveDrawerForm)
    return
  }
  if (fieldKey === 'address_city') {
    archiveDrawerForm.address_detail = ''
    return
  }
  commitArchiveFieldEdit()
}

function archiveAddressFieldVisible(fieldKey: string, values: Record<string, any>) {
  if (fieldKey === 'address_detail' && values.address_detail) return true
  if (fieldKey === 'address_city') return Boolean(values.address_province)
  if (fieldKey === 'address_detail') return Boolean(values.address_province && values.address_city)
  return true
}

const erpSyncStatusOptions: ListFilterOption[] = [
  'queued', 'pending', 'review', 'historical', 'success', 'failed',
].map(value => ({ value, label: archiveSyncLabel(value) }))

function dictFilterOptions(code: string, numeric = false): ListFilterOption[] {
  return (dictOptions[code] || []).map(item => ({
    label: String(item.label),
    value: numeric ? Number(item.value) : item.value,
  }))
}

function uniqueValueOptions(values: Array<string | number | null | undefined>): ListFilterOption[] {
  const optionMap = new Map<string, ListFilterOption>()
  values.forEach(value => {
    if (value === null || value === undefined || value === '') return
    const label = String(value)
    if (!optionMap.has(label)) {
      optionMap.set(label, { label, value })
    }
  })
  return Array.from(optionMap.values())
}

const archivePersonFilterKeys = new Set(['manager_name','created_by_name','updated_by_name','erp_sync_by_name'])
function archiveConditionPersonNames(conditions: QueryCondition[]): string[] {
  return conditions.filter(c => archivePersonFilterKeys.has(c.field))
    .flatMap(c => Array.isArray(c.value) ? c.value : [c.value])
    .filter((v): v is string => typeof v === 'string' && Boolean(v.trim()) && v.length <= 256)
}
const archiveUserNameOptions = computed((): ListFilterOption[] => uniqueValueOptions([
  ...userList.value.map(user => user.real_name || user.username),
  // Historical names already selected remain valid when filtered off the page.
  ...archiveConditionPersonNames(customFilters.value),
  ...rowData.value.flatMap(row => [
    row.manager_name,
    row.created_by_name,
    row.updated_by_name,
    row.erp_sync_by_name,
  ]),
]))

const archiveQueryReference=archiveReference(params=>request.get('/projects/archives/list',{params}) as unknown as Promise<any>,productLines.label,()=>productLines.filterOptions.value)
const archiveFilterFields = computed<ListFilterField<any>[]>(() => ([
  { field:'is_enabled',policyKey:'is_enabled',label:'启用状态',type:'select',options:()=>[{value:1,label:'启用'},{value:0,label:'已禁用'}] },
  ...archiveExpansionFields.map(field => ({
    field: field.key, policyKey: field.key, label: field.label, type: field.value_type === 'long_text' ? 'text' : field.value_type,
    ...(offlineEnumCodes[field.key] ? { options: () => dictFilterOptions(offlineEnumCodes[field.key], true) } : {}),
    ...(field.key === 'product_line_id' ? { options: () => productLines.filterOptions.value } : {}),
    ...(field.key === 'address_province' ? { options: () => archiveRegions.value } : {}),
    ...(field.key === 'address_city' ? { options: () => archiveRegions.value.flatMap(region => region.children) } : {}),
  })),
  { field: 'project_code', policyKey: 'project_code', label: '项目编号', type: 'text', reference:archiveQueryReference },
  { field: 'project_name', policyKey: 'project_name', label: '项目名称', type: 'text', reference:archiveQueryReference },
  { field: 'customer', policyKey: 'customer', label: '客户', type: 'text' },
  { field: 'product_category', policyKey: 'product_category', label: '产品类别', type: 'select', options: () => filteredProductCategoryOptions.value.map(item => ({ ...item, value: Number(item.value) })) },
  { field: 'manager_name', policyKey: 'manager_id', label: '负责人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'equipment_series', policyKey: 'equipment_series', label: '设备系列', type: 'select', options: () => dictFilterOptions('equipment_series', true) },
  { field: 'serial_no', policyKey: 'serial_no', label: '序列号', type: 'text' },
  { field: 'created_by_name', policyKey: 'created_by_name', label: '创建人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'updated_by_name', policyKey: 'updated_by_name', label: '最后编辑人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'erp_sync_by_name', policyKey: 'erp_sync_by_name', label: '最后同步人', type: 'select', options: () => archiveUserNameOptions.value },
  {
    field: 'erp_sync_status',
    policyKey: 'erp_sync_status',
    label: '同步状态',
    type: 'select',
    options: () => erpSyncStatusOptions,
    getValue: row => row.erp_sync_status || '',
  },
] as Array<ListFilterField<any> & { policyKey: string }>).filter(field => field.policyKey !== 'product_category' && archiveFieldPolicy(field.policyKey)?.visible !== false))

const { customFilters } = useListFilters(archiveFilterFields)
const archiveWorkspaceReady = ref(false)
const archiveAppliedFilters = ref<QueryCondition[]>([])
const archiveHasQueried = ref(false)
const archiveColumnFilters = ref<ColumnFilter[]>([])
const archivePageColumns = usePageColumnFilter(rowData, () => archiveQueryFields.value, archiveColumnFilters, () => [page.value, pageSize.value], row => toQueryRecord(row, archiveFilterFields.value), () => archiveHasQueried.value && !archiveListLoading.value)
const visibleArchiveRows = archivePageColumns.visibleRows
const archiveColumnContext:ColumnQueryContext = {
  ...archivePageColumns.context,
  ready:()=>archiveHasQueried.value && !archiveListLoading.value,
  fields:()=>archiveQueryFields.value,
  filters:()=>archiveColumnFilters.value,
  sort:(field,direction)=>{gridApi?.applyColumnState({state:[{colId:field,sort:direction}],defaultState:{sort:null}});handleArchiveSortChanged()},
}
const archiveQueryFields = computed(() => archiveValidationFields(customFilters.value))
const archiveQueryDefaults = computed<QueryDefinition[]>(() => {
  const mainCategory = archiveCategoryFilterOptions.value.find(option => option.label === '主机')
  return [
    {field:'project_code',shown:true,operator:'contains',value:null,valueEnd:null},
    {field:'is_enabled',shown:true,operator:'equals',value:1,valueEnd:null},
    {field:'archive_category',shown:true,operator:'in',value:mainCategory?[mainCategory.value]:[],valueEnd:null},
  ].filter(d=>archiveQueryFields.value.some(f=>f.field===d.field)) as QueryDefinition[]
})
function archiveValidationFields(conditions: typeof customFilters.value) {
  const historicalNames = uniqueValueOptions(archiveConditionPersonNames(conditions))
  return [...toQueryFields(archiveFilterFields.value),
    {field:'product_category',label:'产品类别（历史）',type:'enum' as const,options:archiveProductCategoryOptions.value.map(o=>({value:Number(o.value),label:o.label}))},
  ].map(f => archivePersonFilterKeys.has(f.field)
    ? {...f, options:[...(f.options || []),...historicalNames]} : f)
}
function archivePlanSnapshot() {
  return cloneQuery({pageSize:pageSize.value,columns:{selected_column_keys:[...selectedArchiveColumnKeys.value],columnState:gridApi?.getColumnState()||[]}})
}

async function submitArchiveQuery(conditions:QueryCondition[], preferences:any) {
  archiveAppliedFilters.value = cloneQuery(conditions)
  archiveColumnFilters.value = []
  if (PAGE_SIZE_OPTIONS.includes(preferences.pageSize)) pageSize.value = preferences.pageSize
  if (preferences.columns?.selected_column_keys && preferences.columns?.columnState) {
    const writable = archiveColumnPreferenceWritesEnabled.value
    archiveColumnPreferenceWritesEnabled.value = false
    try {
      const key = archiveColumnPreferenceStorageKey()
      if (key) localStorage.setItem(key,JSON.stringify(preferences.columns))
      restoreSelectedArchiveColumnKeys(); archiveColumnStateRestored.value = false
      await nextTick(); restoreArchiveColumnState()
    } finally { archiveColumnPreferenceWritesEnabled.value = writable }
  }
  page.value = 1
  await fetchList()
}
function clearArchiveColumnFilters() {
  if (!archiveColumnFilters.value.length) return
  archivePageColumns.clear()
  agGridRef.value?.api?.refreshHeader()
  agGridRef.value?.api?.refreshCells({ force: true })
}
watch(archiveColumnFilters, () => nextTick(() => {
  agGridRef.value?.api?.refreshHeader()
  agGridRef.value?.api?.refreshCells({ force: true })
}), { deep: true })

async function fetchDictOptions(code: string) {
  try {
    const definition = await loadEnumOptions(code)
    dictOptions[code] = definition.items
    dictLabelMaps[code] = definition.label_map
    await nextTick()
    agGridRef.value?.api?.refreshCells({ columns: [code], force: true })
    if (code === 'product_line') agGridRef.value?.api?.refreshCells({ columns: ['product_line_id'], force: true })
  } catch { /* ignore */ }
}

function scheduleArchiveScrollbarMetrics() {
  archiveListRef.value?.refreshScrollbar()
}

// ========== 新增弹窗与编辑抽屉 ==========
const dialogVisible = ref(false)
const archiveCreateSaving = ref(false)
const archiveCreateSnapshot = ref('')
const formRef = ref<FormInstance>()
const form = reactive<Record<string, any>>({
  id: 0,
  project_code: '',
  project_name: '',
  customer: '',
  manager_id: null as number | null,
  equipment_series: null as number | null,
  product_category: null as number | null,
  serial_no: '',
  ...Object.fromEntries(archiveExpansionFields.map(field => [field.key, field.key === 'product_line_id' || field.value_type === 'number' || (field.value_type === 'select' && !field.key.startsWith('address_')) ? null : ''])),
})
const archiveCreateServerErrors = reactive<Record<string, string>>({})
const archiveDrawerServerErrors = reactive<Record<string, string>>({})
const selectedArchive = ref<any | null>(null)
const archiveView = ref<'archives' | 'changes'>('archives')
const archiveDrawerLifecycleConflict = ref(false)
const archiveDrawerReadOnly = computed(() => (
  selectedArchive.value?.is_enabled !== 1
  || archiveDrawerLifecycleConflict.value
  || selectedArchive.value?.can_edit !== true
))
const archiveDrawerFormRef = ref<FormInstance>()
const archiveDrawerForm = reactive<Record<string, any>>({})
const archiveOriginalValues = ref<Record<string, unknown>>({})
const archivePendingChanges = ref<Record<string, ArchivePendingChange>>({})
const archiveEditingField = ref<string | null>(null)
const archiveEditSnapshot = ref<Record<string, any>>({})
const archiveDrawerSaving = ref(false)
const archivePendingChangeCount = computed(() => {
  const changedKeys = new Set(Object.keys(archivePendingChanges.value))
  const activeFieldKey = archiveEditingField.value
  if (!activeFieldKey) return changedKeys.size
  const keys = activeFieldKey === 'address_province' ? [activeFieldKey, 'address_city', 'address_detail']
    : activeFieldKey === 'address_city' ? [activeFieldKey, 'address_detail'] : [activeFieldKey]
  for (const key of keys) {
    const activeField = archiveDrawerFieldByKey(key)
    if (!activeField) continue
    const activeValue = normalizeArchiveDrawerValue(activeField, archiveDrawerForm[key])
    if (sameArchiveDrawerValue(activeValue, archiveOriginalValues.value[key])) {
      changedKeys.delete(key)
    } else {
      changedKeys.add(key)
    }
  }
  return changedKeys.size
})
const archiveDrawerGroups = computed(() => archiveOrderedGroups.map(group => ({
  ...group,
  fields: group.fields.filter((field) => {
    if (field.key === 'erp_error_msg') return Boolean(selectedArchive.value?.erp_error_msg)
    return archiveFieldVisible(field.key) && governanceFieldVisible(field.key, archiveDrawerForm) && archiveAddressFieldVisible(field.key, archiveDrawerForm)
  }),
})).filter(group => group.fields.length > 0))

const archiveCreateGroups = computed(() => archiveOrderedGroups.map(group => ({
  ...group, fields: group.fields.filter(field => field.source_type === 'archive'
    && archiveFieldVisible(field.key) && governanceFieldVisible(field.key, form, true) && archiveAddressFieldVisible(field.key, form)),
})).filter(group => group.fields.length > 0))

const legacyArchiveRules: FormRules = {
  project_code: [{ required: true, message: '请输入项目编号' }],
  project_name: [{ required: true, message: '请输入项目名称' }],
  contract_signed_date: [{ required: true, message: '请选择合同签订日期' }],
  contract_ship_date: [{ required: true, message: '请选择合同出货日期' }],
}

function archiveAddressComplete(values: Record<string, any>) {
  const filled = ['address_province', 'address_city', 'address_detail'].map(key => String(values[key] ?? '').trim().length > 0)
  return filled.every(Boolean) || filled.every(value => !value)
}

function buildArchiveRules(values: Record<string, any>, createdAt?: string, historical = false): FormRules {
  const nextRules: FormRules = effectiveArchiveFields.value.length || historical ? {} : { ...legacyArchiveRules }
  effectiveArchiveFields.value
    .filter(field => field.visible && archiveFieldRequired(field.field_key, createdAt, values) && !(historical && !values[field.field_key] && !field.required_effective_at))
    .forEach((field) => {
      nextRules[field.field_key] = [{
        required: true,
        message: `${field.label.includes('日期') || field.label.includes('时间') ? '请选择' : '请填写'}${field.label}`,
        trigger: ['blur', 'change'],
      }]
    })
  for (const key of ['address_province', 'address_city', 'address_detail']) {
    if (!archiveFieldVisible(key) || !archiveFieldEditable(key)) continue
    const existing = nextRules[key]
    nextRules[key] = [...(Array.isArray(existing) ? existing : existing ? [existing] : []), {
      validator: (_rule, _value, callback) => callback((archiveAddressComplete(values) || (historical && ['address_province', 'address_city', 'address_detail'].every(key => (values[key] ?? '') === (selectedArchive.value?.[key] ?? '')))) ? undefined : new Error('请完整填写省份、城市和详细地址')),
      trigger: ['blur', 'change'],
    }]
  }
  return nextRules
}
const rules = computed<FormRules>(() => buildArchiveRules(form))
const archiveDrawerRules = computed<FormRules>(() => buildArchiveRules(archiveDrawerForm, selectedArchive.value?.created_at, selectedArchive.value?.data_origin === 'offline_initial'))

// ========== AG Grid 列定义 ==========
function escapeHtml(value: any) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function archiveIsEnabled(row: any) {
  return row?.is_enabled === 1
}

function archiveActionButton(label: string, className: string, action: () => void) {
  return h('button', {
    type: 'button',
    class: ['pms-table-action', className],
    onClick: (event: MouseEvent) => {
      event.stopPropagation()
      action()
    },
  }, label)
}

const ArchiveActionsRenderer = defineComponent({
  name: 'ArchiveActionsRenderer',
  props: {
    params: { type: Object, required: true },
  },
  setup(props) {
    return () => {
      const row = (props.params as any).data
      const actions = []
      const editable = archiveIsEnabled(row) && row.can_edit === true && hasPermission('project:archive:edit')
      actions.push(archiveActionButton(editable ? '编辑' : '查看', editable ? 'edit-btn' : 'view-btn', () => openArchiveDrawer(row)))
      return h('div', { class: 'archive-row-actions' }, actions)
    }
  },
})

function archiveColumnVisibility(key: string): Pick<ColDef, 'colId' | 'hide'> {
  return {
    colId: key,
    hide: !archiveColumnListAvailable(key) || !selectedArchiveColumnKeys.value.includes(key),
  }
}

const archiveBusinessColumnDefs = computed<ColDef[]>(() => [
  ...archiveExpansionFields.map(field => ({
    ...archiveColumnVisibility(field.key), field: field.key, headerName: field.label, width: 140, minWidth: 110,
    valueFormatter: (params: any) => offlineEnumCodes[field.key] ? enumLabel(offlineEnumCodes[field.key]!,params.value) : field.key === 'product_line_id' ? enumLabel('product_line', params.value)
      : ['address_province', 'address_city'].includes(field.key) ? archiveRegionLabel(field.key, params.value)
      : field.value_type === 'date' ? archiveDateValue(params.value) || '-' : params.value ?? '-',
  })),
  ...(hasPermission('project:archive:delete') || hasPermission('project:archive:toggle') || hasPermission('project:archive:assign-line')
    ? [{ colId: 'archive_selection', headerClass: 'archive-list-header-center', headerCheckboxSelection: true, checkboxSelection: true, width: 44, pinned: 'left', lockPosition: 'left', lockPinned: true, lockVisible: true, suppressMovable: true, filter: false, sortable: false, resizable: false } as ColDef]
    : []),
  { colId: 'project_code', field: 'project_code', headerName: '项目编号', width: 130, minWidth: 110, pinned: 'left', hide: !archiveColumnListAvailable('project_code') },
  {
    colId: 'project_name', field: 'project_name', headerName: '项目名称', width: 190, minWidth: 160,
    hide: !archiveColumnListAvailable('project_name'),
    valueFormatter: (params: any) => params.value || '待补全名称',
  },
  { ...archiveColumnVisibility('customer'), field: 'customer', headerName: '客户', width: 150, minWidth: 120 },
  {
    ...archiveColumnVisibility('product_category'), field: 'product_category', headerName: '产品类别', width: 110, minWidth: 100,
    valueFormatter: (params: any) => enumLabel('product_category', params.value),
  },
  {
    ...archiveColumnVisibility('is_enabled'), field: 'is_enabled', headerName: '启用状态', width: 92, minWidth: 88,
    cellRenderer: (params: any) => {
      return params.value === 1
        ? '<span class="pms-status pms-status-success"><span class="pms-status-dot"></span>启用</span>'
        : '<span class="pms-status pms-status-neutral"><span class="pms-status-dot"></span>已禁用</span>'
    },
  },
  { ...archiveColumnVisibility('manager_name'), field: 'manager_name', headerName: '负责人', width: 110, minWidth: 96 },
  {
    ...archiveColumnVisibility('equipment_series'), field: 'equipment_series', headerName: '设备系列', width: 110, minWidth: 96,
    valueFormatter: (params: any) => enumLabel('equipment_series', params.value),
  },
  { ...archiveColumnVisibility('serial_no'), field: 'serial_no', headerName: '序列号', width: 130, minWidth: 110 },
  { ...archiveColumnVisibility('created_by_name'), field: 'created_by_name', headerName: '创建人', width: 110, minWidth: 96 },
  {
    ...archiveColumnVisibility('data_origin'), field: 'data_origin', headerName: '档案来源', width: 122, minWidth: 112,
    valueFormatter: (params: any) => ({ kingdee_initial: '金蝶期初', offline_initial: '线下期初', pms: 'PMS新建' } as Record<string, string>)[params.value] || '-',
  },
  { ...archiveColumnVisibility('updated_by_name'), field: 'updated_by_name', headerName: '最后编辑人', width: 120, minWidth: 110 },
  {
    ...archiveColumnVisibility('updated_at'), field: 'updated_at', headerName: '最后编辑时间', width: 170, minWidth: 160,
    valueFormatter: (params: any) => params.value ? new Date(params.value).toLocaleString('zh-CN') : '-',
  },
  {
    ...archiveColumnVisibility('erp_sync_time'), field: 'erp_sync_time', headerName: '最后同步时间', width: 170, minWidth: 160,
    valueFormatter: (params: any) => {
      if (!params.value) return '-'
      const d = new Date(params.value)
      const pad = (n: number) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    },
  },
  { ...archiveColumnVisibility('erp_sync_by_name'), field: 'erp_sync_by_name', headerName: '最后同步人', width: 120, minWidth: 110 },
  {
    ...archiveColumnVisibility('erp_sync_status'), field: 'erp_sync_status', headerName: '同步', width: 100, minWidth: 96,
    cellRenderer: (params: any) => {
      const button = document.createElement('button')
      button.className = 'el-button el-button--primary el-button--small is-link'
      button.textContent = archiveSyncLabel(params.value)
      button.title = '查看同步日志'
      button.onclick = () => openSyncLog(params.data.id)
      return button
    },
  },
  {
    colId: 'archive_actions', headerName: '操作', ...PMS_ACTION_COLUMN, pinned: 'right', lockPosition: 'right', lockPinned: true, lockVisible: true, suppressMovable: true, filter: false, sortable: false,
    cellClass: 'pms-actions-cell', headerClass: 'pms-actions-header archive-list-header-center',
    cellRenderer: ArchiveActionsRenderer,
  },
])

const columnDefs = computed(() => decorateQueryColumns(archiveBusinessColumnDefs.value.map(column =>
  fixedArchiveColumnKeys.has(column.colId || '') ? column : { ...column, initialWidth: column.width, width: undefined },
),()=>archiveColumnContext) as ColDef[])

const defaultColDef = {
  sortable: true,
  resizable: true,
  filter: false,
  suppressSizeToFit: true,
  headerClass: 'archive-list-header-center',
  tooltipValueGetter: (params: any) => params.valueFormatted ?? params.value ?? '',
  // SQL owns ordering; AG Grid must not reorder just the current page.
  comparator: () => 0,
}

// ========== 数据加载 ==========
const archiveListLoading = ref(false)
const archiveListError = ref(false)
const archiveSort = ref<Array<{ colId: string; sort: string }>>([{ colId: 'project_code', sort: 'desc' }])
function archiveExportSnapshot(){return businessExportSnapshot(archiveAppliedFilters.value,[],gridApi,{enabled:'all'})}
let archiveListRequestSerial = 0
let archiveQueryReady = false
let archiveQueryTimer: ReturnType<typeof setTimeout> | undefined

async function fetchList() {
  const errors = validateConditions(archiveAppliedFilters.value,archiveValidationFields(archiveAppliedFilters.value))
  if (Object.keys(errors).length) { ElMessage.warning(Object.values(errors).join('；')); return }
  archivePageColumns.clear()
  clearTimeout(archiveQueryTimer)
  const requestSerial = ++archiveListRequestSerial
  archiveListLoading.value = true
  archiveListError.value = false
  agGridRef.value?.api?.deselectAll?.()
  selectedRows.value = []
  try {
    const res: any = await request.get('/projects/archives/list', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        enabled: 'all',
        filters: JSON.stringify([
          ...archiveAppliedFilters.value,
        ]),
        column_filters: '[]',
        sort: JSON.stringify(archiveSort.value),
      },
    })
    if (requestSerial !== archiveListRequestSerial) return
    total.value = res.total
    const lastPage = Math.max(1, Math.ceil(res.total / pageSize.value))
    if (page.value > lastPage) {
      page.value = lastPage
      return await fetchList()
    }
    rowData.value = res.items
    archiveHasQueried.value = true
    scheduleArchiveScrollbarMetrics()
  } catch {
    if (requestSerial !== archiveListRequestSerial) return
    rowData.value = []
    total.value = 0
    archiveListError.value = true
  } finally {
    if (requestSerial === archiveListRequestSerial) archiveListLoading.value = false
  }
}

function scheduleArchiveQuery() {
  if (!archiveQueryReady) return
  page.value = 1
  ++archiveListRequestSerial
  archiveListLoading.value = true
  agGridRef.value?.api?.deselectAll?.()
  selectedRows.value = []
  clearTimeout(archiveQueryTimer)
  archiveQueryTimer = setTimeout(fetchList, 200)
}

function handleArchiveSortChanged() {
  const sorts = ((gridApi?.getColumnState() || []) as ColumnState[])
    .filter(state => state.sort && !fixedArchiveColumnKeys.has(state.colId))
    .sort((a, b) => (a.sortIndex ?? 0) - (b.sortIndex ?? 0))
    .map(state => ({ colId: state.colId, sort: state.sort! }))
  if (JSON.stringify(sorts) === JSON.stringify(archiveSort.value)) return
  archiveSort.value = sorts
  persistArchiveColumnPreferences()
  scheduleArchiveQuery()
}

onUnmounted(() => { clearTimeout(archiveQueryTimer); ++archiveListRequestSerial })

async function fetchUsers() {
  userList.value = (await request.get('/users/options')) as any
}

// ========== 选择事件 ==========
function onSelectionChanged() {
  selectedRows.value = agGridRef.value?.api?.getSelectedRows?.() || []
}

const selectedRowsIncludeDisabled = computed(() => selectedRows.value.some(row => !archiveIsEnabled(row)))

function getArchiveRowClass(params: any) {
  return [archiveIsEnabled(params.data) ? '' : 'archive-row-disabled',
    selectedArchive.value?.id === params.data?.id ? 'pms-detail-row-active' : ''].filter(Boolean)
}

watch(() => selectedArchive.value?.id, () => {
  nextTick(() => agGridRef.value?.api?.redrawRows())
})

// ========== 新增与字段级抽屉编辑 ==========
const archiveCreateOpening = ref(false)
async function openCreateDialog() {
  if (!hasPermission('project:archive:add') || archiveCreateOpening.value) return
  archiveCreateOpening.value = true
  await productLines.load()
  archiveCreateOpening.value = false
  if (productLines.failed.value) {
    ElMessage.error('产品线读取失败，请重新点击新增档案重试')
    return
  }
  if (!productLines.options.value.length) {
    ElMessage.warning('没有可用的产品线权限，请联系管理员')
    return
  }
  formRef.value?.resetFields()
  clearArchiveServerErrors(archiveCreateServerErrors)
  Object.assign(form, {
    id: 0,
    project_code: '',
    project_name: '',
    customer: '',
    manager_id: authStore.user?.id ?? null,
    equipment_series: null,
    product_category: null,
    serial_no: '',
    ...Object.fromEntries(archiveExpansionFields.map(field => [field.key, field.key === 'product_line_id' || field.value_type === 'number' || (field.value_type === 'select' && !field.key.startsWith('address_')) ? null : ''])),
  })
  form.product_line_id = productLines.options.value.length === 1 ? productLines.options.value[0]!.value : null
  archiveCreateSnapshot.value = JSON.stringify(form)
  dialogVisible.value = true
}

async function beforeCloseArchiveCreate(done: () => void) {
  if (archiveCreateSaving.value) return
  if (JSON.stringify(form) !== archiveCreateSnapshot.value) {
    try {
      await ElMessageBox.confirm('新增档案有未保存的修改，确定放弃吗？', '未保存修改', { type: 'warning' })
    } catch { return }
  }
  done()
}

function buildArchiveCreatePayload() {
  const payload: Record<string, unknown> = {}
  const values: Record<string, unknown> = {
    project_code: form.project_code,
    project_name: form.project_name,
    customer: form.customer || null,
    manager_id: form.manager_id,
    equipment_series: form.equipment_series,
    product_category: form.product_category,
    serial_no: form.serial_no || null,
    ...Object.fromEntries(archiveExpansionFields.map(field => [field.key, normalizeOfflineValue(field.key, form[field.key])])),
  }
  Object.entries(values).forEach(([fieldKey, value]) => {
    if (!archiveFieldVisible(fieldKey) || !archiveFieldEditable(fieldKey)) return
    payload[fieldKey] = value
  })
  return payload
}

function archiveDateValue(value: unknown) {
  return value ? String(value).substring(0, 10) : ''
}

function archiveDrawerValues(row: any) {
  return {
    ...Object.fromEntries(archiveExpansionFields.map(field => [field.key,
      field.value_type === 'date' ? archiveDateValue(row[field.key]) : field.value_type === 'number' && row[field.key] != null ? Number(row[field.key]) : row[field.key] ?? (field.key === 'product_line_id' || field.value_type === 'number' || (field.value_type === 'select' && !field.key.startsWith('address_')) ? null : ''),
    ])),
    project_code: row.project_code || '',
    project_name: row.project_name || '',
    data_origin: row.data_origin || 'pms',
    customer: row.customer || '',
    manager_id: row.manager_id ?? null,
    equipment_series: row.equipment_series ?? null,
    product_category: row.product_category ?? null,
    serial_no: row.serial_no || '',
    erp_sync_policy: row.erp_sync_policy || 'auto',
    erp_sync_status: row.erp_sync_status || '',
    erp_sync_time: row.erp_sync_time || '',
    erp_sync_by_name: row.erp_sync_by_name || '',
    erp_error_msg: row.erp_error_msg || '',
    created_by_name: row.created_by_name || '',
    created_at: row.created_at || '',
    updated_by_name: row.updated_by_name || '',
    updated_at: row.updated_at || '',
  }
}

function resetArchiveDrawer(row: any) {
  clearArchiveServerErrors(archiveDrawerServerErrors)
  selectedArchive.value = { ...row }
  archiveDrawerLifecycleConflict.value = false
  const values = archiveDrawerValues(row)
  Object.keys(archiveDrawerForm).forEach(key => delete archiveDrawerForm[key])
  Object.assign(archiveDrawerForm, values)
  archiveOriginalValues.value = { ...values }
  archivePendingChanges.value = {}
  archiveEditingField.value = null
  nextTick(() => archiveDrawerFormRef.value?.clearValidate())
}

function reconcileSelectedArchiveLifecycle(row: any) {
  if (!selectedArchive.value || selectedArchive.value.id !== row.id) return
  selectedArchive.value = { ...selectedArchive.value, ...row }
}

async function confirmDiscardArchiveChanges() {
  commitArchiveFieldEdit()
  if (!archivePendingChangeCount.value) return true
  try {
    await ElMessageBox.confirm('当前档案有未保存的修改。', '未保存修改', {
      confirmButtonText: '放弃修改',
      cancelButtonText: '继续编辑',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}

const archiveDetailSwitch = createDetailSwitch<any>(async () => {
  if (archiveDrawerSaving.value) return false
  commitArchiveFieldEdit()
  if (!archivePendingChangeCount.value) return true
  const decision = await confirmDetailSwitch()
  if (decision === 'cancel') return false
  if (decision === 'save') {
    await saveArchiveDrawer()
    return !archivePendingChangeCount.value
  }
  return true
}, async row => { resetArchiveDrawer(row) })

function onArchiveRowClicked(event: any) {
  if (!selectedArchive.value || !event.data) return
  if ((event.event?.target as HTMLElement | null)?.closest('button, input, .ag-selection-checkbox')) return
  void openArchiveDrawer(event.data)
}

async function openArchiveDrawer(row: any) {
  if (selectedArchive.value?.id === row.id) {
    archiveDetailSwitch.invalidate()
    reconcileSelectedArchiveLifecycle(row)
    return
  }
  await archiveDetailSwitch.select(row)
}

async function closeArchiveDrawer() {
  if (archiveDrawerSaving.value) return
  if (!await confirmDiscardArchiveChanges()) return
  archiveDetailSwitch.invalidate()
  selectedArchive.value = null
  archivePendingChanges.value = {}
  archiveEditingField.value = null
  archiveDrawerLifecycleConflict.value = false
}

function archiveDrawerFieldRequired(field: ArchiveDrawerField) {
  if (selectedArchive.value?.data_origin === 'offline_initial' && !archiveDrawerForm[field.key] && !archiveFieldPolicy(field.key)?.required_effective_at) return false
  return archiveFieldRequired(field.key, selectedArchive.value?.created_at, archiveDrawerForm)
}

function archiveDrawerFieldEditable(field: ArchiveDrawerField) {
  if (field.key === 'project_code' && (selectedArchive.value?.erp_synced || selectedArchive.value?.data_origin === 'kingdee_initial')) return false
  return !archiveDrawerReadOnly.value
    && !archiveDrawerSaving.value
    && field.source_type === 'archive'
    && archiveFieldEditable(field.key)
    && hasPermission('project:archive:edit')
}

function archiveDrawerReadonlyReason(field: ArchiveDrawerField) {
  if (field.key === 'project_code' && (selectedArchive.value?.erp_synced || selectedArchive.value?.data_origin === 'kingdee_initial')) return '已同步或金蝶期初档案编号不可修改'
  if (archiveDrawerLifecycleConflict.value) return '档案状态已变化，当前草稿仅供查看'
  if (selectedArchive.value?.is_enabled !== 1) return '项目档案已禁用，仅供查看'
  if (field.source_type === 'system') return '系统维护字段，仅供查看'
  if (!hasPermission('project:archive:edit')) return '当前角色没有项目档案编辑权限'
  return '字段规则已设置为不可编辑'
}

function archiveDrawerFieldByKey(fieldKey: string) {
  return archiveOrderedGroups
    .flatMap(group => group.fields)
    .find(field => field.key === fieldKey)
}

function archiveDrawerCurrentValue(field: ArchiveDrawerField) {
  return archiveDrawerForm[field.key]
}

function archiveDrawerValueEmpty(field: ArchiveDrawerField) {
  const value = archiveDrawerCurrentValue(field)
  return value === null || value === undefined || value === ''
}

function formatArchiveDateTime(value: unknown) {
  if (!value) return '-'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatArchiveDrawerValue(field: ArchiveDrawerField) {
  const value = archiveDrawerCurrentValue(field)
  if (field.key === 'erp_sync_policy') return value === 'manual' ? '仅手动同步' : '自动同步'
  if (offlineEnumCodes[field.key]) return enumLabel(offlineEnumCodes[field.key]!, value)
  if (field.key === 'data_origin') {
    return ({ kingdee_initial: '金蝶期初', offline_initial: '线下期初', pms: 'PMS新建' } as Record<string, string>)[String(value)] || '-'
  }
  if (field.key === 'erp_sync_status') {
    return archiveSyncLabel(value)
  }
  if (archiveDrawerValueEmpty(field)) return archiveDrawerFieldEditable(field) ? '点击填写' : '-'
  if (field.key === 'product_line_id') return enumLabel('product_line', value)
  if (['address_province', 'address_city'].includes(field.key)) return archiveRegionLabel(field.key, value)
  if (field.key === 'product_category') return enumLabel('product_category', value)
  if (field.key === 'equipment_series') return enumLabel('equipment_series', value)
  if (field.key === 'manager_id') {
    const user = userList.value.find(item => Number(item.id) === Number(value))
    return user?.real_name || selectedArchive.value?.manager_name || String(value)
  }
  if (field.value_type === 'date') return archiveDateValue(value) || '-'
  if (field.value_type === 'datetime') return formatArchiveDateTime(value)
  return String(value)
}

function normalizeArchiveDrawerValue(field: ArchiveDrawerField, value: unknown) {
  if (field.key === 'quantity' || offlineEnumCodes[field.key]) return normalizeOfflineValue(field.key, value)
  if (field.key === 'manager_id') return value === '' || value == null ? null : Number(value)
  if (field.value_type === 'date') return value ? archiveDateValue(value) : null
  if (['product_category', 'equipment_series', 'product_line_id'].includes(field.key)) {
    return value === '' || value == null ? null : Number(value)
  }
  return value ?? ''
}

function sameArchiveDrawerValue(left: unknown, right: unknown) {
  return String(left ?? '') === String(right ?? '')
}

function startArchiveFieldEdit(field: ArchiveDrawerField) {
  if (archiveDrawerSaving.value) return
  if (archiveDrawerReadOnly.value) return
  if (!archiveDrawerFieldEditable(field)) return
  clearArchiveServerError(archiveDrawerServerErrors, field.key)
  if (archiveEditingField.value && archiveEditingField.value !== field.key) commitArchiveFieldEdit()
  if (archiveEditingField.value === field.key) return
  archiveEditSnapshot.value = { ...archiveDrawerForm }
  archiveEditingField.value = field.key
}

function cancelArchiveFieldEdit() {
  if (!archiveEditingField.value) return
  Object.assign(archiveDrawerForm, archiveEditSnapshot.value)
  archiveEditingField.value = null
}

function commitArchiveFieldEdit() {
  const fieldKey = archiveEditingField.value
  if (!fieldKey) return
  const keys = fieldKey === 'address_province' ? [fieldKey, 'address_city', 'address_detail']
    : fieldKey === 'address_city' ? [fieldKey, 'address_detail'] : [fieldKey]
  const nextChanges = { ...archivePendingChanges.value }
  for (const key of keys) {
    const field = archiveDrawerFieldByKey(key)
    if (!field) continue
    const value = normalizeArchiveDrawerValue(field, archiveDrawerForm[key])
    const originalValue = archiveOriginalValues.value[key]
    archiveDrawerForm[key] = value
    if (sameArchiveDrawerValue(value, originalValue)) {
      delete nextChanges[key]
    } else {
      nextChanges[key] = { value, originalValue }
    }
  }
  archivePendingChanges.value = nextChanges
  archiveEditingField.value = null
}

function buildArchiveDrawerPayload() {
  const payload: Record<string, unknown> = {}
  Object.entries(archivePendingChanges.value).forEach(([fieldKey, change]) => {
    const field = archiveDrawerFieldByKey(fieldKey)
    if (!field || !archiveDrawerFieldEditable(field)) return
    payload[fieldKey] = change.value
  })
  return payload
}

function updateArchiveCreateField(key: string, value: any) {
  form[key] = value
  changeArchiveCreateSelect(key)
}

function updateArchiveDetailField(key: string, value: any) {
  const field = archiveDrawerFieldByKey(key)
  if (!field || !archiveDrawerFieldEditable(field)) return
  archiveDrawerForm[key] = value
  clearArchiveServerError(archiveDrawerServerErrors, key)
  if (key === 'address_province') changeArchiveProvince(archiveDrawerForm)
  if (key === 'address_city') archiveDrawerForm.address_detail = ''
  const changes: Record<string, ArchivePendingChange> = {}
  for (const item of archiveOrderedGroups.flatMap(group => group.fields)) {
    if (!archiveDrawerFieldEditable(item)) continue
    const normalized = normalizeArchiveDrawerValue(item, archiveDrawerForm[item.key])
    if (!sameArchiveDrawerValue(normalized, archiveOriginalValues.value[item.key])) changes[item.key] = { value: normalized, originalValue: archiveOriginalValues.value[item.key] }
  }
  archivePendingChanges.value = changes
}

async function beforeCloseArchiveDetail(done: () => void) {
  await closeArchiveDrawer()
  if (!selectedArchive.value) done()
}

async function showArchiveChanges() {
  if (archiveDrawerSaving.value || !await confirmDiscardArchiveChanges()) return
  selectedArchive.value = null
  archiveView.value = 'changes'
}

const archiveChangeConfirmOpen = ref(false)
const archiveChangeSubmitting = ref(false)
const archiveChangeReason = ref('')
const archiveChangeReasonError = ref('')
const archiveChangePreview = ref<any>(null)
let archiveChangeResolve: ((success: boolean) => void) | undefined
let archiveChangeSubmissionId = ''
let archiveChangePayload: Record<string, unknown> = {}
let archiveChangeArchiveId = 0

function cancelArchiveChangeConfirmation() {
  if (archiveChangeSubmitting.value) return
  archiveChangeResolve?.(false)
  archiveChangeResolve = undefined
}

async function submitArchiveChangeRequest() {
  if (archiveChangeSubmitting.value) return
  if (!archiveChangeReason.value.trim()) { archiveChangeReasonError.value = '请填写变更原因'; return }
  archiveChangeSubmitting.value = true
  try {
    await request.post(`/projects/archive-changes/${archiveChangeArchiveId}/submit`, {
      updates: archiveChangePayload, expected_version: archiveChangePreview.value.expected_version,
      reason: archiveChangeReason.value.trim(), submission_id: archiveChangeSubmissionId,
    })
    archivePendingChanges.value = {}
    archiveEditingField.value = null
    archiveChangeResolve?.(true)
    archiveChangeResolve = undefined
    archiveChangeConfirmOpen.value = false
    await fetchList()
    const row = await fetchArchiveLifecycleSnapshot(archiveChangeArchiveId)
    if (row && selectedArchive.value?.id === archiveChangeArchiveId) resetArchiveDrawer(row)
    ElMessage.success('变更已提交审批，正式档案保持原值')
  } catch { /* The shared request handler reports the error; retain the draft and submission id. */ }
  finally { archiveChangeSubmitting.value = false }
}

function archivePolicyValidationFieldKeys(error: any): string[] {
  const detail = error?.response?.data?.detail
  if (!['FIELD_POLICY_VALIDATION_FAILED', 'FIELD_POLICY_INVALID'].includes(detail?.code)) return []
  if (!Array.isArray(detail?.fields)) return []
  return detail.fields
    .map((field: any) => String(field?.field_key || '').trim())
    .filter(Boolean)
}

function clearArchiveServerErrors(target: Record<string, string>) {
  Object.keys(target).forEach(key => delete target[key])
}

function clearArchiveServerError(target: Record<string, string>, fieldKey: string) {
  delete target[fieldKey]
}

function archiveUniqueConflict(error: any) {
  const detail = error?.response?.data?.detail
  if (!['ARCHIVE_UNIQUE_CONFLICT', 'ARCHIVE_FIELD_REQUIRED'].includes(detail?.code) || !detail?.field_key) return null
  return {
    field_key: String(detail.field_key),
    message: String(detail.message || '字段值已存在'),
  }
}

async function focusArchiveUniqueConflict(
  error: any,
  targetForm: typeof formRef | typeof archiveDrawerFormRef,
  targetErrors: Record<string, string>,
) {
  const conflict = archiveUniqueConflict(error)
  if (!conflict) return false
  targetErrors[conflict.field_key] = conflict.message
  await nextTick()
  targetForm.value?.scrollToField(conflict.field_key)
  return true
}

async function focusArchivePolicyValidation(error: any, targetForm = formRef) {
  const fieldKeys = archivePolicyValidationFieldKeys(error)
  if (!fieldKeys.length) return
  await fetchEffectiveArchiveFields()
  await nextTick()
  const visibleProps = fieldKeys.filter(fieldKey => archiveFieldVisible(fieldKey))
  if (!visibleProps.length) return
  await targetForm.value?.validateField(visibleProps).catch(() => false)
  targetForm.value?.scrollToField(visibleProps[0])
}

async function handleSubmit() {
  if (!hasPermission('project:archive:add') || archiveCreateSaving.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  archiveCreateSaving.value = true
  try {
    await request.post('/projects/archives', buildArchiveCreatePayload())
    ElMessage.success('已保存，后台将自动同步金蝶')
    dialogVisible.value = false
    fetchList()
  } catch (error) {
    if (await focusArchiveUniqueConflict(error, formRef, archiveCreateServerErrors)) return
    await focusArchivePolicyValidation(error)
  } finally {
    archiveCreateSaving.value = false
  }
}

const ARCHIVE_DRAWER_LIFECYCLE_CONFLICT_CODES = new Set([
  'ARCHIVE_DISABLED',
  'ARCHIVE_OPERATION_PENDING',
  'ARCHIVE_LIFECYCLE_CONFLICT',
])

function archiveLifecycleConflictDetail(error: any) {
  if (error?.response?.status !== 409) return null
  const detail = error?.response?.data?.detail
  const code = String(detail?.code || '')
  if (!ARCHIVE_DRAWER_LIFECYCLE_CONFLICT_CODES.has(code) && !code.startsWith('ARCHIVE_LIFECYCLE_')) return null
  return {
    code,
    message: String(detail?.message || '项目档案状态已变化，请刷新后重试'),
  }
}

async function fetchArchiveLifecycleSnapshot(archiveId: number) {
  const response: any = await request.get('/projects/archives/list', {
    params: { page: 1, page_size: 1, archive_id: archiveId, enabled: 'all' },
  })
  return (response.items || []).find((row: any) => row.id === archiveId) || null
}

async function reconcileArchiveDrawerLifecycleConflict(error: any, archiveId: number, actionLabel: string) {
  const conflict = archiveLifecycleConflictDetail(error)
  if (!conflict) return false

  archiveDrawerLifecycleConflict.value = true
  const draftNotice = archivePendingChangeCount.value
    ? '未保存草稿已保留，请关闭抽屉时明确决定是否放弃。'
    : '当前抽屉已转为只读。'
  ElMessage.warning(`${actionLabel}失败：${conflict.message}。${draftNotice}`)

  let refreshed: any | null = null
  try {
    refreshed = await fetchArchiveLifecycleSnapshot(archiveId)
  } catch { /* 统一请求层已提示快照刷新失败 */ }
  if (!refreshed && conflict.code === 'ARCHIVE_DISABLED' && selectedArchive.value?.id === archiveId) {
    refreshed = { ...selectedArchive.value, is_enabled: 0 }
  }
  if (refreshed) reconcileSelectedArchiveLifecycle(refreshed)
  try {
    await fetchList()
  } catch { /* 统一请求层已提示列表刷新失败 */ }
  return true
}

async function saveArchiveDrawer() {
  if (!selectedArchive.value || archiveDrawerReadOnly.value || archiveDrawerSaving.value || !hasPermission('project:archive:edit')) return
  commitArchiveFieldEdit()
  if (!archivePendingChangeCount.value) return

  const valid = await archiveDrawerFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const archiveId = selectedArchive.value.id
  const payload = buildArchiveDrawerPayload()
  archiveDrawerSaving.value = true
  let syncQueued = false
  try {
    if (Object.keys(payload).length) {
      if (selectedArchive.value.change_mode === 'approval') {
        archiveChangePreview.value = await request.post(`/projects/archive-changes/${archiveId}/preview`, { updates: payload, expected_version: selectedArchive.value.change_version })
        archiveChangePayload = payload
        archiveChangeArchiveId = archiveId
        archiveChangeSubmissionId = newSubmissionId()
        archiveChangeReason.value = ''
        archiveChangeReasonError.value = ''
        archiveChangeConfirmOpen.value = true
        archiveDrawerSaving.value = false
        return await new Promise<boolean>(resolve => { archiveChangeResolve = resolve })
      }
      const result: any = await request.put(`/projects/archives/${archiveId}`, { ...payload, expected_version: selectedArchive.value.change_version })
      syncQueued = result.sync_queued === true
    }
  } catch (error) {
    if (await focusArchiveUniqueConflict(error, archiveDrawerFormRef, archiveDrawerServerErrors)) {
      archiveDrawerSaving.value = false
      return
    }
    if (await reconcileArchiveDrawerLifecycleConflict(error, archiveId, '保存')) {
      archiveDrawerSaving.value = false
      return
    }
    await focusArchivePolicyValidation(error, archiveDrawerFormRef)
    archiveDrawerSaving.value = false
    return
  }

  archivePendingChanges.value = {}
  archiveEditingField.value = null

  let refreshSucceeded = true
  try {
    await fetchList()
    if (archiveListError.value) throw new Error('List refresh failed')
    const refreshed = await fetchArchiveLifecycleSnapshot(archiveId)
    if (refreshed && selectedArchive.value?.id === archiveId) resetArchiveDrawer(refreshed)
  } catch {
    refreshSucceeded = false
    ElMessage.warning('档案已保存，但列表刷新失败，请手动刷新页面')
  } finally {
    archiveDrawerSaving.value = false
  }

  if (!refreshSucceeded) return
  ElMessage.success(syncQueued ? '已保存，后台将自动同步金蝶' : '已保存')
}

async function refreshArchiveListAfterConflict(error: any) {
  if (error?.response?.status !== 409) return
  await fetchList().catch(() => undefined)
}

function resetArchiveSelection() {
  agGridRef.value?.api?.deselectAll?.()
  selectedRows.value = []
}

async function releaseArchiveDrawerForLifecycle(archiveIds: number[]) {
  if (!selectedArchive.value || !archiveIds.includes(selectedArchive.value.id)) return true
  if (!await confirmDiscardArchiveChanges()) return false
  selectedArchive.value = null
  archivePendingChanges.value = {}
  archiveEditingField.value = null
  archiveDrawerLifecycleConflict.value = false
  return true
}

// ========== 启用状态 ==========
async function handleArchiveEnabledChange(row: any, enabled: boolean) {
  if (!hasPermission('project:archive:toggle')) return
  const action = enabled ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确定${action}项目档案“${row.project_name}”吗？`, `${action}确认`, { type: 'warning' })
  } catch {
    return
  }
  if (!await releaseArchiveDrawerForLifecycle([row.id])) return
  try {
    const res: any = await request.put(`/projects/archives/${row.id}/enabled`, { enabled })
    ElMessage.success(res.msg || `${action}成功`)
    resetArchiveSelection()
    await fetchList()
  } catch (error) {
    await refreshArchiveListAfterConflict(error)
  }
}

async function handleBatchEnabledChange(enabled: boolean) {
  if (!hasPermission('project:archive:toggle') || selectedRows.value.length === 0) return
  const archiveIds = selectedRows.value.map(row => row.id)
  const action = enabled ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(`确定${action}选中的 ${archiveIds.length} 条档案吗？`, `批量${action}确认`, { type: 'warning' })
  } catch {
    return
  }
  if (!await releaseArchiveDrawerForLifecycle(archiveIds)) return
  try {
    const res: any = await request.put('/projects/archives/batch-enabled', {
      archive_ids: archiveIds,
      enabled,
    })
    ElMessage.success(`${res.msg || `批量${action}成功`}，处理 ${Number(res.count) || 0} 条`)
    resetArchiveSelection()
    await fetchList()
  } catch (error) {
    await refreshArchiveListAfterConflict(error)
  }
}

// ========== 删除 ==========
async function handleDeleteSingle(row: any) {
  if (!hasPermission('project:archive:delete')) return
  if (row.can_delete === false) return
  try {
    await ElMessageBox.confirm('确定删除该项目档案吗？', '提示', { type: 'warning' })
  } catch {
    return
  }
  if (!await releaseArchiveDrawerForLifecycle([row.id])) return
  try {
    await request.delete(`/projects/archives/${row.id}`)
    ElMessage.success('删除成功')
    resetArchiveSelection()
    await fetchList()
  } catch (error) {
    await refreshArchiveListAfterConflict(error)
  }
}

async function handleBatchDelete() {
  if (!hasPermission('project:archive:delete')) return
  if (selectedRows.value.length === 0) return
  const archiveIds = selectedRows.value.map(row => row.id)
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${archiveIds.length} 条档案吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  if (!await releaseArchiveDrawerForLifecycle(archiveIds)) return
  try {
    const res: any = await request.post('/projects/archives/batch-delete', {
      archive_ids: archiveIds,
    })
    ElMessage.success(`${res.msg || '批量删除成功'}，删除 ${Number(res.count) || 0} 条`)
    resetArchiveSelection()
    await fetchList()
  } catch (error) {
    await refreshArchiveListAfterConflict(error)
  }
}

onMounted(async () => {
  const usersReady = fetchUsers().catch(() => {
    userList.value = []
  })
  await Promise.allSettled([
    usersReady,
    fetchEffectiveArchiveFields(), productLines.load(),
    fetchDictOptions('equipment_series'),
    ...Object.values(offlineEnumCodes).map(code => fetchDictOptions(code)),
    fetchArchiveRegions(),
    resolveArchiveColumnPreferenceOwner(),
  ])
  restoreSelectedArchiveColumnKeys()
  archiveColumnPreferencesReady.value = true
  await nextTick()
  completeArchiveColumnPreferenceRestore()
  handleArchiveSortChanged()
  archiveQueryReady = true
  archiveWorkspaceReady.value = true
  scheduleArchiveScrollbarMetrics()
})
const archiveSyncPoll = setInterval(() => {
  if (!archiveQueryReady || archiveListLoading.value || archiveDrawerSaving.value || archiveEditingField.value || archivePendingChangeCount.value || selectedRows.value.length || syncLogVisible.value) return
  if (rowData.value.some(row => ['queued', 'pending'].includes(row.erp_sync_status))) void fetchList()
}, 15000)
onUnmounted(() => clearInterval(archiveSyncPoll))
</script>

<style scoped>
.archive-governance-route {
  padding: 6px 8px;
  margin: 0 0 8px;
  border-radius: 4px;
  background: var(--pms-info-soft);
  color: var(--pms-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.project-archive-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--pms-query-gap);
  height: 100%;
  min-height: 0;
}


.archive-list-shell,
.project-archive-page {
  min-width: 0;
  min-height: 0;
}

.project-archive-page {
  height: 100%;
  min-height: 0;
}

.archive-base-filter {
  flex: 0 0 auto;
}

.archive-base-filter--keyword { width: 180px; }
.archive-base-filter--enabled { width: 112px; }
.archive-base-filter--category { width: 112px; }
.archive-base-filter--archive-category { width: 160px; }

.archive-edit-drawer {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--pms-border-soft);
  border-radius: var(--pms-radius);
  background: var(--pms-surface);
  box-shadow: var(--pms-shadow-sm);
}

.archive-drawer-head {
  flex: 0 0 auto;
  padding: 10px 12px;
  border-bottom: 1px solid var(--pms-border-soft);
}

.archive-drawer-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.archive-drawer-identity {
  min-width: 0;
}

.archive-drawer-title-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.archive-drawer-title {
  color: var(--pms-text);
  font-size: 14px;
  font-weight: 750;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.archive-drawer-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;
  color: var(--pms-text-secondary);
  font-family: var(--pms-font-mono);
  font-size: 12px;
}

.archive-drawer-close {
  flex: 0 0 auto;
  margin-top: -3px;
}

.archive-sync-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 8px 16px; border-bottom: 1px solid var(--pms-border-soft); font-size: 12px; color: var(--pms-text-secondary); }

.archive-drawer-form {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.archive-drawer-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 12px 12px;
}

.archive-drawer-section + .archive-drawer-section {
  margin-top: 4px;
}

.archive-drawer-section-title {
  margin: 0;
  padding: 12px 0 7px;
  border-bottom: 1px solid var(--pms-border-soft);
  color: var(--pms-text);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.4;
}

.archive-drawer-form-item {
  min-width: 0;
  margin-bottom: 0;
}

.archive-drawer-form-item :deep(.el-form-item__content) {
  display: block;
  width: 100%;
  min-width: 0;
  line-height: inherit;
}

.archive-drawer-form-item :deep(.el-form-item__error) {
  position: static;
  padding: 3px 10px 5px 112px;
  font-size: 11px;
}

.archive-drawer-savebar {
  display: grid;
  flex: 0 0 auto;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--pms-border-soft);
  background: var(--pms-surface);
}

.archive-drawer-savebar :deep(.el-button + .el-button) {
  margin-left: 0;
}

.archive-drawer-save {
  min-width: 0;
}

:deep(.archive-row-disabled .ag-cell) {
  color: var(--pms-text-muted);
  background: var(--pms-surface-muted);
}

:deep(.archive-list-header-center .ag-header-cell-label) {
  justify-content: center;
}

@media (max-width: 1280px) {
  .project-archive-workbench.is-drawer-open {
    grid-template-columns: minmax(0, 1fr) 360px;
  }
}
</style>
