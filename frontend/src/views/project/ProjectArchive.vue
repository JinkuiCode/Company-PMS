<template>
  <section
    class="project-archive-workbench"
    :class="{ 'is-drawer-open': selectedArchive }"
  >
    <div class="archive-list-shell">
      <PmsDataList
        ref="archiveListRef"
        class="project-archive-page"
        scrollbar-label="项目档案表格横向滚动条"
      >
    <template #toolbar-left>
        <el-button v-if="hasPermission('project:archive:add')" type="primary" size="small" @click="openCreateDialog">
          <el-icon style="margin-right:4px;"><Plus /></el-icon>
          新增档案
        </el-button>
        <el-button v-if="hasPermission('project:archive:delete')" type="danger" size="small" plain :disabled="selectedRows.length === 0" @click="handleBatchDelete">
          <el-icon style="margin-right:4px;"><Delete /></el-icon>
          批量删除
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
        <el-button v-if="hasPermission('project:archive:toggle')" size="small" :disabled="selectedRows.length === 0" @click="handleBatchEnabledChange(true)">
          批量启用
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
        <el-button v-if="hasPermission('project:archive:toggle')" size="small" :disabled="selectedRows.length === 0" @click="handleBatchEnabledChange(false)">
          批量禁用
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
        <el-button v-if="hasPermission('project:archive:sync')" type="success" size="small" :disabled="selectedRows.length === 0 || selectedRowsIncludeDisabled" @click="handleBatchSync">
          <el-icon style="margin-right:4px;"><Connection /></el-icon>
          批量同步 ERP
          <span v-if="selectedRows.length" style="margin-left:4px;">({{ selectedRows.length }})</span>
        </el-button>
    </template>
    <template #toolbar-right>
        <span class="filter-count" v-if="filteredRowData.length !== rowData.length">
          已筛选 {{ filteredRowData.length }} / {{ total }} 条
        </span>
        <PmsListColumnPicker
          :model-value="selectedArchiveColumnKeys"
          :groups="archiveColumnGroups"
          :default-keys="defaultArchiveColumnKeys"
          aria-label="项目档案列设置"
          @update:model-value="handleArchiveColumnSelection"
          @restore-defaults="restoreArchiveColumnDefaults"
        />
    </template>

    <template #filters>
      <PmsListFilters
        v-model:filters="customFilters"
        :fields="archiveFilterFields"
        :active-count="activeCustomFilterCount"
      >
        <el-input
          v-if="archiveFieldVisible('project_code') || archiveFieldVisible('project_name')"
          v-model="searchKeyword"
          placeholder="搜索编号、名称、客户或序列号"
          size="small"
          clearable
          style="width: 200px;"
          :prefix-icon="Search"
        />
        <el-select
          v-model="archiveQuery.enabled"
          aria-label="启用状态"
          size="small"
          style="width: 112px;"
          @change="handleArchiveEnabledFilterChange"
        >
          <el-option
            v-for="item in archiveEnabledFilterOptions"
            :key="String(item.value)"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select
          v-if="archiveFieldVisible('product_category')"
          v-model="filterProductCategory"
          placeholder="全部产品类别"
          size="small"
          clearable
          style="width: 140px;"
        >
          <el-option v-for="item in filteredProductCategoryOptions" :key="item.value" :label="item.label" :value="Number(item.value)" />
        </el-select>
      </PmsListFilters>
    </template>

    <template #grid>
      <ag-grid-vue
        ref="agGridRef"
        class="ag-theme-alpine wechat-table pms-ag-grid"
        :style="archiveGridStyle"
        :rowData="filteredRowData"
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

        <!-- 新增档案保持集中录入，编辑使用右侧字段级抽屉。 -->
        <el-dialog v-model="dialogVisible" title="新增项目档案" width="560px">
          <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
            <el-form-item v-if="archiveFieldVisible('project_code')" label="项目编号" prop="project_code" :error="archiveCreateServerErrors.project_code">
              <el-input v-model="form.project_code" placeholder="请输入项目编号" :disabled="!archiveFieldEditable('project_code')" @input="clearArchiveServerError(archiveCreateServerErrors, 'project_code')" />
            </el-form-item>
            <el-form-item v-if="archiveFieldVisible('project_name')" label="项目名称" prop="project_name" :error="archiveCreateServerErrors.project_name">
              <el-input v-model="form.project_name" placeholder="请输入项目名称" :disabled="!archiveFieldEditable('project_name')" @input="clearArchiveServerError(archiveCreateServerErrors, 'project_name')" />
            </el-form-item>
            <el-form-item v-if="archiveFieldVisible('customer')" label="客户" prop="customer">
              <el-input v-model="form.customer" placeholder="请输入客户名称" :disabled="!archiveFieldEditable('customer')" />
            </el-form-item>
            <el-form-item v-if="archiveFieldVisible('product_category')" label="产品类别" prop="product_category">
              <el-select v-model="form.product_category" placeholder="请选择产品类别" style="width: 100%;" :disabled="!archiveFieldEditable('product_category')">
                <el-option v-for="item in filteredProductCategoryOptions" :key="item.value" :label="item.label" :value="Number(item.value)" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="archiveFieldVisible('manager_id')" label="负责人" prop="manager_id">
              <el-select v-model="form.manager_id" placeholder="请选择负责人" clearable style="width: 100%;" :disabled="!archiveFieldEditable('manager_id')">
                <el-option
                  v-for="u in userList"
                  :key="u.id"
                  :label="u.real_name"
                  :value="u.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="archiveFieldVisible('equipment_series')" label="设备系列" prop="equipment_series">
              <el-select v-model="form.equipment_series" placeholder="请选择设备系列" clearable style="width: 100%;" :disabled="!archiveFieldEditable('equipment_series')">
                <el-option v-for="item in dictOptions.equipment_series" :key="item.value" :label="item.label" :value="Number(item.value)" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="archiveFieldVisible('serial_no')" label="序列号" prop="serial_no" :error="archiveCreateServerErrors.serial_no">
              <el-input v-model="form.serial_no" placeholder="请输入序列号" :disabled="!archiveFieldEditable('serial_no')" @input="clearArchiveServerError(archiveCreateServerErrors, 'serial_no')" />
            </el-form-item>
            <el-row :gutter="12">
              <el-col v-if="archiveFieldVisible('plan_start_date')" :span="12">
                <el-form-item label="计划开始" prop="plan_start_date">
                  <el-date-picker v-model="form.plan_start_date" type="date" style="width: 100%;" value-format="YYYY-MM-DD" placeholder="选择日期" :disabled="!archiveFieldEditable('plan_start_date')" />
                </el-form-item>
              </el-col>
              <el-col v-if="archiveFieldVisible('plan_end_date')" :span="12">
                <el-form-item label="计划结束" prop="plan_end_date">
                  <el-date-picker v-model="form.plan_end_date" type="date" style="width: 100%;" value-format="YYYY-MM-DD" placeholder="选择日期" :disabled="!archiveFieldEditable('plan_end_date')" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
          <template #footer>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button v-if="hasPermission('project:archive:add')" type="primary" @click="handleSubmit">保存</el-button>
          </template>
        </el-dialog>
      </PmsDataList>
    </div>

    <aside
      v-if="selectedArchive"
      class="archive-edit-drawer"
      :aria-label="archiveDrawerReadOnly ? '项目档案查看' : '项目档案编辑'"
    >
      <header class="archive-drawer-head">
        <div class="archive-drawer-title-row">
          <div class="archive-drawer-identity">
            <div class="archive-drawer-title-line">
              <div class="archive-drawer-title">{{ selectedArchive.project_name || '-' }}</div>
              <span v-if="archiveDrawerReadOnly" class="pms-status pms-status-neutral">
                <span class="pms-status-dot"></span>已禁用
              </span>
            </div>
            <div class="archive-drawer-meta">
              <span>{{ selectedArchive.project_code || '-' }}</span>
              <span>·</span>
              <span>{{ enumLabel('product_category', selectedArchive.product_category) }}</span>
            </div>
          </div>
          <el-tooltip content="关闭档案编辑" placement="left">
            <el-button
              class="archive-drawer-close"
              :icon="Close"
              text
              circle
              aria-label="关闭档案编辑"
              @click="closeArchiveDrawer"
            />
          </el-tooltip>
        </div>
      </header>

      <el-form
        ref="archiveDrawerFormRef"
        :model="archiveDrawerForm"
        :rules="rules"
        class="archive-drawer-form"
        label-position="top"
        @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
      >
        <div class="archive-drawer-body">
          <section
            v-for="group in archiveDrawerGroups"
            :key="group.key"
            class="archive-drawer-section"
          >
            <h3 class="archive-drawer-section-title">{{ group.label }}</h3>
            <div class="archive-drawer-field-list">
              <div
                v-for="field in group.fields"
                :key="field.key"
                class="archive-drawer-field-row"
                :class="{
                  editing: archiveEditingField === field.key,
                  'is-long-text': field.value_type === 'long_text',
                }"
              >
                <div class="archive-drawer-field-label">
                  <span>{{ field.label }}</span>
                  <span v-if="archiveDrawerFieldRequired(field)" class="archive-required-mark" aria-label="必填">*</span>
                  <el-tooltip
                    v-if="!archiveDrawerFieldEditable(field)"
                    :content="archiveDrawerReadonlyReason(field)"
                    placement="top"
                  >
                    <el-icon class="archive-field-lock" aria-hidden="true"><Lock /></el-icon>
                  </el-tooltip>
                </div>

                <el-form-item :prop="field.key" :error="archiveDrawerServerErrors[field.key]" class="archive-drawer-form-item">
                  <template v-if="archiveEditingField === field.key">
                    <div
                      class="archive-drawer-field-editor"
                      @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
                    >
                      <el-select
                        v-if="field.key === 'product_category'"
                        v-model="archiveDrawerForm[field.key]"
                        size="small"
                        filterable
                        placeholder="选择产品类别"
                        style="width: 100%;"
                        @change="commitArchiveFieldEdit"
                        @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
                      >
                        <el-option v-for="item in filteredProductCategoryOptions" :key="item.value" :label="item.label" :value="Number(item.value)" />
                      </el-select>
                      <el-select
                        v-else-if="field.key === 'manager_id'"
                        v-model="archiveDrawerForm[field.key]"
                        size="small"
                        filterable
                        clearable
                        placeholder="选择负责人"
                        style="width: 100%;"
                        @change="commitArchiveFieldEdit"
                        @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
                      >
                        <el-option v-for="user in userList" :key="user.id" :label="user.real_name" :value="user.id" />
                      </el-select>
                      <el-select
                        v-else-if="field.key === 'equipment_series'"
                        v-model="archiveDrawerForm[field.key]"
                        size="small"
                        filterable
                        clearable
                        placeholder="选择设备系列"
                        style="width: 100%;"
                        @change="commitArchiveFieldEdit"
                        @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
                      >
                        <el-option v-for="item in dictOptions.equipment_series" :key="item.value" :label="item.label" :value="Number(item.value)" />
                      </el-select>
                      <el-date-picker
                        v-else-if="field.value_type === 'date'"
                        v-model="archiveDrawerForm[field.key]"
                        type="date"
                        size="small"
                        value-format="YYYY-MM-DD"
                        placeholder="选择日期"
                        style="width: 100%;"
                        @change="commitArchiveFieldEdit"
                        @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
                      />
                      <el-input
                        v-else
                        v-model="archiveDrawerForm[field.key]"
                        size="small"
                        :placeholder="`输入${field.label}`"
                        @keydown.enter.exact.prevent="commitArchiveFieldEdit"
                        @keydown.esc.stop.prevent="cancelArchiveFieldEdit"
                      />
                    </div>
                  </template>

                  <button
                    v-else-if="archiveDrawerFieldEditable(field)"
                    type="button"
                    class="archive-drawer-field-value"
                    :class="{ 'is-empty': archiveDrawerValueEmpty(field) }"
                    :aria-label="`编辑${field.label}`"
                    @click="startArchiveFieldEdit(field)"
                  >
                    {{ formatArchiveDrawerValue(field) }}
                  </button>
                  <div
                    v-else
                    class="archive-drawer-field-static"
                    :class="{ 'is-empty': archiveDrawerValueEmpty(field) }"
                  >
                    {{ formatArchiveDrawerValue(field) }}
                  </div>
                </el-form-item>
              </div>
            </div>
          </section>
        </div>

        <div v-if="!archiveDrawerReadOnly" class="archive-drawer-savebar">
          <el-button
            class="archive-drawer-save"
            type="primary"
            size="small"
            :disabled="!archivePendingChangeCount"
            :loading="archiveDrawerSaving"
            @click="saveArchiveDrawer(false)"
          >
            保存修改{{ archivePendingChangeCount ? ` (${archivePendingChangeCount})` : '' }}
          </el-button>
          <el-button
            v-if="hasPermission('project:archive:sync')"
            class="archive-drawer-sync"
            type="success"
            size="small"
            plain
            :loading="archiveDrawerSaving"
            @click="saveArchiveDrawer(true)"
          >
            保存并同步 ERP
          </el-button>
        </div>
      </el-form>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Delete, Search, Connection, Close, Lock } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import { ModuleRegistry, AllCommunityModule, type ColDef, type ColumnState } from 'ag-grid-community'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import { type ListFilterField, type ListFilterOption, useListFilters } from '@/composables/useListFilters'
import { loadEnumOptions } from '@/composables/useEnumOptions'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { useAuthStore } from '@/stores/auth'

ModuleRegistry.registerModules([AllCommunityModule])
import request from '@/utils/request'

const localeText = chineseLocaleText
const authStore = useAuthStore()
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
  list_available: boolean
}

type ArchiveDrawerValueType = 'text' | 'select' | 'user' | 'date' | 'datetime' | 'long_text'

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
    ],
  },
  {
    key: 'plan',
    label: '计划信息',
    fields: [
      { key: 'plan_start_date', label: '计划开始', value_type: 'date', list_available: true, quick_addable: false },
      { key: 'plan_end_date', label: '计划结束', value_type: 'date', list_available: true, quick_addable: false },
    ],
  },
  {
    key: 'audit',
    label: '维护信息',
    fields: [
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
    ],
  },
  {
    key: 'plan',
    label: '计划信息',
    fields: [
      { key: 'plan_start_date', label: '计划开始', value_type: 'date', source_type: 'archive' },
      { key: 'plan_end_date', label: '计划结束', value_type: 'date', source_type: 'archive' },
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
      { key: 'created_by_name', label: '创建人', value_type: 'text', source_type: 'system' },
      { key: 'created_at', label: '创建时间', value_type: 'datetime', source_type: 'system' },
      { key: 'updated_by_name', label: '最后编辑人', value_type: 'text', source_type: 'system' },
      { key: 'updated_at', label: '最后编辑时间', value_type: 'datetime', source_type: 'system' },
    ],
  },
]

const archiveColumnPolicyKey: Record<string, string> = {
  manager_name: 'manager_id',
}
const baseArchiveColumnKeys = ARCHIVE_COLUMN_GROUP_DEFINITIONS.flatMap(group => group.fields.map(field => field.key))
const effectiveArchiveFields = ref<EffectiveArchiveField[]>([])
const effectiveArchiveFieldMap = computed(() => new Map(
  effectiveArchiveFields.value.map(field => [field.field_key, field]),
))

function archiveFieldPolicy(fieldKey: string) {
  return effectiveArchiveFieldMap.value.get(fieldKey)
}

function archiveFieldVisible(fieldKey: string) {
  const field = archiveFieldPolicy(fieldKey)
  return field?.visible !== false
}

function archiveFieldEditable(fieldKey: string) {
  return archiveFieldPolicy(fieldKey)?.editable !== false
}

function archiveColumnListAvailable(columnKey: string) {
  const field = archiveFieldPolicy(archiveColumnPolicyKey[columnKey] || columnKey)
  return field ? field.visible && field.list_available : true
}

const archiveColumnGroups = computed(() => ARCHIVE_COLUMN_GROUP_DEFINITIONS.map(group => ({
  ...group,
  fields: group.fields.filter(field => archiveColumnListAvailable(field.key)),
})).filter(group => group.fields.length > 0))
const defaultArchiveColumnKeys = computed(() => baseArchiveColumnKeys.filter(archiveColumnListAvailable))
const availableArchiveColumnKeys = computed(() => new Set(defaultArchiveColumnKeys.value))
const fixedArchiveColumnKeys = new Set(['archive_selection', 'archive_actions'])
const selectedArchiveColumnKeys = ref<string[]>([...baseArchiveColumnKeys])
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
        }
      }
      if (state.colId === 'project_code' || state.colId === 'project_name') {
        return { ...state, hide: !archiveColumnListAvailable(state.colId) }
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

function completeArchiveColumnPreferenceRestore() {
  if (!archiveColumnPreferencesReady.value || !gridApi) return
  restoreArchiveColumnState()
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
const searchKeyword = ref('')
const selectedRows = ref<any[]>([])
const agGridRef = ref()
const archiveListRef = ref<InstanceType<typeof PmsDataList>>()
const page = ref(1)
const pageSize = ref(15)
const filterProductCategory = ref<number | null>(null)
const archiveQuery = reactive({
  enabled: true as boolean | null,
})
const archiveEnabledFilterOptions = [
  { label: '启用', value: true },
  { label: '已禁用', value: false },
  { label: '全部', value: null },
]

// 字典选项
const dictOptions = reactive<Record<string, any[]>>({
  product_category: [],
  equipment_series: [],
})
const dictLabelMaps = reactive<Record<string, Record<string, string>>>({})

function enumLabel(code: string, value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  return dictLabelMaps[code]?.[String(value)] || String(value)
}

// 用户允许的产品类别
const allowedProductCategoryIds = ref<number[] | null>(null)

async function fetchAllowedProductCategories() {
  try {
    const res: any = await request.get('/auth/product-categories')
    if (res.unrestricted) {
      allowedProductCategoryIds.value = null // null = 不限制
    } else {
      allowedProductCategoryIds.value = (res.items || []).map(Number)
    }
  } catch { /* ignore */ }
}

async function fetchEffectiveArchiveFields() {
  try {
    const response: any = await request.get('/projects/archives/fields')
    effectiveArchiveFields.value = Array.isArray(response?.items) ? response.items : []
  } catch {
    effectiveArchiveFields.value = []
  }
}

// 筛选栏可用的产品类别选项（取字典与权限的交集）
const filteredProductCategoryOptions = computed(() => {
  const all = dictOptions.product_category || []
  if (allowedProductCategoryIds.value === null) return all
  return all.filter(item => allowedProductCategoryIds.value!.includes(Number(item.value)))
})

const erpSyncStatusOptions: ListFilterOption[] = [
  { label: '待同步', value: 'pending' },
  { label: '已同步', value: 'success' },
  { label: '失败', value: 'failed' },
]

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

const archiveUserNameOptions = computed(() => uniqueValueOptions([
  ...userList.value.map(user => user.real_name || user.username),
  ...rowData.value.flatMap(row => [
    row.manager_name,
    row.created_by_name,
    row.updated_by_name,
    row.erp_sync_by_name,
  ]),
]))

const archiveFilterFields = computed<ListFilterField<any>[]>(() => ([
  { field: 'project_code', policyKey: 'project_code', label: '项目编号', type: 'text' },
  { field: 'project_name', policyKey: 'project_name', label: '项目名称', type: 'text' },
  { field: 'customer', policyKey: 'customer', label: '客户', type: 'text' },
  { field: 'product_category', policyKey: 'product_category', label: '产品类别', type: 'select', options: () => filteredProductCategoryOptions.value.map(item => ({ ...item, value: Number(item.value) })) },
  { field: 'manager_name', policyKey: 'manager_id', label: '负责人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'equipment_series', policyKey: 'equipment_series', label: '设备系列', type: 'select', options: () => dictFilterOptions('equipment_series', true) },
  { field: 'serial_no', policyKey: 'serial_no', label: '序列号', type: 'text' },
  { field: 'plan_start_date', policyKey: 'plan_start_date', label: '计划开始', type: 'date' },
  { field: 'plan_end_date', policyKey: 'plan_end_date', label: '计划结束', type: 'date' },
  { field: 'created_by_name', policyKey: 'created_by_name', label: '创建人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'updated_by_name', policyKey: 'updated_by_name', label: '最后编辑人', type: 'select', options: () => archiveUserNameOptions.value },
  { field: 'erp_sync_by_name', policyKey: 'erp_sync_by_name', label: '最后同步人', type: 'select', options: () => archiveUserNameOptions.value },
  {
    field: 'erp_sync_status',
    policyKey: 'erp_sync_status',
    label: '同步状态',
    type: 'select',
    options: () => erpSyncStatusOptions,
    getValue: row => row.erp_sync_status || 'pending',
  },
] as Array<ListFilterField<any> & { policyKey: string }>).filter(field => archiveFieldPolicy(field.policyKey)?.visible !== false))

const { customFilters, activeCustomFilterCount, applyCustomFilters } = useListFilters(archiveFilterFields)

async function fetchDictOptions(code: string) {
  try {
    const definition = await loadEnumOptions(code)
    dictOptions[code] = definition.items
    dictLabelMaps[code] = definition.label_map
  } catch { /* ignore */ }
}

// 客户端筛选
const filteredRowData = computed(() => {
  let result = rowData.value
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(r =>
      String(r.project_code ?? '').toLowerCase().includes(kw) ||
      String(r.project_name ?? '').toLowerCase().includes(kw) ||
      String(r.customer ?? '').toLowerCase().includes(kw) ||
      String(r.serial_no ?? '').toLowerCase().includes(kw)
    )
  }
  if (filterProductCategory.value != null) {
    result = result.filter(r => Number(r.product_category) === filterProductCategory.value)
  }
  return applyCustomFilters(result)
})

const archiveGridStyle = computed(() => {
  const visibleRows = Math.max(filteredRowData.value.length, 1)
  const height = Math.min(430, Math.max(176, 74 + visibleRows * 38))
  return { width: '100%', height: `${height}px` }
})

function scheduleArchiveScrollbarMetrics() {
  archiveListRef.value?.refreshScrollbar()
}

// ========== 新增弹窗与编辑抽屉 ==========
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  id: 0,
  project_code: '',
  project_name: '',
  customer: '',
  manager_id: null as number | null,
  equipment_series: null as number | null,
  product_category: null as number | null,
  serial_no: '',
  plan_start_date: '',
  plan_end_date: '',
})
const archiveCreateServerErrors = reactive<Record<string, string>>({})
const archiveDrawerServerErrors = reactive<Record<string, string>>({})
const selectedArchive = ref<any | null>(null)
const archiveDrawerReadOnly = computed(() => selectedArchive.value?.is_enabled !== 1)
const archiveDrawerFormRef = ref<FormInstance>()
const archiveDrawerForm = reactive<Record<string, any>>({})
const archiveOriginalValues = ref<Record<string, unknown>>({})
const archivePendingChanges = ref<Record<string, ArchivePendingChange>>({})
const archiveEditingField = ref<string | null>(null)
const archiveDrawerSaving = ref(false)
const archivePendingChangeCount = computed(() => {
  const changedKeys = new Set(Object.keys(archivePendingChanges.value))
  const activeFieldKey = archiveEditingField.value
  if (!activeFieldKey) return changedKeys.size
  const activeField = archiveDrawerFieldByKey(activeFieldKey)
  if (!activeField) return changedKeys.size
  const activeValue = normalizeArchiveDrawerValue(activeField, archiveDrawerForm[activeFieldKey])
  if (sameArchiveDrawerValue(activeValue, archiveOriginalValues.value[activeFieldKey])) {
    changedKeys.delete(activeFieldKey)
  } else {
    changedKeys.add(activeFieldKey)
  }
  return changedKeys.size
})
const archiveDrawerGroups = computed(() => ARCHIVE_DRAWER_GROUP_DEFINITIONS.map(group => ({
  ...group,
  fields: group.fields.filter((field) => {
    if (field.key === 'erp_error_msg') return Boolean(selectedArchive.value?.erp_error_msg)
    return archiveFieldVisible(field.key)
  }),
})).filter(group => group.fields.length > 0))

const legacyArchiveRules: FormRules = {
  project_code: [{ required: true, message: '请输入项目编号' }],
  project_name: [{ required: true, message: '请输入项目名称' }],
  product_category: [{ required: true, message: '请选择产品类别' }],
  plan_start_date: [{ required: true, message: '请选择计划开始日期' }],
  plan_end_date: [{ required: true, message: '请选择计划结束日期' }],
}

const rules = computed<FormRules>(() => {
  if (!effectiveArchiveFields.value.length) return legacyArchiveRules
  const nextRules: FormRules = {}
  effectiveArchiveFields.value
    .filter(field => field.visible && field.required)
    .forEach((field) => {
      nextRules[field.field_key] = [{
        required: true,
        message: `${field.label.includes('日期') || field.label.includes('时间') ? '请选择' : '请填写'}${field.label}`,
        trigger: ['blur', 'change'],
      }]
    })
  return nextRules
})

// ========== AG Grid 列定义 ==========
function escapeHtml(value: any) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatDeleteBlockers(blockers: unknown) {
  if (!Array.isArray(blockers) || blockers.length === 0) return '该档案当前受保护，无法删除'
  return blockers
    .map(blocker => `${blocker?.label || '业务关联'}（${Number(blocker?.count) || 0}）`)
    .join('；')
}

function archiveIsEnabled(row: any) {
  return row?.is_enabled === 1
}

function archiveColumnVisibility(key: string): Pick<ColDef, 'colId' | 'hide'> {
  return {
    colId: key,
    hide: !archiveColumnListAvailable(key) || !selectedArchiveColumnKeys.value.includes(key),
  }
}

const columnDefs = computed<ColDef[]>(() => [
  ...(hasPermission('project:archive:delete') || hasPermission('project:archive:sync') || hasPermission('project:archive:toggle')
    ? [{ colId: 'archive_selection', headerClass: 'archive-list-header-center', headerCheckboxSelection: true, checkboxSelection: true, width: 44, pinned: 'left', lockPinned: true, lockVisible: true, suppressMovable: true, filter: false, sortable: false, resizable: false } as ColDef]
    : []),
  { colId: 'project_code', field: 'project_code', headerName: '项目编号', width: 130, minWidth: 110, pinned: 'left', hide: !archiveColumnListAvailable('project_code') },
  { colId: 'project_name', field: 'project_name', headerName: '项目名称', width: 190, minWidth: 160, hide: !archiveColumnListAvailable('project_name') },
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
  {
    ...archiveColumnVisibility('plan_start_date'), field: 'plan_start_date', headerName: '计划开始', width: 118, minWidth: 112,
    valueFormatter: (params: any) => params.value ? params.value.substring(0, 10) : '-',
  },
  {
    ...archiveColumnVisibility('plan_end_date'), field: 'plan_end_date', headerName: '计划结束', width: 118, minWidth: 112,
    valueFormatter: (params: any) => params.value ? params.value.substring(0, 10) : '-',
  },
  { ...archiveColumnVisibility('created_by_name'), field: 'created_by_name', headerName: '创建人', width: 110, minWidth: 96 },
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
      const v = params.value
      if (!v || v === 'pending') return '<span class="pms-status pms-status-warning"><span class="pms-status-dot"></span>待同步</span>'
      if (v === 'success') return '<span class="pms-status pms-status-success"><span class="pms-status-dot"></span>已同步</span>'
      if (v === 'failed') {
        const title = escapeHtml(params.data.erp_error_msg || '')
        return `<span class="pms-status pms-status-danger" title="${title}"><span class="pms-status-dot"></span>失败</span>`
      }
      return '<span class="pms-status pms-status-neutral"><span class="pms-status-dot"></span>-</span>'
    },
  },
  {
    colId: 'archive_actions', headerName: '操作', width: 200, minWidth: 196, pinned: 'right', lockPinned: true, lockVisible: true, suppressMovable: true, filter: false, sortable: false, resizable: false,
    cellRenderer: (params: any) => {
      const row = params.data
      const actions: string[] = []
      if (archiveIsEnabled(row)) {
        if (hasPermission('project:archive:edit')) actions.push('<button type="button" class="pms-table-action edit-btn">编辑</button>')
        if (hasPermission('project:archive:sync')) actions.push('<button type="button" class="pms-table-action pms-link-success sync-btn">同步</button>')
        if (hasPermission('project:archive:toggle')) actions.push('<button type="button" class="pms-table-action pms-link-muted disable-btn">禁用</button>')
      } else {
        actions.push('<button type="button" class="pms-table-action view-btn">查看</button>')
        if (hasPermission('project:archive:toggle')) actions.push('<button type="button" class="pms-table-action pms-link-success enable-btn">启用</button>')
      }
      if (hasPermission('project:archive:delete')) {
        if (row.can_delete !== false) {
          actions.push('<button type="button" class="pms-table-action pms-link-danger del-btn">删除</button>')
        } else {
          const blockerTooltip = escapeHtml(formatDeleteBlockers(row.delete_blockers))
          actions.push(`<button type="button" class="pms-table-action archive-delete-disabled" title="${blockerTooltip}" aria-disabled="true" disabled>删除</button>`)
        }
      }
      return actions.join('')
    },
    onCellClicked: (params: any) => {
      if (params.event.target.classList.contains('edit-btn') || params.event.target.classList.contains('view-btn')) {
        openArchiveDrawer(params.data)
      } else if (params.event.target.classList.contains('sync-btn')) {
        handleSyncSingle(params.data.id)
      } else if (params.event.target.classList.contains('disable-btn')) {
        handleArchiveEnabledChange(params.data, false)
      } else if (params.event.target.classList.contains('enable-btn')) {
        handleArchiveEnabledChange(params.data, true)
      } else if (params.event.target.classList.contains('del-btn')) {
        handleDeleteSingle(params.data)
      }
    },
  },
])

const defaultColDef = {
  sortable: true,
  resizable: true,
  filter: false,
  suppressSizeToFit: true,
  headerClass: 'archive-list-header-center',
}

// ========== 数据加载 ==========
function archiveEnabledHttpValue(enabled: boolean | null) {
  if (enabled === true) return 'true'
  if (enabled === false) return 'false'
  return 'all'
}

async function fetchList() {
  const res: any = await request.get('/projects/archives/list', {
    params: {
      page: 1,
      page_size: 1000,
      enabled: archiveEnabledHttpValue(archiveQuery.enabled),
    },
  })
  rowData.value = res.items
  total.value = res.total
  scheduleArchiveScrollbarMetrics()
}

function handleArchiveEnabledFilterChange() {
  page.value = 1
  agGridRef.value?.api?.deselectAll?.()
  selectedRows.value = []
  fetchList()
}

async function fetchUsers() {
  userList.value = (await request.get('/users/options')) as any
}

// ========== 选择事件 ==========
function onSelectionChanged() {
  selectedRows.value = agGridRef.value?.api?.getSelectedRows?.() || []
}

const selectedRowsIncludeDisabled = computed(() => selectedRows.value.some(row => !archiveIsEnabled(row)))

function getArchiveRowClass(params: any) {
  return archiveIsEnabled(params.data) ? undefined : 'archive-row-disabled'
}

// ========== 新增与字段级抽屉编辑 ==========
function openCreateDialog() {
  if (!hasPermission('project:archive:add')) return
  formRef.value?.resetFields()
  clearArchiveServerErrors(archiveCreateServerErrors)
  Object.assign(form, {
    id: 0,
    project_code: '',
    project_name: '',
    customer: '',
    manager_id: null,
    equipment_series: null,
    product_category: null,
    serial_no: '',
    plan_start_date: '',
    plan_end_date: '',
  })
  dialogVisible.value = true
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
    plan_start_date: form.plan_start_date || null,
    plan_end_date: form.plan_end_date || null,
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
    project_code: row.project_code || '',
    project_name: row.project_name || '',
    customer: row.customer || '',
    manager_id: row.manager_id ?? null,
    equipment_series: row.equipment_series ?? null,
    product_category: row.product_category ?? null,
    serial_no: row.serial_no || '',
    plan_start_date: archiveDateValue(row.plan_start_date),
    plan_end_date: archiveDateValue(row.plan_end_date),
    erp_sync_status: row.erp_sync_status || 'pending',
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
  const values = archiveDrawerValues(row)
  Object.keys(archiveDrawerForm).forEach(key => delete archiveDrawerForm[key])
  Object.assign(archiveDrawerForm, values)
  archiveOriginalValues.value = { ...values }
  archivePendingChanges.value = {}
  archiveEditingField.value = null
  nextTick(() => archiveDrawerFormRef.value?.clearValidate())
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

async function openArchiveDrawer(row: any) {
  if (archiveIsEnabled(row) && !hasPermission('project:archive:edit')) return
  if (selectedArchive.value?.id === row.id) return
  if (!await confirmDiscardArchiveChanges()) return
  resetArchiveDrawer(row)
}

async function closeArchiveDrawer() {
  if (!await confirmDiscardArchiveChanges()) return
  selectedArchive.value = null
  archivePendingChanges.value = {}
  archiveEditingField.value = null
}

function archiveDrawerFieldRequired(field: ArchiveDrawerField) {
  return archiveFieldPolicy(field.key)?.required === true
}

function archiveDrawerFieldEditable(field: ArchiveDrawerField) {
  return !archiveDrawerReadOnly.value
    && field.source_type === 'archive'
    && archiveFieldEditable(field.key)
    && hasPermission('project:archive:edit')
}

function archiveDrawerReadonlyReason(field: ArchiveDrawerField) {
  if (archiveDrawerReadOnly.value) return '项目档案已禁用，仅供查看'
  if (field.source_type === 'system') return '系统维护字段，仅供查看'
  if (!hasPermission('project:archive:edit')) return '当前角色没有项目档案编辑权限'
  return '字段规则已设置为不可编辑'
}

function archiveDrawerFieldByKey(fieldKey: string) {
  return ARCHIVE_DRAWER_GROUP_DEFINITIONS
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
  if (field.key === 'erp_sync_status') {
    return ({ pending: '待同步', success: '已同步', failed: '同步失败' } as Record<string, string>)[String(value || 'pending')] || String(value)
  }
  if (archiveDrawerValueEmpty(field)) return archiveDrawerFieldEditable(field) ? '点击填写' : '-'
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
  if (field.key === 'manager_id') return value === '' || value == null ? null : Number(value)
  if (field.value_type === 'date') return value ? archiveDateValue(value) : null
  if (['product_category', 'equipment_series'].includes(field.key)) {
    return value === '' || value == null ? null : Number(value)
  }
  return value ?? ''
}

function sameArchiveDrawerValue(left: unknown, right: unknown) {
  return String(left ?? '') === String(right ?? '')
}

function startArchiveFieldEdit(field: ArchiveDrawerField) {
  if (archiveDrawerReadOnly.value) return
  if (!archiveDrawerFieldEditable(field)) return
  clearArchiveServerError(archiveDrawerServerErrors, field.key)
  if (archiveEditingField.value && archiveEditingField.value !== field.key) commitArchiveFieldEdit()
  archiveEditingField.value = field.key
}

function cancelArchiveFieldEdit() {
  if (!archiveEditingField.value) return
  const fieldKey = archiveEditingField.value
  archiveDrawerForm[fieldKey] = archivePendingChanges.value[fieldKey]?.value ?? archiveOriginalValues.value[fieldKey]
  archiveEditingField.value = null
}

function commitArchiveFieldEdit() {
  const fieldKey = archiveEditingField.value
  if (!fieldKey) return
  const field = archiveDrawerFieldByKey(fieldKey)
  if (!field) {
    archiveEditingField.value = null
    return
  }
  const value = normalizeArchiveDrawerValue(field, archiveDrawerForm[fieldKey])
  const originalValue = archiveOriginalValues.value[fieldKey]
  archiveDrawerForm[fieldKey] = value
  if (sameArchiveDrawerValue(value, originalValue)) {
    const nextChanges = { ...archivePendingChanges.value }
    delete nextChanges[fieldKey]
    archivePendingChanges.value = nextChanges
  } else {
    archivePendingChanges.value = {
      ...archivePendingChanges.value,
      [fieldKey]: { value, originalValue },
    }
  }
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
  if (!hasPermission('project:archive:add')) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  try {
    await request.post('/projects/archives', buildArchiveCreatePayload())
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchList()
  } catch (error) {
    if (await focusArchiveUniqueConflict(error, formRef, archiveCreateServerErrors)) return
    await focusArchivePolicyValidation(error)
  }
}

async function saveArchiveDrawer(syncAfterSave: boolean) {
  if (!selectedArchive.value || archiveDrawerReadOnly.value || archiveDrawerSaving.value || !hasPermission('project:archive:edit')) return
  if (syncAfterSave && !hasPermission('project:archive:sync')) return
  commitArchiveFieldEdit()
  if (!archivePendingChangeCount.value && !syncAfterSave) return

  const valid = await archiveDrawerFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const archiveId = selectedArchive.value.id
  const payload = buildArchiveDrawerPayload()
  archiveDrawerSaving.value = true
  try {
    if (Object.keys(payload).length) await request.put(`/projects/archives/${archiveId}`, payload)
  } catch (error) {
    if (await focusArchiveUniqueConflict(error, archiveDrawerFormRef, archiveDrawerServerErrors)) {
      archiveDrawerSaving.value = false
      return
    }
    await focusArchivePolicyValidation(error, archiveDrawerFormRef)
    archiveDrawerSaving.value = false
    return
  }

  archivePendingChanges.value = {}
  archiveEditingField.value = null
  let syncSucceeded = false
  if (syncAfterSave) {
    try {
      const syncRes: any = await request.post('/erp/sync', { archive_id: archiveId })
      syncSucceeded = Boolean(syncRes.success)
      if (!syncRes.success) ElMessage.warning(`档案已保存，但同步失败：${syncRes.message}`)
    } catch (error: any) {
      ElMessage.warning('档案已保存，但同步异常：' + (error?.response?.data?.message || error?.message))
    }
  }

  let refreshSucceeded = true
  try {
    await fetchList()
    const refreshed = rowData.value.find(row => row.id === archiveId)
    if (refreshed) resetArchiveDrawer(refreshed)
  } catch {
    refreshSucceeded = false
    ElMessage.warning('档案已保存，但列表刷新失败，请手动刷新页面')
  } finally {
    archiveDrawerSaving.value = false
  }

  if (!refreshSucceeded) return
  if (!syncAfterSave) ElMessage.success('项目档案已保存')
  if (syncAfterSave && syncSucceeded) ElMessage.success('保存并同步成功')
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

// ========== ERP 同步 ==========
async function handleSyncSingle(id: number) {
  if (!hasPermission('project:archive:sync')) return
  try {
    const res: any = await request.post('/erp/sync', { archive_id: id })
    if (res.success) {
      ElMessage.success(res.message)
    } else {
      ElMessage.error(res.message)
    }
    fetchList()
  } catch (e: any) {
    ElMessage.error('同步失败: ' + (e?.response?.data?.message || e?.message))
  }
}

async function handleBatchSync() {
  if (!hasPermission('project:archive:sync')) return
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定同步选中的 ${selectedRows.value.length} 条档案到金蝶 ERP 吗？`, '同步确认', { type: 'warning' })
  } catch {
    return
  }
  const ids = selectedRows.value.map((r: any) => r.id)
  try {
    const res: any = await request.post('/erp/sync/batch', { archive_ids: ids })
    if (res.success) {
      ElMessage.success(res.message)
    } else {
      ElMessage.error(res.message)
    }
    selectedRows.value = []
    fetchList()
  } catch (e: any) {
    ElMessage.error('批量同步失败: ' + (e?.response?.data?.message || e?.message))
  }
}

onMounted(async () => {
  await fetchEffectiveArchiveFields()
  fetchList(); fetchUsers(); fetchAllowedProductCategories()
  fetchDictOptions('product_category')
  fetchDictOptions('equipment_series')
  await resolveArchiveColumnPreferenceOwner()
  restoreSelectedArchiveColumnKeys()
  archiveColumnPreferencesReady.value = true
  await nextTick()
  completeArchiveColumnPreferenceRestore()
  scheduleArchiveScrollbarMetrics()
})
</script>

<style scoped>
.project-archive-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.project-archive-workbench.is-drawer-open {
  grid-template-columns: minmax(0, 1fr) 400px;
}

.archive-list-shell,
.project-archive-page {
  min-width: 0;
  min-height: 0;
}

.project-archive-page {
  height: 100%;
  min-height: 100%;
}

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
  padding: 14px 16px;
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
  padding: 4px 16px 16px;
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

.archive-drawer-field-row {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  align-items: start;
  gap: 12px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.72);
}

.archive-drawer-field-row.is-long-text {
  grid-template-columns: minmax(0, 1fr);
  gap: 3px;
}

.archive-drawer-field-label {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 30px;
  color: var(--pms-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.archive-required-mark {
  color: var(--pms-danger);
}

.archive-field-lock {
  color: var(--pms-text-muted);
  font-size: 12px;
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
  padding: 3px 6px 0;
  font-size: 11px;
}

.archive-drawer-field-value,
.archive-drawer-field-static {
  display: block;
  width: 100%;
  min-height: 30px;
  padding: 5px 7px;
  border: 1px solid transparent;
  border-radius: var(--pms-radius-sm);
  background: transparent;
  color: var(--pms-text);
  font-family: var(--pms-font);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
  text-align: left;
  white-space: pre-wrap;
}

.archive-drawer-field-value {
  cursor: text;
}

.archive-drawer-field-value:hover,
.archive-drawer-field-value:focus-visible {
  border-color: rgba(79, 70, 229, 0.22);
  outline: none;
  background: var(--pms-primary-soft);
  color: var(--pms-primary);
}

.archive-drawer-field-value.is-empty,
.archive-drawer-field-static.is-empty {
  color: var(--pms-text-muted);
}

.archive-drawer-field-editor {
  width: 100%;
  padding: 1px 0;
}

.archive-drawer-savebar {
  display: grid;
  flex: 0 0 auto;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--pms-border-soft);
  background: var(--pms-surface);
}

.archive-drawer-savebar :deep(.el-button + .el-button) {
  margin-left: 0;
}

.archive-drawer-save {
  min-width: 0;
}

:deep(.pms-table-action + .pms-table-action) {
  margin-left: 2px;
}

:deep(.archive-delete-disabled),
:deep(.archive-delete-disabled:hover) {
  color: var(--pms-text-muted);
  cursor: not-allowed;
  text-decoration: none;
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

  .archive-drawer-field-row {
    grid-template-columns: 88px minmax(0, 1fr);
  }
}
</style>
