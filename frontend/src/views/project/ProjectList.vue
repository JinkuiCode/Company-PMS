<template>
  <section
    class="project-progress-workbench"
    :class="{ 'is-drawer-open': selectedProject }"
  >
    <div class="progress-list-shell">
      <PmsDataList
        ref="projectListRef"
        class="project-list-page"
        scrollbar-label="项目进度工作台横向滚动条"
      >
        <template #header>
          <div class="progress-view-context" aria-label="当前项目进度视图">
            <span class="progress-view-label">{{ currentViewName }}</span>
            <span class="pms-muted">当前只开放总进度视图，多视图会在字段模型稳定后接入</span>
          </div>
        </template>

        <template #toolbar-left>
          <el-button type="primary" size="small" @click="openCreateDialog">
            <el-icon style="margin-right:4px;"><Plus /></el-icon>
            新增项目
          </el-button>
          <PmsListColumnPicker
            v-model="selectedSheetFieldKeys"
            :groups="columnPickerGroups"
            :default-keys="defaultSelectedSheetFieldKeys"
          />
        </template>

        <template #toolbar-right>
          <span v-if="lastSavedText" class="progress-save-tip">{{ lastSavedText }}</span>
          <span v-else class="pms-muted">单击选中；双击进度/计划字段自动保存；点右侧详情展开抽屉</span>
        </template>

        <template #filters>
          <PmsListFilters
            v-model:filters="customFilters"
            :fields="projectListFilterFieldsForView"
            :active-count="activeCustomFilterCount"
          >
            <el-input
              v-model="filterKeyword"
              placeholder="搜索项目号 / 项目名"
              size="small"
              clearable
              style="width: 210px;"
              :prefix-icon="Search"
            />
            <el-select
              v-model="filterProductLine"
              placeholder="产品类"
              size="small"
              clearable
              style="width: 128px;"
            >
              <el-option
                v-for="item in filteredProductLineOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-select
              v-model="filterStatus"
              placeholder="节点"
              size="small"
              clearable
              style="width: 116px;"
            >
              <el-option
                v-for="item in projectStatusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-tree-select
              v-model="filterDeptId"
              :data="deptList"
              :props="{ label: 'dept_name', value: 'id', children: 'children' }"
              check-strictly
              clearable
              placeholder="负责人部门"
              size="small"
              style="width: 148px;"
            />
          </PmsListFilters>
        </template>

        <template #grid>
          <ag-grid-vue
            ref="agGridRef"
            class="ag-theme-alpine wechat-table pms-ag-grid progress-workbench-grid"
            :rowData="displayedRowData"
            :columnDefs="columnDefs"
            :defaultColDef="defaultColDef"
            :localeText="localeText"
            :theme="'legacy'"
            :domLayout="'autoHeight'"
            :pagination="false"
            :enableCellTextSelection="true"
            :suppressRowClickSelection="true"
            :singleClickEdit="false"
            :stopEditingWhenCellsLoseFocus="true"
            :alwaysShowHorizontalScroll="true"
            :getRowClass="getRowClass"
            @grid-ready="onGridReady"
            @cell-double-clicked="onProjectCellDoubleClicked"
            @cell-value-changed="onCellValueChanged"
            @first-data-rendered="handleGridStructureChanged"
            @grid-size-changed="refreshListScrollbar"
            @column-resized="handleColumnResized"
            @column-moved="handleGridStructureChanged"
            @column-pinned="handleGridStructureChanged"
            @displayed-columns-changed="handleGridStructureChanged"
            style="width: 100%;"
          />
        </template>

        <template #pagination>
          <CustomPagination
            v-if="filteredRowData.length > 0"
            v-model="page"
            v-model:page-size="pageSize"
            :total="filteredRowData.length"
            @update:model-value="refreshListScrollbar"
            @update:page-size="() => { page = 1; refreshListScrollbar() }"
          />
        </template>

        <el-dialog v-model="dialogVisible" title="新增项目" width="520px">
          <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
            <el-form-item label="项目档案" prop="archive_id">
              <el-select
                v-model="form.archive_id"
                filterable
                placeholder="请选择项目档案（自动带出编号和名称）"
                style="width: 100%;"
                @change="onArchiveChange"
              >
                <el-option
                  v-for="a in archiveList"
                  :key="a.id"
                  :label="`${a.project_code} - ${a.project_name}`"
                  :value="a.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="项目编号">
              <el-input v-model="form.project_code" disabled placeholder="由档案自动带出" />
            </el-form-item>
            <el-form-item label="项目名称">
              <el-input v-model="form.project_name" disabled placeholder="由档案自动带出" />
            </el-form-item>
            <el-form-item label="所属部门" prop="dept_id">
              <el-tree-select
                v-model="form.dept_id"
                style="width: 100%;"
                :data="deptList"
                :props="{ label: 'dept_name', value: 'id', children: 'children' }"
                check-strictly
              />
            </el-form-item>
            <el-form-item label="项目经理" prop="pm_id">
              <el-select v-model="form.pm_id" style="width: 100%;">
                <el-option
                  v-for="u in userList"
                  :key="u.id"
                  :label="`${u.real_name} (${u.username})`"
                  :value="u.id"
                />
              </el-select>
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="开始日期">
                  <el-date-picker
                    v-model="form.start_date"
                    type="date"
                    style="width: 100%;"
                    value-format="YYYY-MM-DD"
                    placeholder="选择日期"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="结束日期">
                  <el-date-picker
                    v-model="form.end_date"
                    type="date"
                    style="width: 100%;"
                    value-format="YYYY-MM-DD"
                    placeholder="选择日期"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="预算(万)">
              <el-input-number
                v-model="form.budget"
                :min="0"
                :precision="2"
                style="width: 100%;"
                placeholder="请输入预算"
              />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="handleSubmit">确定</el-button>
          </template>
        </el-dialog>
      </PmsDataList>
    </div>

    <aside
      v-if="selectedProject"
      class="progress-detail-drawer"
      aria-label="项目进度详情"
    >
      <div class="drawer-head">
        <div class="drawer-title-row">
          <div class="drawer-title">{{ selectedProject.project_name || '-' }}</div>
          <el-button
            class="drawer-close"
            :icon="Close"
            size="small"
            text
            aria-label="收起项目详情"
            @click="closeProjectDrawer"
          >
            收起
          </el-button>
        </div>
        <div class="drawer-meta">
          {{ selectedProject.project_code || '-' }}
          <span>·</span>
          {{ selectedProject.product_line || '未设置产品类' }}
          <span>·</span>
          原计划发货 {{ selectedProject.end_date || '-' }}
        </div>
      </div>

      <div class="drawer-body">
        <section v-if="sheetDetailLoading" class="drawer-section">
          <div class="drawer-note muted">正在加载项目总表字段...</div>
        </section>

        <el-collapse
          v-else
          v-model="drawerOpenGroups"
          class="drawer-collapse"
        >
          <el-collapse-item
            v-for="group in orderedDrawerGroups"
            :key="group.key"
            :name="group.key"
            class="drawer-collapse-item"
          >
            <template #title>
              <div
                class="drawer-group-title"
                :aria-expanded="drawerOpenGroups.includes(group.key)"
              >
                <span>{{ group.label }}</span>
                <span class="drawer-field-count">已填写 {{ filledFieldCount(group) }}/{{ group.fields.length }} 项</span>
              </div>
            </template>

            <div class="drawer-field-list">
              <div
                v-for="field in group.fields"
                :key="field.key"
                class="drawer-field-row"
                :class="{
                  editing: drawerEditingField === field.key,
                  'is-long-text': field.value_type === 'long_text',
                  'is-progress': field.value_type === 'progress',
                }"
              >
                <div class="drawer-field-header">
                  <span class="drawer-field-label">{{ field.label }}</span>
                  <el-tooltip
                    v-if="drawerFieldReason(field)"
                    :content="drawerFieldReason(field)!.tooltip"
                    placement="top"
                  >
                    <el-icon class="drawer-field-icon" aria-hidden="true">
                      <component :is="drawerFieldReason(field)!.icon" />
                    </el-icon>
                  </el-tooltip>
                </div>

                <div class="drawer-field-content">
                  <template v-if="drawerEditingField === field.key">
                    <div
                      class="drawer-field-editor"
                      @keydown.enter.exact.prevent="commitDrawerEdit"
                      @keydown.esc.stop="cancelDrawerEdit"
                    >
                      <el-select
                        v-if="field.value_type === 'select'"
                        v-model="drawerDraftValue"
                        size="small"
                        filterable
                        :placeholder="`选择${field.label}`"
                        style="width: 100%;"
                      >
                        <el-option
                          v-for="option in sheetFieldOptions(field)"
                          :key="String(option.value)"
                          :label="option.label"
                          :value="option.value"
                        />
                      </el-select>
                      <el-input-number
                        v-else-if="field.value_type === 'number' || field.value_type === 'percent' || field.value_type === 'progress'"
                        v-model="drawerDraftValue"
                        size="small"
                        :min="0"
                        :max="field.value_type === 'progress' ? 100 : undefined"
                        :precision="field.value_type === 'progress' ? 0 : 2"
                        style="width: 100%;"
                      />
                      <el-date-picker
                        v-else-if="field.value_type === 'date' || field.value_type === 'datetime'"
                        v-model="drawerDraftValue"
                        type="date"
                        size="small"
                        value-format="YYYY-MM-DD"
                        style="width: 100%;"
                      />
                      <el-input
                        v-else-if="field.value_type === 'long_text'"
                        v-model="drawerDraftValue"
                        type="textarea"
                        size="small"
                        :rows="4"
                        :placeholder="`输入${field.label}`"
                        @keydown.enter.exact.prevent="commitDrawerEdit"
                      />
                      <el-input
                        v-else
                        v-model="drawerDraftValue"
                        size="small"
                        :placeholder="`输入${field.label}`"
                      />
                      <div class="drawer-editor-actions">
                        <el-button size="small" type="primary" link @click="commitDrawerEdit">保存</el-button>
                        <el-button size="small" link @click="cancelDrawerEdit">取消</el-button>
                      </div>
                    </div>
                  </template>

                  <template v-else>
                    <button
                      v-if="field.editable"
                      type="button"
                      class="drawer-field-value-button"
                      :aria-label="`编辑${field.label}`"
                      @click="startSheetFieldEdit(field)"
                    >
                      <template v-if="field.value_type === 'progress'">
                        <span class="drawer-progress-row">
                          <span class="pms-progress-track">
                            <span
                              class="pms-progress-bar"
                              :class="progressToneClass(sheetProgressValue(field))"
                              :style="{ width: `${sheetProgressValue(field)}%` }"
                            ></span>
                          </span>
                          <span class="drawer-progress-value">{{ sheetProgressValue(field) }}%</span>
                        </span>
                      </template>
                      <span v-else class="drawer-field-text">{{ formatSheetFieldValue(field, group.key) }}</span>
                    </button>
                    <div
                      v-else
                      class="drawer-field-value-static"
                      :aria-label="`${field.label}当前不可改`"
                    >
                      <template v-if="field.value_type === 'progress'">
                        <span class="drawer-progress-row">
                          <span class="pms-progress-track">
                            <span
                              class="pms-progress-bar"
                              :class="progressToneClass(sheetProgressValue(field))"
                              :style="{ width: `${sheetProgressValue(field)}%` }"
                            ></span>
                          </span>
                          <span class="drawer-progress-value">{{ sheetProgressValue(field) }}%</span>
                        </span>
                      </template>
                      <span v-else class="drawer-field-text">{{ formatSheetFieldValue(field, group.key) }}</span>
                    </div>

                    <el-tooltip
                      v-if="canQuickToggleField(field)"
                      :content="isSheetFieldSelected(field.key) ? '移出列表' : '加入列表'"
                      placement="top"
                    >
                      <button
                        type="button"
                        class="drawer-quick-toggle"
                        :aria-label="isSheetFieldSelected(field.key) ? `将${field.label}移出列表` : `将${field.label}加入列表`"
                        :aria-pressed="isSheetFieldSelected(field.key)"
                        @click="toggleSheetFieldSelection(field.key)"
                      >
                        <el-icon aria-hidden="true">
                          <component :is="isSheetFieldSelected(field.key) ? Minus : Plus" />
                        </el-icon>
                      </button>
                    </el-tooltip>
                  </template>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  Close,
  Plus,
  Minus,
  Search,
  Link,
  Lock,
  DataAnalysis,
  Setting,
} from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import {
  ModuleRegistry,
  AllCommunityModule,
  type CellDoubleClickedEvent,
  type CellValueChangedEvent,
  type ColDef,
  type ColGroupDef,
  type GridReadyEvent,
  type RowClassParams,
} from 'ag-grid-community'
import type { ColumnState } from 'ag-grid-community'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsDataList from '@/components/PmsDataList.vue'
import PmsListFilters from '@/components/PmsListFilters.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import { type ListFilterField, type ListFilterOption, useListFilters } from '@/composables/useListFilters'
import { chineseLocaleText } from '@/utils/agGridLocale'
import request from '@/utils/request'

ModuleRegistry.registerModules([AllCommunityModule])

type ProjectRow = {
  id: number
  project_code: string
  project_name: string
  dept_id: number
  dept_name?: string
  pm_id: number
  pm_name?: string
  status: number | string
  start_date?: string | null
  end_date?: string | null
  budget?: number | null
  description?: string | null
  product_line?: string | null
  task_count?: number
  total_progress?: number
  design_progress?: number
  order_progress?: number
  kit_progress?: number
  frame_progress?: number
  dryer_progress?: number
  assembly_progress?: number
  test_progress?: number
  sheet_fields?: Record<string, unknown>
}

type StageProgressFieldKey =
  | 'design_progress'
  | 'order_progress'
  | 'kit_progress'
  | 'frame_progress'
  | 'dryer_progress'
  | 'assembly_progress'
  | 'test_progress'

type EditableProjectFieldKey =
  | 'pm_name'
  | 'dept_name'
  | 'status'
  | 'start_date'
  | 'end_date'
  | 'budget'
  | StageProgressFieldKey

type ProjectSheetFieldMeta = {
  sort: number
  key: string
  label: string
  group: string
  value_type: 'text' | 'long_text' | 'date' | 'datetime' | 'number' | 'percent' | 'progress' | 'select'
  source_type: 'detail' | 'project' | 'archive' | 'computed' | 'system'
  editable: boolean
  computed: boolean
  list_available: boolean
  quick_addable: boolean
}

type ProjectSheetField = ProjectSheetFieldMeta & {
  value: unknown
}

type ProjectSheetGroupMeta = {
  key: string
  label: string
  sort: number
  fields: ProjectSheetFieldMeta[]
}

type ProjectSheetGroup = {
  key: string
  label: string
  sort: number
  fields: ProjectSheetField[]
}

type ColumnPreferenceState = {
  selected_sheet_field_keys: string[]
  columnState: ColumnState[]
}

const localeText = chineseLocaleText
const currentViewName = '总进度'
const COLUMN_STORAGE_KEY = 'pms_project_progress_list_columns_v1'
const progressSummaryMaxLength = 24
const drawerDefaultExpandedGroupKeys = ['basic', 'stage', 'plan']

const DEFAULT_SHEET_GROUPS = [
  { key: 'basic', label: '基础信息', sort: 10 },
  { key: 'stage', label: '阶段进度', sort: 20 },
  { key: 'plan', label: '计划节点', sort: 30 },
  { key: 'actual', label: '实际节点', sort: 40 },
  { key: 'progress', label: '推进记录', sort: 50 },
  { key: 'product', label: '产品配置', sort: 60 },
  { key: 'delivery', label: '交付验收', sort: 70 },
  { key: 'people', label: '人员分工', sort: 80 },
  { key: 'issues', label: '问题统计', sort: 90 },
  { key: 'duration', label: '工期分析', sort: 100 },
  { key: 'system', label: '系统信息', sort: 110 },
] as const

const DEFAULT_GROUP_SORT_MAP = Object.fromEntries(DEFAULT_SHEET_GROUPS.map(item => [item.key, item.sort])) as Record<string, number>
const DEFAULT_GROUP_LABEL_MAP = Object.fromEntries(DEFAULT_SHEET_GROUPS.map(item => [item.key, item.label])) as Record<string, string>

const progressFieldKeys: StageProgressFieldKey[] = [
  'design_progress',
  'order_progress',
  'kit_progress',
  'frame_progress',
  'dryer_progress',
  'assembly_progress',
  'test_progress',
]

const stageProgressOffsets: Record<StageProgressFieldKey, number> = {
  design_progress: 24,
  order_progress: 12,
  kit_progress: 0,
  frame_progress: -8,
  dryer_progress: -14,
  assembly_progress: -22,
  test_progress: -34,
}

const sheetProjectFieldMap: Record<string, EditableProjectFieldKey> = {
  node_status: 'status',
  project_start_date: 'start_date',
  original_planned_ship_date: 'end_date',
  design_progress: 'design_progress',
  order_progress: 'order_progress',
  kit_progress: 'kit_progress',
  frame_progress: 'frame_progress',
  dryer_progress: 'dryer_progress',
  assembly_progress: 'assembly_progress',
  test_progress: 'test_progress',
}

const projectListRef = ref<InstanceType<typeof PmsDataList>>()
const agGridRef = ref<any>()
const gridApi = ref<any>(null)

const rowData = ref<ProjectRow[]>([])
const archiveList = ref<any[]>([])
const deptList = ref<any[]>([])
const deptNames = ref<string[]>([])
const deptFlatList = ref<any[]>([])
const userList = ref<any[]>([])
const userNames = ref<string[]>([])
const serverTotal = ref(0)
const page = ref(1)
const pageSize = ref(15)
const filterKeyword = ref('')
const filterStatus = ref<number | null>(null)
const filterDeptId = ref<number | null>(null)
const filterProductLine = ref<string | null>(null)
const selectedProject = ref<ProjectRow | null>(null)
const lastSavedText = ref('')
const drawerOpenGroups = ref<string[]>([...drawerDefaultExpandedGroupKeys])
const drawerEditingField = ref<string | null>(null)
const drawerEditingFieldData = ref<ProjectSheetField | null>(null)
const drawerDraftValue = ref<unknown>(null)
const sheetDetailGroups = ref<ProjectSheetGroup[]>([])
const sheetDetailLoading = ref(false)
const sheetFieldGroupsMeta = ref<ProjectSheetGroupMeta[]>(buildFallbackSheetGroupMetas())
const sheetMetadataLoaded = ref(false)
const selectedSheetFieldKeys = ref<string[]>([])
const restoringColumnState = ref(false)

const productLineOptions = ref<ListFilterOption[]>([])
const allowedProductLines = ref<string[] | null>(null)
const projectStatusOptions: ListFilterOption[] = [
  { label: '进行中', value: 1 },
  { label: '已完结', value: 2 },
  { label: '暂停', value: 3 },
]
const projectStatusEditorValues = projectStatusOptions.map(item => item.label)

const filteredProductLineOptions = computed(() => {
  if (allowedProductLines.value === null) return productLineOptions.value
  return productLineOptions.value.filter(item => allowedProductLines.value!.includes(String(item.value)))
})

const deptNameOptions = computed(() => deptFlatList.value.map((dept: any) => ({
  label: dept.dept_name,
  value: dept.dept_name,
})))

const userNameFilterOptions = computed(() => userNames.value.map(name => ({
  label: name,
  value: name,
})))

const sheetFieldMetas = computed(() => sheetFieldGroupsMeta.value.flatMap(group => group.fields))
const sheetFieldMetaMap = computed(() => {
  return new Map(sheetFieldMetas.value.map(field => [field.key, field]))
})

const defaultSelectedSheetFieldKeys = computed(() => {
  const quickAddableKeys = sheetFieldMetas.value
    .filter(field => field.list_available && field.quick_addable && field.value_type !== 'long_text')
    .map(field => field.key)
  if (quickAddableKeys.length) return quickAddableKeys
  return sheetFieldMetas.value
    .filter(field => field.list_available)
    .slice(0, 6)
    .map(field => field.key)
})

const columnPickerGroups = computed(() => {
  return sheetFieldGroupsMeta.value.map(group => ({
    key: group.key,
    label: group.label,
    fields: group.fields.filter(field => field.list_available),
  }))
})

const projectListFilterFields = computed<ListFilterField<ProjectRow>[]>(() => {
  const fixedFields: ListFilterField<ProjectRow>[] = [
    { field: 'project_code', label: '项目编号', type: 'text' },
    { field: 'project_name', label: '项目名称', type: 'text' },
    { field: 'product_line', label: '产品类', type: 'select', options: () => filteredProductLineOptions.value },
    { field: 'status', label: '节点', type: 'select', options: () => projectStatusOptions, getValue: row => statusLabel(row.status) },
    { field: 'dept_name', label: '所属部门', type: 'select', options: () => deptNameOptions.value },
    { field: 'pm_name', label: '负责人', type: 'select', options: () => userNameFilterOptions.value },
    { field: 'total_progress', label: '总进度', type: 'number' },
    { field: 'task_count', label: '任务数', type: 'number' },
    { field: 'budget', label: '预算', type: 'number' },
    { field: 'start_date', label: '立项日期', type: 'date' },
    { field: 'end_date', label: '原计划发货', type: 'date' },
  ]

  const dynamicFields = sheetFieldMetas.value.map<ListFilterField<ProjectRow>>((field) => ({
    field: field.key,
    label: `${sheetGroupLabel(field.group)} / ${field.label}`,
    type: toListFilterType(field.value_type),
    getValue: row => row.sheet_fields?.[field.key],
    options: field.value_type === 'select'
      ? () => uniqueSheetFieldOptions(field.key)
      : undefined,
  }))

  return [...fixedFields, ...dynamicFields]
})

const projectListFilterFieldsForView = computed(() => projectListFilterFields.value as unknown as ListFilterField[])

const { customFilters, activeCustomFilterCount, applyCustomFilters } = useListFilters<ProjectRow>(projectListFilterFields)

const currentFilterSheetFieldKeys = computed(() => {
  const keys = new Set<string>()
  for (const filter of customFilters.value) {
    if (sheetFieldMetaMap.value.has(filter.field)) {
      keys.add(filter.field)
    }
  }
  return Array.from(keys).sort()
})

const requestedSheetFieldKeys = computed(() => {
  const keys = new Set<string>()
  for (const key of selectedSheetFieldKeys.value) keys.add(key)
  for (const key of currentFilterSheetFieldKeys.value) keys.add(key)
  return Array.from(keys).sort()
})

const filteredRowData = computed(() => {
  let result = rowData.value
  if (filterKeyword.value) {
    const kw = filterKeyword.value.toLowerCase()
    result = result.filter(row =>
      String(row.project_code ?? '').toLowerCase().includes(kw)
      || String(row.project_name ?? '').toLowerCase().includes(kw)
      || String(row.product_line ?? '').toLowerCase().includes(kw)
    )
  }
  if (filterStatus.value != null) {
    result = result.filter(row => normalizeStatus(row.status) === filterStatus.value)
  }
  if (filterDeptId.value != null) {
    result = result.filter(row => row.dept_id === filterDeptId.value)
  }
  if (filterProductLine.value) {
    result = result.filter(row => row.product_line === filterProductLine.value)
  }
  return applyCustomFilters(result)
})

const displayedRowData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRowData.value.slice(start, start + pageSize.value)
})

const orderedDrawerGroups = computed(() => {
  if (sheetDetailGroups.value.length) return sheetDetailGroups.value
  if (!selectedProject.value) return []
  return buildDrawerGroupsFromRow(selectedProject.value)
})

watch([filterKeyword, filterStatus, filterDeptId, filterProductLine, customFilters], () => {
  page.value = 1
  if (selectedProject.value && !filteredRowData.value.some(row => row.id === selectedProject.value?.id)) {
    selectedProject.value = null
  }
  nextTick(refreshListScrollbar)
}, { deep: true })

watch(
  () => sheetMetadataLoaded.value ? requestedSheetFieldKeys.value.join(',') : '__pending__',
  (signature) => {
    if (signature === '__pending__') return
    fetchList()
  },
  { immediate: true },
)

watch(
  () => selectedSheetFieldKeys.value.join(','),
  async () => {
    persistColumnPreferences()
    await nextTick()
    restoreColumnState()
  },
)

const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  id: 0,
  archive_id: null as number | null,
  project_code: '',
  project_name: '',
  dept_id: 0,
  pm_id: 0,
  status: 1,
  start_date: '',
  end_date: '',
  budget: null as number | null,
})

const rules: FormRules = {
  archive_id: [{ required: true, message: '请选择项目档案' }],
  dept_id: [{ required: true, message: '请选择部门' }],
  pm_id: [{ required: true, message: '请选择项目经理' }],
}

function sheetGroupLabel(groupKey: string) {
  return DEFAULT_GROUP_LABEL_MAP[groupKey] || groupKey
}

function buildFallbackSheetGroupMetas(): ProjectSheetGroupMeta[] {
  return DEFAULT_SHEET_GROUPS.map(group => ({
    key: group.key,
    label: group.label,
    sort: group.sort,
    fields: [],
  }))
}

function normalizeSheetGroupKey(key: unknown, label?: unknown) {
  const rawKey = String(key || '').trim()
  const rawLabel = String(label || '').trim()
  if (rawKey === 'progress_notes' || rawLabel.includes('推进')) return 'progress'
  if (rawKey === 'stage_progress' || rawLabel.includes('阶段')) return 'stage'
  if (rawLabel.includes('计划')) return 'plan'
  if (rawLabel.includes('实际')) return 'actual'
  if (rawLabel.includes('产品')) return 'product'
  if (rawLabel.includes('交付')) return 'delivery'
  if (rawLabel.includes('人员')) return 'people'
  if (rawLabel.includes('问题')) return 'issues'
  if (rawLabel.includes('工期')) return 'duration'
  if (rawLabel.includes('系统')) return 'system'
  if (rawLabel.includes('基础')) return 'basic'
  return rawKey || 'basic'
}

function normalizeFieldMeta(rawField: any, index: number): ProjectSheetFieldMeta | null {
  if (!rawField?.key) return null
  const key = String(rawField.key)
  const valueType = (['text', 'long_text', 'date', 'datetime', 'number', 'percent', 'progress', 'select'].includes(rawField.value_type)
    ? rawField.value_type
    : 'text') as ProjectSheetFieldMeta['value_type']
  const sourceType = (['detail', 'project', 'archive', 'computed', 'system'].includes(rawField.source_type)
    ? rawField.source_type
    : 'detail') as ProjectSheetFieldMeta['source_type']
  return {
    sort: numberValue(rawField.sort, index + 1),
    key,
    label: String(rawField.label || key),
    group: normalizeSheetGroupKey(rawField.group, rawField.group_label),
    value_type: valueType,
    source_type: sourceType,
    editable: Boolean(rawField.editable),
    computed: Boolean(rawField.computed),
    list_available: Boolean(rawField.list_available),
    quick_addable: Boolean(rawField.quick_addable),
  }
}

function normalizeSheetMetadata(payload: any): ProjectSheetGroupMeta[] {
  const fallbackGroups = buildFallbackSheetGroupMetas()
  const groupMap = new Map<string, ProjectSheetGroupMeta>(fallbackGroups.map(group => [group.key, { ...group, fields: [] }]))

  const rawGroups = Array.isArray(payload?.groups) ? payload.groups : []
  const groupFields = rawGroups.flatMap((group: any) => Array.isArray(group?.fields) ? group.fields : [])
  const rawFields = Array.isArray(payload?.fields) && payload.fields.length ? payload.fields : groupFields

  rawGroups.forEach((group: any, index: number) => {
    const key = normalizeSheetGroupKey(group?.key, group?.label)
    const current = groupMap.get(key) || {
      key,
      label: String(group?.label || DEFAULT_GROUP_LABEL_MAP[key] || key),
      sort: numberValue(group?.sort, DEFAULT_GROUP_SORT_MAP[key] || index + 1),
      fields: [],
    }
    current.label = String(group?.label || current.label || DEFAULT_GROUP_LABEL_MAP[key] || key)
    current.sort = numberValue(group?.sort, current.sort)
    groupMap.set(key, current)
  })

  rawFields.forEach((rawField: any, index: number) => {
    const field = normalizeFieldMeta(rawField, index)
    if (!field) return
    const groupKey = normalizeSheetGroupKey(field.group)
    const group = groupMap.get(groupKey) || {
      key: groupKey,
      label: DEFAULT_GROUP_LABEL_MAP[groupKey] || groupKey,
      sort: DEFAULT_GROUP_SORT_MAP[groupKey] || 500 + index,
      fields: [],
    }
    group.fields.push({ ...field, group: groupKey })
    groupMap.set(groupKey, group)
  })

  return Array.from(groupMap.values())
    .map(group => ({
      ...group,
      label: group.label || DEFAULT_GROUP_LABEL_MAP[group.key] || group.key,
      fields: group.fields.slice().sort((a, b) => a.sort - b.sort),
    }))
    .sort((a, b) => a.sort - b.sort)
}

function normalizeSheetDetailGroups(groups: any[], row?: ProjectRow | null): ProjectSheetGroup[] {
  const byMeta = new Map(sheetFieldMetas.value.map(field => [field.key, field]))
  return groups
    .map((group: any, groupIndex: number) => {
      const key = normalizeSheetGroupKey(group?.key, group?.label)
      const fields = Array.isArray(group?.fields) ? group.fields : []
      return {
        key,
        label: String(group?.label || DEFAULT_GROUP_LABEL_MAP[key] || key),
        sort: numberValue(group?.sort, DEFAULT_GROUP_SORT_MAP[key] || groupIndex + 1),
        fields: fields
          .map((field: any, fieldIndex: number) => {
            const meta = byMeta.get(String(field?.key))
            const normalized = normalizeFieldMeta({ ...meta, ...field, group: key }, fieldIndex)
            if (!normalized) return null
            return {
              ...normalized,
              value: field?.value ?? row?.sheet_fields?.[normalized.key] ?? null,
            } satisfies ProjectSheetField
          })
          .filter(Boolean) as ProjectSheetField[],
      }
    })
    .sort((a, b) => a.sort - b.sort)
}

function buildDrawerGroupsFromRow(row: ProjectRow): ProjectSheetGroup[] {
  return sheetFieldGroupsMeta.value.map((group) => ({
    key: group.key,
    label: group.label,
    sort: group.sort,
    fields: group.fields.map((field) => ({
      ...field,
      value: row.sheet_fields?.[field.key] ?? null,
    })),
  }))
}

function progressToneClass(v: number) {
  if (v < 30) return 'is-danger'
  if (v < 80) return 'is-warning'
  return 'is-success'
}

function escapeHtml(value: unknown) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function clampProgress(value: number) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value)))
}

function numberValue(value: unknown, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function isProgressField(field: string): field is StageProgressFieldKey {
  return progressFieldKeys.includes(field as StageProgressFieldKey)
}

function normalizeProgressInput(value: unknown) {
  if (value == null || value === '') return null
  return clampProgress(numberValue(value))
}

function stageProgress(row: ProjectRow, field: StageProgressFieldKey) {
  if (row[field] != null) return clampProgress(numberValue(row[field]))
  return clampProgress(numberValue(row.total_progress) + stageProgressOffsets[field])
}

function materializeStageProgressDefaults(row: ProjectRow) {
  const next = {
    ...row,
    sheet_fields: row.sheet_fields && typeof row.sheet_fields === 'object' ? { ...row.sheet_fields } : {},
  }
  for (const field of progressFieldKeys) {
    if (next[field] == null) {
      next[field] = stageProgress(next, field)
    }
  }
  return next
}

function renderProgressBar(value: number) {
  const v = clampProgress(value)
  const tone = progressToneClass(v)
  return `<div class="pms-progress-cell">
    <div class="pms-progress-track">
      <div class="pms-progress-bar ${tone}" style="width:${v}%;"></div>
    </div>
    <span class="pms-progress-value">${v}%</span>
  </div>`
}

function renderStageProgress(field: StageProgressFieldKey) {
  return (params: any) => renderProgressBar(stageProgress(params.data, field))
}

function parseProgressEditValue(params: any) {
  return normalizeProgressInput(params.newValue)
}

function normalizeStatus(value: number | string | null | undefined) {
  if (typeof value === 'number') return value
  const map: Record<string, number> = { '进行中': 1, '已完结': 2, '暂停': 3 }
  if (value && map[value]) return map[value]
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 1
}

function statusLabel(value: number | string | null | undefined) {
  const map: Record<number, string> = { 1: '进行中', 2: '已完结', 3: '暂停' }
  return map[normalizeStatus(value)] || '-'
}

function statusTone(value: number | string | null | undefined) {
  const map: Record<number, string> = { 1: 'info', 2: 'success', 3: 'warning' }
  return map[normalizeStatus(value)] || 'neutral'
}

function toListFilterType(valueType: ProjectSheetFieldMeta['value_type']) {
  if (valueType === 'date' || valueType === 'datetime') return 'date'
  if (valueType === 'number' || valueType === 'percent' || valueType === 'progress') return 'number'
  if (valueType === 'select') return 'select'
  return 'text'
}

function uniqueSheetFieldOptions(fieldKey: string): ListFilterOption[] {
  const values = new Set<string>()
  rowData.value.forEach((row) => {
    const value = row.sheet_fields?.[fieldKey]
    if (value != null && value !== '') values.add(String(value))
  })
  return Array.from(values).sort().map(value => ({ label: value, value }))
}

function sheetColumnId(fieldKey: string) {
  return `sheet:${fieldKey}`
}

function isSheetFieldSelected(fieldKey: string) {
  return selectedSheetFieldKeys.value.includes(fieldKey)
}

function sheetFieldValue(row: ProjectRow | null | undefined, fieldKey: string) {
  return row?.sheet_fields?.[fieldKey] ?? null
}

function summarizeProgressText(value: unknown) {
  const text = String(value ?? '').trim().replace(/\s+/g, ' ')
  if (!text) return '-'
  if (text.length <= progressSummaryMaxLength) return text
  return `${text.slice(0, progressSummaryMaxLength)}...`
}

function isFilledValue(value: unknown) {
  return value !== null && value !== undefined && value !== ''
}

function filledFieldCount(group: ProjectSheetGroup) {
  return group.fields.filter(field => isFilledValue(field.value)).length
}

function isReferenceSheetField(field: ProjectSheetFieldMeta) {
  return ['archive', 'project'].includes(field.source_type) && !field.editable
}

function drawerFieldReason(field: ProjectSheetFieldMeta) {
  if (field.computed || field.source_type === 'computed') {
    return { icon: DataAnalysis, tooltip: '计算结果' }
  }
  if (isReferenceSheetField(field)) {
    return { icon: Link, tooltip: '引用来源' }
  }
  if (field.source_type === 'system') {
    return { icon: Setting, tooltip: '系统维护' }
  }
  if (!field.editable) {
    return { icon: Lock, tooltip: '当前不可改' }
  }
  return null
}

function canQuickToggleField(field: ProjectSheetFieldMeta) {
  return Boolean(field.quick_addable && field.list_available && field.value_type !== 'long_text' && field.source_type !== 'system')
}

function toggleSheetFieldSelection(fieldKey: string) {
  const next = new Set(selectedSheetFieldKeys.value)
  if (next.has(fieldKey)) next.delete(fieldKey)
  else next.add(fieldKey)
  selectedSheetFieldKeys.value = Array.from(next)
}

function dynamicColumnDefs(): Array<ColDef<ProjectRow> | ColGroupDef<ProjectRow>> {
  return sheetFieldGroupsMeta.value
    .map((group) => {
      const fields = group.fields.filter(field => selectedSheetFieldKeys.value.includes(field.key))
      if (!fields.length) return null
      return {
        headerName: group.label,
        marryChildren: false,
        children: fields.map((field) => ({
          colId: sheetColumnId(field.key),
          headerName: field.label,
          width: field.value_type === 'long_text' ? 210 : 136,
          minWidth: field.value_type === 'long_text' ? 170 : 110,
          editable: false,
          sortable: true,
          valueGetter: (params: any) => sheetFieldValue(params.data, field.key),
          tooltipValueGetter: (params: any) => formatSheetFieldValue({ ...field, value: sheetFieldValue(params.data, field.key) }, group.key),
          cellRenderer: (params: any) => {
            const value = sheetFieldValue(params.data, field.key)
            if (field.value_type === 'progress') {
              return renderProgressBar(clampProgress(numberValue(value)))
            }
            const text = formatSheetFieldValue({ ...field, value }, group.key)
            return `<span class="sheet-column-text">${escapeHtml(text)}</span>`
          },
        })),
      } satisfies ColGroupDef<ProjectRow>
    })
    .filter(Boolean) as Array<ColDef<ProjectRow> | ColGroupDef<ProjectRow>>
}

const columnDefs = computed<Array<ColDef<ProjectRow> | ColGroupDef<ProjectRow>>>(() => [
  { field: 'project_code', headerName: '项目号', width: 112, pinned: 'left', filter: false },
  {
    field: 'project_name',
    headerName: '项目名称',
    width: 190,
    minWidth: 150,
    pinned: 'left',
    cellRenderer: (params: any) => `<span class="proj-name-cell">${escapeHtml(params.value || '-')}</span>`,
  },
  { field: 'product_line', headerName: '产品类', width: 100 },
  {
    field: 'status',
    headerName: '节点',
    width: 102,
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: { values: projectStatusEditorValues },
    cellRenderer: (params: any) => {
      const tone = statusTone(params.value)
      return `<span class="pms-status pms-status-${tone}"><span class="pms-status-dot"></span>${statusLabel(params.value)}</span>`
    },
  },
  {
    field: 'end_date',
    headerName: '原计划发货',
    width: 122,
    editable: true,
    cellEditor: 'agTextCellEditor',
  },
  {
    headerName: '项目进度',
    marryChildren: true,
    children: [
      { field: 'design_progress', headerName: '设计进度', width: 112, editable: true, cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('design_progress') },
      { field: 'order_progress', headerName: '下单进度', width: 112, editable: true, cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('order_progress') },
      { field: 'kit_progress', headerName: '齐套进度', width: 112, editable: true, cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('kit_progress') },
      { field: 'frame_progress', headerName: '框架进度', width: 112, editable: true, cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('frame_progress') },
      { field: 'dryer_progress', headerName: 'dryer进度', width: 112, editable: true, cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('dryer_progress') },
      { field: 'assembly_progress', headerName: '组装进度', width: 112, editable: true, cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('assembly_progress') },
      { field: 'test_progress', headerName: '测试进度', width: 112, editable: true, cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('test_progress') },
    ],
  },
  {
    headerName: '成员 / 配置',
    marryChildren: true,
    children: [
      {
        field: 'pm_name',
        headerName: '负责人',
        width: 112,
        editable: true,
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: () => ({ values: userNames.value }),
      },
      {
        field: 'dept_name',
        headerName: '所属部门',
        width: 124,
        editable: true,
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: () => ({ values: deptNames.value }),
      },
      { field: 'budget', headerName: '预算(万)', width: 110, editable: true, type: 'numericColumn' },
    ],
  },
  ...dynamicColumnDefs(),
  { field: 'task_count', headerName: '关联任务', width: 94 },
  {
    headerName: '操作',
    width: 118,
    pinned: 'right',
    filter: false,
    sortable: false,
    resizable: false,
    cellRenderer: () => `
      <span class="progress-row-actions">
        <button class="progress-detail-btn detail-btn" type="button" title="打开详情" aria-label="打开详情">详情</button>
        <button class="pms-more-btn more-btn" type="button" title="更多操作" aria-label="更多操作"></button>
      </span>
    `,
    onCellClicked: (params: any) => {
      if (params.event.target.classList.contains('detail-btn')) {
        openProjectDrawer(params.data)
        return
      }
      if (params.event.target.classList.contains('more-btn')) {
        handleRowMenu(params.data)
      }
    },
  },
])

const defaultColDef: ColDef = {
  sortable: true,
  resizable: true,
  filter: false,
  cellClassRules: {
    'progress-editable-cell': params => {
      const editable = params.colDef.editable
      return typeof editable === 'function' ? Boolean(editable(params as any)) : editable === true
    },
  },
}

function refreshListScrollbar() {
  nextTick(() => projectListRef.value?.refreshScrollbar())
}

function readStoredColumnPreferences(): ColumnPreferenceState | null {
  const raw = localStorage.getItem(COLUMN_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function persistColumnPreferences() {
  const state: ColumnPreferenceState = {
    selected_sheet_field_keys: [...selectedSheetFieldKeys.value],
    columnState: gridApi.value?.getColumnState?.() || [],
  }
  localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(state))
}

function restoreColumnState() {
  if (!gridApi.value) return
  const saved = readStoredColumnPreferences()
  if (!saved?.columnState?.length) return
  restoringColumnState.value = true
  try {
    gridApi.value.applyColumnState({ state: saved.columnState, applyOrder: true })
  } finally {
    restoringColumnState.value = false
  }
  refreshListScrollbar()
}

function restoreSelectedSheetFieldKeys() {
  const saved = readStoredColumnPreferences()
  const availableKeys = new Set(sheetFieldMetas.value.filter(field => field.list_available).map(field => field.key))
  const savedKeys = saved?.selected_sheet_field_keys?.filter(key => availableKeys.has(key)) || []
  selectedSheetFieldKeys.value = savedKeys.length ? savedKeys : [...defaultSelectedSheetFieldKeys.value]
}

function onGridReady(params: GridReadyEvent<ProjectRow>) {
  gridApi.value = params.api
  restoreColumnState()
  refreshListScrollbar()
}

function handleGridStructureChanged() {
  refreshListScrollbar()
  if (restoringColumnState.value) return
  persistColumnPreferences()
}

function handleColumnResized(event: any) {
  refreshListScrollbar()
  if (!event?.finished || restoringColumnState.value) return
  persistColumnPreferences()
}

async function fetchList() {
  const params: Record<string, unknown> = { page: 1, page_size: 1000 }
  if (requestedSheetFieldKeys.value.length) {
    params.sheet_field_keys = requestedSheetFieldKeys.value.join(',')
  }
  const res: any = await request.get('/projects', { params })
  rowData.value = res.items.map(materializeStageProgressDefaults)
  serverTotal.value = res.total
  if (selectedProject.value) {
    selectedProject.value = rowData.value.find(row => row.id === selectedProject.value?.id) || null
  }
  refreshListScrollbar()
}

async function fetchOptions() {
  archiveList.value = (await request.get('/projects/archives/options')) as any

  try {
    const dictRes: any = await request.get('/dicts/code/product_line')
    productLineOptions.value = dictRes?.items || []
  } catch {
    productLineOptions.value = []
  }

  try {
    const plRes: any = await request.get('/auth/product-lines')
    allowedProductLines.value = plRes.unrestricted ? null : (plRes.items || [])
  } catch {
    allowedProductLines.value = null
  }

  deptList.value = (await request.get('/depts/tree')) as any
  const flat: any[] = []
  function walk(nodes: any[]) {
    for (const node of nodes) {
      flat.push(node)
      if (node.children?.length) walk(node.children)
    }
  }
  walk(deptList.value)
  deptFlatList.value = flat
  deptNames.value = flat.map((d: any) => d.dept_name)

  const res: any = await request.get('/users', { params: { page: 1, page_size: 1000 } })
  userList.value = res.items
  userNames.value = res.items.map((u: any) => u.real_name)
}

async function fetchSheetFieldMetadata() {
  try {
    const res: any = await request.get('/projects/sheet-fields')
    sheetFieldGroupsMeta.value = normalizeSheetMetadata(res)
  } catch {
    sheetFieldGroupsMeta.value = buildFallbackSheetGroupMetas()
  } finally {
    sheetMetadataLoaded.value = true
  }
}

async function onCellValueChanged(event: CellValueChangedEvent<ProjectRow>) {
  const field = event.colDef.field
  if (!field) return
  await saveProjectField(event.data, field as EditableProjectFieldKey, event.newValue)
}

async function saveProjectField(row: ProjectRow | null | undefined, field: EditableProjectFieldKey, value: any) {
  const projectId = row?.id
  if (!projectId) return

  const updateLocalRow = (patch: Partial<ProjectRow>) => {
    Object.assign(row, patch)
    const storeRow = rowData.value.find(item => item.id === projectId)
    if (storeRow && storeRow !== row) Object.assign(storeRow, patch)
    if (selectedProject.value?.id === projectId) Object.assign(selectedProject.value, patch)
  }

  if (isProgressField(field)) {
    const progressValue = normalizeProgressInput(value)
    await request.put(`/projects/${projectId}`, { [field]: progressValue })
    updateLocalRow({ [field]: progressValue } as Partial<ProjectRow>)
    setSavedText(row)
    return
  }

  if (field === 'status') {
    const statusValue = normalizeStatus(value)
    await request.put(`/projects/${projectId}`, { status: statusValue })
    updateLocalRow({ status: statusValue })
    setSavedText(row)
    return
  }

  if (field === 'dept_name') {
    const dept = deptFlatList.value.find((d: any) => d.dept_name === value)
    if (!dept) return
    await request.put(`/projects/${projectId}`, { dept_id: dept.id })
    updateLocalRow({ dept_id: dept.id, dept_name: dept.dept_name })
    setSavedText(row)
    return
  }

  if (field === 'pm_name') {
    const user = userList.value.find((u: any) => u.real_name === value)
    if (!user) return
    await request.put(`/projects/${projectId}`, { pm_id: user.id })
    updateLocalRow({ pm_id: user.id, pm_name: user.real_name })
    setSavedText(row)
    return
  }

  await request.put(`/projects/${projectId}`, { [field]: value })
  updateLocalRow({ [field]: value } as Partial<ProjectRow>)
  setSavedText(row)
}

function setSavedText(row?: ProjectRow) {
  if (row) {
    selectedProject.value = rowData.value.find(item => item.id === row.id) || row
  }
  const name = row?.project_code || row?.project_name || '项目'
  lastSavedText.value = `${name} 已自动保存`
  ElMessage.success('已自动保存')
  refreshListScrollbar()
}

async function openProjectDrawer(row: ProjectRow) {
  selectedProject.value = rowData.value.find(item => item.id === row.id) || row
  drawerOpenGroups.value = [...drawerDefaultExpandedGroupKeys]
  drawerEditingField.value = null
  drawerEditingFieldData.value = null
  drawerDraftValue.value = null
  sheetDetailGroups.value = buildDrawerGroupsFromRow(selectedProject.value)
  await fetchProjectSheetDetail(row.id)
  await nextTick()
  refreshListScrollbar()
}

async function fetchProjectSheetDetail(projectId: number) {
  sheetDetailLoading.value = true
  try {
    const res: any = await request.get(`/projects/${projectId}/sheet-detail`)
    if (Array.isArray(res?.groups) && res.groups.length) {
      sheetDetailGroups.value = normalizeSheetDetailGroups(res.groups, selectedProject.value)
    }
  } catch {
    if (selectedProject.value) {
      sheetDetailGroups.value = buildDrawerGroupsFromRow(selectedProject.value)
    }
  } finally {
    sheetDetailLoading.value = false
  }
}

function sheetFieldOptions(field: ProjectSheetField): ListFilterOption[] {
  if (field.key === 'node_status') return projectStatusOptions
  return uniqueSheetFieldOptions(field.key)
}

function sheetProgressValue(field: ProjectSheetField) {
  return clampProgress(numberValue(field.value))
}

function formatSheetFieldValue(field: ProjectSheetField, groupKey = field.group) {
  const value = field.value
  if (value == null || value === '') return field.computed ? '待计算' : '-'
  if (field.key === 'node_status') return statusLabel(value as any)
  if (field.value_type === 'progress') return `${sheetProgressValue(field)}%`
  if (field.value_type === 'percent') return `${numberValue(value).toFixed(2)}%`
  if (groupKey === 'progress') return summarizeProgressText(value)
  return String(value)
}

function startSheetFieldEdit(field: ProjectSheetField) {
  if (!selectedProject.value || !field.editable) return
  drawerEditingField.value = field.key
  drawerEditingFieldData.value = field
  drawerDraftValue.value = field.value ?? null
}

function cancelDrawerEdit() {
  drawerEditingField.value = null
  drawerEditingFieldData.value = null
  drawerDraftValue.value = null
}

async function commitDrawerEdit() {
  if (!selectedProject.value || !drawerEditingField.value || !drawerEditingFieldData.value) return
  await saveSheetDetailField(drawerEditingFieldData.value, drawerDraftValue.value)
  cancelDrawerEdit()
}

function patchSheetFieldValue(fieldKey: string, value: unknown) {
  sheetDetailGroups.value = sheetDetailGroups.value.map(group => ({
    ...group,
    fields: group.fields.map(field => field.key === fieldKey ? { ...field, value } : field),
  }))
  const row = rowData.value.find(item => item.id === selectedProject.value?.id)
  if (row) {
    row.sheet_fields = { ...(row.sheet_fields || {}), [fieldKey]: value }
  }
  if (selectedProject.value) {
    selectedProject.value.sheet_fields = { ...(selectedProject.value.sheet_fields || {}), [fieldKey]: value }
  }
}

async function saveSheetDetailField(field: ProjectSheetField, value: any) {
  if (!selectedProject.value) return
  const projectId = selectedProject.value.id
  const projectField = sheetProjectFieldMap[field.key]
  if (field.source_type === 'project' && projectField) {
    await saveProjectField(selectedProject.value, projectField, value)
    patchSheetFieldValue(field.key, value)
    return
  }

  if (field.source_type !== 'detail') return
  const payloadValue = field.value_type === 'progress' ? normalizeProgressInput(value) : value
  const res: any = await request.put(`/projects/${projectId}/sheet-detail`, {
    values: { [field.key]: payloadValue },
  })
  if (Array.isArray(res?.groups) && res.groups.length) {
    sheetDetailGroups.value = normalizeSheetDetailGroups(res.groups, selectedProject.value)
  } else {
    patchSheetFieldValue(field.key, payloadValue)
  }
  setSavedText(selectedProject.value)
}

function onProjectCellDoubleClicked(event: CellDoubleClickedEvent<ProjectRow>) {
  const target = event.event?.target as HTMLElement | null
  if (target?.closest('button')) return
  if (!event.data || !event.colDef.field) return

  const editable = event.colDef.editable
  const canEdit = typeof editable === 'function' ? editable(event as any) : editable === true
  if (!canEdit) return

  const rowIndex = (event as any).rowIndex ?? event.node?.rowIndex
  if (rowIndex == null) return

  event.api.startEditingCell({
    rowIndex,
    colKey: event.column,
  })
}

async function closeProjectDrawer() {
  selectedProject.value = null
  drawerOpenGroups.value = [...drawerDefaultExpandedGroupKeys]
  sheetDetailGroups.value = []
  cancelDrawerEdit()
  await nextTick()
  refreshListScrollbar()
}

function getRowClass(params: RowClassParams<ProjectRow>) {
  return selectedProject.value?.id === params.data?.id ? 'progress-row-active' : ''
}

async function handleRowMenu(row: ProjectRow) {
  try {
    await ElMessageBox.confirm(
      `对项目「${row.project_name}」的操作`,
      '更多操作',
      {
        confirmButtonText: '删除项目',
        cancelButtonText: '打开详情',
        distinguishCancelAndClose: true,
        type: 'warning',
      },
    )
    await handleDelete(row.id)
  } catch (action: any) {
    if (action === 'cancel') {
      openProjectDrawer(row)
    }
  }
}

async function handleDelete(id: number) {
  await ElMessageBox.confirm('确定删除该项目吗？任务数据也将被删除', '提示', { type: 'warning' })
  await request.delete(`/projects/${id}`)
  ElMessage.success('删除成功')
  if (selectedProject.value?.id === id) selectedProject.value = null
  fetchList()
}

function onArchiveChange(archiveId: number) {
  const archive = archiveList.value.find((a: any) => a.id === archiveId)
  if (archive) {
    form.project_code = archive.project_code
    form.project_name = archive.project_name
  }
}

function openCreateDialog() {
  formRef.value?.resetFields()
  Object.assign(form, {
    id: 0,
    archive_id: null,
    project_code: '',
    project_name: '',
    dept_id: 0,
    pm_id: 0,
    status: 1,
    start_date: '',
    end_date: '',
    budget: null,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  await request.post('/projects', {
    archive_id: form.archive_id,
    project_code: form.project_code,
    project_name: form.project_name,
    dept_id: form.dept_id,
    pm_id: form.pm_id,
    status: form.status,
    start_date: form.start_date || null,
    end_date: form.end_date || null,
    budget: form.budget,
  })
  ElMessage.success('创建成功')
  dialogVisible.value = false
  fetchList()
}

onMounted(async () => {
  await Promise.all([fetchOptions(), fetchSheetFieldMetadata()])
  restoreSelectedSheetFieldKeys()
  restoreColumnState()
})
</script>

<style scoped>
.project-progress-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  min-height: 100%;
}

.project-progress-workbench.is-drawer-open {
  grid-template-columns: minmax(0, 1fr) 312px;
}

.progress-list-shell,
.project-list-page {
  min-width: 0;
  min-height: 100%;
}

.progress-view-context {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--pms-border-soft);
}

.progress-view-label {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(79, 70, 229, 0.16);
  border-radius: var(--pms-radius-sm);
  color: var(--pms-primary);
  background: var(--pms-primary-soft);
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}

.progress-save-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--pms-success);
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}

.progress-save-tip::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
}

:deep(.proj-name-cell) {
  color: var(--pms-text);
  font-weight: 650;
}

:deep(.progress-editable-cell) {
  cursor: text;
}

:deep(.progress-editable-cell:hover) {
  background: #f8fbff;
}

:deep(.progress-editable-cell.ag-cell-focus) {
  box-shadow: inset 0 0 0 1px rgba(79, 70, 229, 0.22);
}

:deep(.progress-workbench-grid .progress-row-active .ag-cell) {
  background: #f8faff;
}

:deep(.progress-row-actions) {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  height: 100%;
}

:deep(.progress-detail-btn) {
  height: 24px;
  padding: 0 6px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--pms-primary);
  font-size: 12px;
  font-weight: 650;
  line-height: 24px;
  cursor: pointer;
}

:deep(.progress-detail-btn:hover),
:deep(.progress-detail-btn:focus-visible) {
  background: var(--pms-primary-soft);
  outline: none;
}

:deep(.sheet-column-text) {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-detail-drawer {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--pms-surface);
  border: 1px solid var(--pms-border-soft);
  border-radius: var(--pms-radius);
  box-shadow: var(--pms-shadow-sm);
}

.drawer-head {
  padding: 14px;
  border-bottom: 1px solid var(--pms-border-soft);
}

.drawer-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.drawer-title {
  min-width: 0;
  color: var(--pms-text);
  font-size: 14px;
  font-weight: 750;
  line-height: 1.35;
}

.drawer-close {
  flex: 0 0 auto;
}

.drawer-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 5px;
  color: var(--pms-text-secondary);
  font-family: var(--pms-font-mono);
  font-size: 12px;
}

.drawer-body {
  height: calc(100% - 70px);
  min-height: 0;
  overflow: auto;
  padding: 8px 12px 14px;
}

.drawer-section {
  padding: 6px 2px;
}

.drawer-collapse {
  border-top: 0;
  border-bottom: 0;
}

.drawer-collapse :deep(.el-collapse-item__header) {
  align-items: flex-start;
  height: auto;
  min-height: 42px;
  padding: 10px 0;
  background: transparent;
  border-bottom-color: var(--pms-border-soft);
}

.drawer-collapse :deep(.el-collapse-item__wrap) {
  border-bottom-color: var(--pms-border-soft);
}

.drawer-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 10px;
}

.drawer-group-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  color: var(--pms-text);
  font-size: 13px;
  font-weight: 750;
}

.drawer-field-count {
  color: var(--pms-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.drawer-field-list {
  display: grid;
  gap: 10px;
}

.drawer-field-row {
  position: relative;
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}

.drawer-field-row.is-long-text {
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
}

.drawer-field-row.is-progress {
  align-items: center;
}

.drawer-field-header {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 28px;
  color: var(--pms-text-muted);
}

.drawer-field-row.is-long-text .drawer-field-header {
  min-height: auto;
}

.drawer-field-label {
  font-size: 12px;
  line-height: 1.5;
}

.drawer-field-icon {
  color: var(--pms-text-muted);
  font-size: 13px;
}

.drawer-field-content {
  position: relative;
  min-width: 0;
}

.drawer-field-value-button,
.drawer-field-value-static {
  display: block;
  width: 100%;
  min-height: 28px;
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: var(--pms-text);
  font-size: 12px;
  line-height: 1.6;
  text-align: left;
}

.drawer-field-value-button {
  cursor: pointer;
}

.drawer-field-value-button:hover,
.drawer-field-value-button:focus-visible {
  outline: none;
  color: var(--pms-primary);
}

.drawer-field-text {
  display: block;
  white-space: pre-wrap;
  word-break: break-word;
}

.drawer-field-row:not(.is-long-text) .drawer-field-text {
  white-space: normal;
}

.drawer-field-editor {
  padding: 2px 0;
}

.drawer-editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 6px;
}

.drawer-progress-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 42px;
  align-items: center;
  gap: 8px;
}

.drawer-progress-value {
  color: var(--pms-text);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.drawer-quick-toggle {
  position: absolute;
  top: 2px;
  right: -2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: var(--pms-surface);
  color: var(--pms-primary);
  box-shadow: 0 0 0 1px rgba(79, 70, 229, 0.16);
  opacity: 0;
  transition: opacity 0.16s ease, background-color 0.16s ease;
}

.drawer-field-row:hover .drawer-quick-toggle,
.drawer-field-row:focus-within .drawer-quick-toggle,
.drawer-quick-toggle:focus-visible {
  opacity: 1;
}

.drawer-quick-toggle:hover,
.drawer-quick-toggle:focus-visible {
  background: var(--pms-primary-soft);
  outline: none;
}

@media (hover: none) {
  .drawer-quick-toggle {
    opacity: 1;
  }
}
</style>
