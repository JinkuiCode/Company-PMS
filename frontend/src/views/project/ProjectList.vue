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
        <template #toolbar-left>
          <el-button v-if="hasPermission('project:list:add')" type="primary" size="small" @click="openCreateDialog">
            <el-icon style="margin-right:4px;"><Plus /></el-icon>
            新增项目
          </el-button>
          <PmsListColumnPicker
            v-model="selectedSheetFieldKeys"
            :groups="columnPickerGroups"
            :default-keys="defaultSelectedSheetFieldKeys"
            aria-label="项目进度列设置"
          />
        </template>

        <template #filters>
          <PmsListFilters
            v-model:filters="customFilters"
            :fields="projectListFilterFieldsForView"
            :active-count="activeCustomFilterCount"
          >
            <el-input
              v-if="isProgressPolicyVisible('project_code') || isProgressPolicyVisible('project_name')"
              v-model="filterKeyword"
              placeholder="搜索项目号 / 项目名"
              size="small"
              clearable
              style="width: 210px;"
              :prefix-icon="Search"
            />
            <el-select
              v-if="isProgressPolicyVisible('product_line')"
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
              v-if="isProgressPolicyVisible('node_status')"
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
              v-if="isProgressPolicyVisible('dept_id')"
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
            :defaultColGroupDef="defaultColGroupDef"
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

        <el-dialog v-model="dialogVisible" title="新增项目" width="620px" class="project-create-dialog">
          <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
            <el-form-item v-if="isProgressPolicyVisible('archive_id')" label="项目档案" prop="archive_id">
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
            <el-form-item v-if="isProgressPolicyVisible('project_code')" label="项目编号">
              <el-input v-model="form.project_code" disabled placeholder="由档案自动带出" />
            </el-form-item>
            <el-form-item v-if="isProgressPolicyVisible('project_name')" label="项目名称">
              <el-input v-model="form.project_name" disabled placeholder="由档案自动带出" />
            </el-form-item>
            <el-form-item v-if="isProgressPolicyVisible('dept_id')" label="所属部门" prop="dept_id">
              <el-tree-select
                v-model="form.dept_id"
                style="width: 100%;"
                :data="deptList"
                :props="{ label: 'dept_name', value: 'id', children: 'children' }"
                check-strictly
                :disabled="!isProgressPolicyEditable('dept_id')"
              />
            </el-form-item>
            <el-form-item v-if="isProgressPolicyVisible('pm_id')" label="项目经理" prop="pm_id">
              <el-select v-model="form.pm_id" style="width: 100%;" :disabled="!isProgressPolicyEditable('pm_id')">
                <el-option
                  v-for="u in userList"
                  :key="u.id"
                  :label="u.real_name"
                  :value="u.id"
                />
              </el-select>
            </el-form-item>
            <el-row :gutter="12">
              <el-col v-if="isProgressPolicyVisible('project_start_date')" :span="12">
                <el-form-item label="开始日期" prop="start_date">
                  <el-date-picker
                    v-model="form.start_date"
                    type="date"
                    style="width: 100%;"
                    value-format="YYYY-MM-DD"
                    placeholder="选择日期"
                    :disabled="!isProgressPolicyEditable('project_start_date')"
                  />
                </el-form-item>
              </el-col>
              <el-col v-if="isProgressPolicyVisible('original_planned_ship_date')" :span="12">
                <el-form-item label="结束日期" prop="end_date">
                  <el-date-picker
                    v-model="form.end_date"
                    type="date"
                    style="width: 100%;"
                    value-format="YYYY-MM-DD"
                    placeholder="选择日期"
                    :disabled="!isProgressPolicyEditable('original_planned_ship_date')"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item v-if="isProgressPolicyVisible('budget')" label="预算(万)" prop="budget">
              <el-input-number
                v-model="form.budget"
                :min="0"
                :precision="2"
                style="width: 100%;"
                placeholder="请输入预算"
                :disabled="!isProgressPolicyEditable('budget')"
              />
            </el-form-item>
            <template v-if="dynamicRequiredFields.length || dynamicRequiredProjectFields.length">
              <el-divider content-position="left">业务必填信息</el-divider>
              <el-form-item
                v-for="field in dynamicRequiredProjectFields"
                :key="field.field_key"
                :label="field.label"
                :prop="`project_values.${field.field_key}`"
                :rules="[{ required: true, message: `请填写${field.label}`, trigger: ['blur', 'change'] }]"
              >
                <el-input-number
                  v-if="['number', 'percent', 'progress'].includes(field.value_type)"
                  v-model="form.project_values[field.field_key]"
                  :min="field.value_type === 'progress' ? 0 : undefined"
                  :max="field.value_type === 'progress' ? 100 : undefined"
                  style="width: 100%"
                />
                <el-date-picker
                  v-else-if="field.value_type === 'date' || field.value_type === 'datetime'"
                  v-model="form.project_values[field.field_key]"
                  type="date"
                  value-format="YYYY-MM-DD"
                  style="width: 100%"
                />
                <el-input
                  v-else
                  v-model="form.project_values[field.field_key]"
                  :type="field.value_type === 'long_text' ? 'textarea' : 'text'"
                  :rows="field.value_type === 'long_text' ? 3 : undefined"
                  :placeholder="`请输入${field.label}`"
                />
              </el-form-item>
              <el-form-item
                v-for="field in dynamicRequiredFields"
                :key="field.key"
                :label="field.label"
                :prop="`sheet_values.${field.key}`"
                :rules="[{ required: true, message: `请填写${field.label}`, trigger: ['blur', 'change'] }]"
              >
                <el-select
                  v-if="field.value_type === 'select'"
                  v-model="form.sheet_values[field.key]"
                  filterable
                  style="width: 100%"
                  :placeholder="`请选择${field.label}`"
                >
                  <el-option
                    v-for="option in sheetFieldFilterOptions(field)"
                    :key="String(option.value)"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-input-number
                  v-else-if="['number', 'percent', 'progress'].includes(field.value_type)"
                  v-model="form.sheet_values[field.key]"
                  :min="field.value_type === 'progress' ? 0 : undefined"
                  :max="field.value_type === 'progress' ? 100 : undefined"
                  style="width: 100%"
                />
                <el-date-picker
                  v-else-if="field.value_type === 'date' || field.value_type === 'datetime'"
                  v-model="form.sheet_values[field.key]"
                  type="date"
                  value-format="YYYY-MM-DD"
                  style="width: 100%"
                />
                <el-input
                  v-else
                  v-model="form.sheet_values[field.key]"
                  :type="field.value_type === 'long_text' ? 'textarea' : 'text'"
                  :rows="field.value_type === 'long_text' ? 3 : undefined"
                  :placeholder="`请输入${field.label}`"
                />
              </el-form-item>
            </template>
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
          <div class="drawer-identity">
            <div class="drawer-title">{{ selectedProject.project_name || '-' }}</div>
            <div class="drawer-meta">
              {{ selectedProject.project_code || '-' }}
              <span>·</span>
              {{ productLineLabel(selectedProject.product_line) }}
            </div>
          </div>
          <el-tooltip content="收起项目详情" placement="left">
            <el-button
              class="drawer-close"
              :icon="Close"
              size="small"
              text
              circle
              aria-label="收起项目详情"
              @click="closeProjectDrawer"
            />
          </el-tooltip>
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
                <span class="drawer-group-heading">
                  <span>{{ group.label }}</span>
                  <span
                    v-if="drawerGroupSummary(group)"
                    class="drawer-group-summary"
                  >
                    {{ drawerGroupSummary(group) }}
                  </span>
                </span>
                <span class="drawer-field-count" :aria-label="`${group.label}已填写 ${filledFieldCount(group)} / ${group.fields.length} 项`">
                  {{ filledFieldCount(group) }} / {{ group.fields.length }}
                </span>
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
                    <button
                      type="button"
                      class="drawer-field-reason"
                      :aria-label="`${field.label}：${drawerFieldReason(field)!.tooltip}`"
                    >
                      <el-icon aria-hidden="true">
                        <component :is="drawerFieldReason(field)!.icon" />
                      </el-icon>
                    </button>
                  </el-tooltip>
                </div>

                <div class="drawer-field-content" :class="{ 'has-quick-toggle': canQuickToggleField(field) }">
                  <template v-if="drawerEditingField === field.key">
                    <div
                      class="drawer-field-editor"
                      @keydown.enter.exact="handleDrawerEditorEnter(field, $event)"
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
                      />
                      <el-input
                        v-else
                        v-model="drawerDraftValue"
                        size="small"
                        :placeholder="`输入${field.label}`"
                      />
                    </div>
                  </template>

                  <template v-else>
                    <button
                      v-if="field.editable && hasPermission('project:list:edit')"
                      type="button"
                      class="drawer-field-value-button"
                      :aria-label="`编辑${field.label}`"
                      @click="startSheetFieldEdit(field)"
                    >
                      <template v-if="field.value_type === 'progress' && sheetProgressValue(field) !== null">
                        <span class="drawer-progress-row">
                          <span class="pms-progress-track">
                            <span
                              class="pms-progress-bar"
                              :class="progressToneClass(sheetProgressValue(field) ?? 0)"
                              :style="{ width: `${sheetProgressValue(field)}%` }"
                            ></span>
                          </span>
                          <span class="drawer-progress-value">{{ sheetProgressValue(field) }}%</span>
                        </span>
                      </template>
                      <span v-else :class="field.value_type === 'progress' ? 'drawer-field-empty' : 'drawer-field-text'">{{ formatSheetFieldValue(field) }}</span>
                    </button>
                    <div
                      v-else
                      class="drawer-field-value-static"
                      :aria-label="`${field.label}当前不可改`"
                    >
                      <template v-if="field.value_type === 'progress' && sheetProgressValue(field) !== null">
                        <span class="drawer-progress-row">
                          <span class="pms-progress-track">
                            <span
                              class="pms-progress-bar"
                              :class="progressToneClass(sheetProgressValue(field) ?? 0)"
                              :style="{ width: `${sheetProgressValue(field)}%` }"
                            ></span>
                          </span>
                          <span class="drawer-progress-value">{{ sheetProgressValue(field) }}%</span>
                        </span>
                      </template>
                      <span v-else :class="field.value_type === 'progress' ? 'drawer-field-empty' : 'drawer-field-text'">{{ formatSheetFieldValue(field) }}</span>
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

      <div class="drawer-savebar">
        <el-button
          class="drawer-save"
          type="primary"
          size="small"
          :disabled="!drawerHasPendingChanges || !hasPermission('project:list:edit')"
          :loading="drawerSaving"
          :aria-label="drawerHasPendingChanges ? `保存 ${drawerPendingChangeCount || 1} 项修改` : '没有待保存的修改'"
          @click="saveDrawerChanges"
        >
          保存修改{{ drawerPendingChangeCount ? ` (${drawerPendingChangeCount})` : '' }}
        </el-button>
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
import { loadEnumOptions, type EnumDefinition } from '@/composables/useEnumOptions'
import { useAuthStore } from '@/stores/auth'
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
  visible: boolean
  required: boolean
  computed: boolean
  list_available: boolean
  quick_addable: boolean
  enum_code?: string | null
}

type EffectiveProgressFieldPolicy = {
  field_key: string
  label: string
  value_type: ProjectSheetFieldMeta['value_type'] | 'user' | 'department'
  source_type: ProjectSheetFieldMeta['source_type']
  visible: boolean
  editable: boolean
  required: boolean
  list_available: boolean
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

type DrawerPendingChange = {
  field: ProjectSheetField
  value: unknown
  originalValue: unknown
}

type ColumnPreferenceState = {
  selected_sheet_field_keys: string[]
  columnState: ColumnState[]
}

const localeText = chineseLocaleText
const authStore = useAuthStore()
const hasPermission = authStore.hasPermission
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
const drawerOpenGroups = ref<string[]>([...drawerDefaultExpandedGroupKeys])
const drawerEditingField = ref<string | null>(null)
const drawerEditingFieldData = ref<ProjectSheetField | null>(null)
const drawerDraftValue = ref<unknown>(null)
const drawerPendingChanges = ref<Record<string, DrawerPendingChange>>({})
const drawerSaving = ref(false)
const sheetDetailGroups = ref<ProjectSheetGroup[]>([])
const sheetDetailLoading = ref(false)
const sheetFieldGroupsMeta = ref<ProjectSheetGroupMeta[]>(buildFallbackSheetGroupMetas())
const progressFieldPolicies = ref<Record<string, EffectiveProgressFieldPolicy>>({})
const sheetMetadataLoaded = ref(false)
const selectedSheetFieldKeys = ref<string[]>([])
const columnPreferencesReady = ref(false)
const columnPreferenceWritesEnabled = ref(false)
const columnStateRestored = ref(false)
const columnPreferenceOwnerId = ref<number | null>(null)
const restoringColumnState = ref(false)
const listRequestSerial = ref(0)

const productLineOptions = ref<ListFilterOption[]>([])
const productLineLabelMap = reactive<Record<string, string>>({})
const allowedProductLines = ref<string[] | null>(null)
const projectStatusOptions = reactive<ListFilterOption[]>([])
const projectStatusLabelMap = reactive<Record<string, string>>({})
const sheetEnumDefinitions = reactive<Record<string, EnumDefinition>>({})
const projectStatusEditorValues = computed(() => projectStatusOptions.map(item => item.value))

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

const dynamicRequiredFields = computed(() => sheetFieldMetas.value.filter(field => (
  field.visible && field.required && field.editable && field.source_type === 'detail'
)))
const handledCreatePolicyFields = new Set([
  'archive_id',
  'dept_id',
  'pm_id',
  'node_status',
  'project_start_date',
  'original_planned_ship_date',
  'budget',
])
const dynamicRequiredProjectFields = computed(() => Object.values(progressFieldPolicies.value).filter(field => (
  field.visible
  && field.required
  && field.editable
  && field.source_type === 'project'
  && !handledCreatePolicyFields.has(field.field_key)
)))

const defaultSelectedSheetFieldKeys = computed<string[]>(() => [])
const drawerPendingChangeCount = computed(() => Object.keys(drawerPendingChanges.value).length)
const drawerHasPendingChanges = computed(() => drawerPendingChangeCount.value > 0 || Boolean(drawerEditingField.value))

const columnPickerGroups = computed(() => {
  return sheetFieldGroupsMeta.value.map(group => ({
    key: group.key,
    label: group.label,
    fields: group.fields.filter(field => field.list_available),
  }))
})

const projectListFilterFields = computed<ListFilterField<ProjectRow>[]>(() => {
  const fixedFields = ([
    { field: 'project_code', policyKey: 'project_code', label: '项目编号', type: 'text' },
    { field: 'project_name', policyKey: 'project_name', label: '项目名称', type: 'text' },
    { field: 'product_line', policyKey: 'product_line', label: '产品类', type: 'select', options: () => filteredProductLineOptions.value },
    { field: 'status', policyKey: 'node_status', label: '节点', type: 'select', options: () => projectStatusOptions },
    { field: 'dept_name', policyKey: 'dept_id', label: '所属部门', type: 'select', options: () => deptNameOptions.value },
    { field: 'pm_name', policyKey: 'pm_id', label: '负责人', type: 'select', options: () => userNameFilterOptions.value },
    { field: 'total_progress', label: '总进度', type: 'number' },
    { field: 'budget', policyKey: 'budget', label: '预算', type: 'number' },
    { field: 'start_date', policyKey: 'project_start_date', label: '立项日期', type: 'date' },
    { field: 'end_date', policyKey: 'original_planned_ship_date', label: '原计划发货', type: 'date' },
  ] as Array<ListFilterField<ProjectRow> & { policyKey?: string }>).filter(
    field => !field.policyKey || isProgressPolicyVisible(field.policyKey),
  )

  const dynamicFields = sheetFieldMetas.value.filter(field => field.list_available).map<ListFilterField<ProjectRow>>((field) => ({
    field: field.key,
    label: `${sheetGroupLabel(field.group)} / ${field.label}`,
    type: toListFilterType(field.value_type),
    getValue: row => row.sheet_fields?.[field.key],
    options: field.value_type === 'select'
      ? () => sheetFieldFilterOptions(field)
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
  () => columnPreferencesReady.value ? requestedSheetFieldKeys.value.join(',') : '__pending__',
  (signature) => {
    if (signature === '__pending__') return
    fetchList()
  },
  { immediate: true },
)

watch(
  () => selectedSheetFieldKeys.value.join(','),
  () => {
    if (!columnPreferenceWritesEnabled.value) return
    persistColumnPreferences()
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
  project_values: {} as Record<string, any>,
  sheet_values: {} as Record<string, any>,
})

const rules = computed<FormRules>(() => {
  const nextRules: FormRules = {
    archive_id: [{ required: true, message: '请选择项目档案', trigger: 'change' }],
    dept_id: [{ required: true, message: '请选择部门', trigger: 'change' }],
    pm_id: [{ required: true, message: '请选择项目经理', trigger: 'change' }],
  }
  const configurableFields = [
    { policyKey: 'project_start_date', formKey: 'start_date', label: '开始日期' },
    { policyKey: 'original_planned_ship_date', formKey: 'end_date', label: '结束日期' },
    { policyKey: 'budget', formKey: 'budget', label: '预算' },
  ]
  configurableFields.forEach(({ policyKey, formKey, label }) => {
    if (progressPolicy(policyKey)?.required && isProgressPolicyVisible(policyKey)) {
      nextRules[formKey] = [{ required: true, message: `请填写${label}`, trigger: ['blur', 'change'] }]
    }
  })
  return nextRules
})

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
    visible: rawField.visible !== false,
    required: Boolean(rawField.required),
    computed: Boolean(rawField.computed),
    list_available: Boolean(rawField.list_available),
    quick_addable: Boolean(rawField.quick_addable),
    enum_code: rawField.enum_code ? String(rawField.enum_code) : null,
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

function progressPolicy(fieldKey: string) {
  return progressFieldPolicies.value[fieldKey]
}

function isProgressPolicyVisible(fieldKey: string) {
  return progressPolicy(fieldKey)?.visible !== false
}

function isProgressPolicyEditable(fieldKey: string) {
  return progressPolicy(fieldKey)?.editable !== false
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

function normalizeProjectRow(row: ProjectRow) {
  return {
    ...row,
    sheet_fields: row.sheet_fields && typeof row.sheet_fields === 'object' ? { ...row.sheet_fields } : {},
  }
}

function renderProgressBar(value: number | null | undefined) {
  if (value == null) return '<span class="pms-progress-empty">-</span>'
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
  return (params: any) => renderProgressBar(params.data?.[field] ?? null)
}

function parseProgressEditValue(params: any) {
  return normalizeProgressInput(params.newValue)
}

function normalizeStatus(value: number | string | null | undefined) {
  if (typeof value === 'number') return value
  const option = projectStatusOptions.find(item => item.label === value)
  if (option) return Number(option.value)
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 1
}

function statusLabel(value: number | string | null | undefined) {
  return projectStatusLabelMap[String(normalizeStatus(value))] || '-'
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
  const text = String(value ?? '').split(/\r?\n/, 1)[0].trim().replace(/\s+/g, ' ')
  if (!text) return '-'
  if (text.length <= progressSummaryMaxLength) return text
  return `${text.slice(0, progressSummaryMaxLength)}...`
}

function drawerGroupSummary(group: ProjectSheetGroup) {
  if (group.key !== 'progress') return ''
  const summaryField = group.fields.find(field => field.value_type === 'long_text' && field.value != null && field.value !== '')
    || group.fields.find(field => field.value != null && field.value !== '')
  return summaryField ? summarizeProgressText(summaryField.value) : ''
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
          tooltipValueGetter: (params: any) => formatSheetFieldValue({ ...field, value: sheetFieldValue(params.data, field.key) }),
          cellRenderer: (params: any) => {
            const value = sheetFieldValue(params.data, field.key)
            if (field.value_type === 'progress') {
              return renderProgressBar(value == null || value === '' ? null : clampProgress(numberValue(value)))
            }
            const text = formatSheetFieldValue({ ...field, value })
            return `<span class="sheet-column-text">${escapeHtml(text)}</span>`
          },
        })),
      } satisfies ColGroupDef<ProjectRow>
    })
    .filter(Boolean) as Array<ColDef<ProjectRow> | ColGroupDef<ProjectRow>>
}

const actionColumnWidth = computed(() => hasPermission('project:list:delete') ? 88 : 60)

const columnDefs = computed<Array<ColDef<ProjectRow> | ColGroupDef<ProjectRow>>>(() => [
  { field: 'project_code', headerName: '项目号', width: 112, pinned: 'left', filter: false, hide: !isProgressPolicyVisible('project_code') },
  {
    field: 'project_name',
    headerName: '项目名称',
    width: 190,
    minWidth: 150,
    pinned: 'left',
    hide: !isProgressPolicyVisible('project_name'),
    cellRenderer: (params: any) => `<span class="proj-name-cell">${escapeHtml(params.value || '-')}</span>`,
  },
  {
    field: 'product_line', headerName: '产品类', width: 100, hide: !isProgressPolicyVisible('product_line'),
    valueFormatter: (params: any) => productLineLabel(params.value),
  },
  {
    field: 'status',
    headerName: '节点',
    width: 102,
    hide: !isProgressPolicyVisible('node_status'),
    editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('node_status'),
    cellEditor: 'agSelectCellEditor',
    valueFormatter: (params: any) => statusLabel(params.value),
    cellEditorParams: () => ({ values: projectStatusEditorValues.value }),
    cellRenderer: (params: any) => {
      const tone = statusTone(params.value)
      const label = escapeHtml(statusLabel(params.value))
      return `<span class="pms-status pms-status-${tone}"><span class="pms-status-dot"></span>${label}</span>`
    },
  },
  {
    field: 'end_date',
    headerName: '原计划发货',
    width: 122,
    hide: !isProgressPolicyVisible('original_planned_ship_date'),
    editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('original_planned_ship_date'),
    cellEditor: 'agTextCellEditor',
  },
  {
    headerName: '项目进度',
    marryChildren: true,
    children: [
      { field: 'design_progress', headerName: '设计进度', width: 112, hide: !isProgressPolicyVisible('design_progress'), editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('design_progress'), cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('design_progress') },
      { field: 'order_progress', headerName: '下单进度', width: 112, hide: !isProgressPolicyVisible('order_progress'), editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('order_progress'), cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('order_progress') },
      { field: 'kit_progress', headerName: '齐套进度', width: 112, hide: !isProgressPolicyVisible('kit_progress'), editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('kit_progress'), cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('kit_progress') },
      { field: 'frame_progress', headerName: '框架进度', width: 112, hide: !isProgressPolicyVisible('frame_progress'), editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('frame_progress'), cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('frame_progress') },
      { field: 'dryer_progress', headerName: 'dryer进度', width: 112, hide: !isProgressPolicyVisible('dryer_progress'), editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('dryer_progress'), cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('dryer_progress') },
      { field: 'assembly_progress', headerName: '组装进度', width: 112, hide: !isProgressPolicyVisible('assembly_progress'), editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('assembly_progress'), cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('assembly_progress') },
      { field: 'test_progress', headerName: '测试进度', width: 112, hide: !isProgressPolicyVisible('test_progress'), editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('test_progress'), cellEditor: 'agNumberCellEditor', valueParser: parseProgressEditValue, cellRenderer: renderStageProgress('test_progress') },
    ].filter(column => column.hide !== true),
  },
  {
    headerName: '成员 / 配置',
    marryChildren: true,
    children: [
      {
        field: 'pm_name',
        headerName: '负责人',
        width: 112,
        hide: !isProgressPolicyVisible('pm_id'),
        editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('pm_id'),
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: () => ({ values: userNames.value }),
      },
      {
        field: 'dept_name',
        headerName: '所属部门',
        width: 124,
        hide: !isProgressPolicyVisible('dept_id'),
        editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('dept_id'),
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: () => ({ values: deptNames.value }),
      },
      { field: 'budget', headerName: '预算(万)', width: 110, hide: !isProgressPolicyVisible('budget'), editable: () => hasPermission('project:list:edit') && isProgressPolicyEditable('budget'), type: 'numericColumn' },
    ].filter(column => column.hide !== true),
  },
  ...dynamicColumnDefs(),
  {
    headerName: '操作',
    width: actionColumnWidth.value,
    minWidth: actionColumnWidth.value,
    maxWidth: actionColumnWidth.value,
    pinned: 'right',
    filter: false,
    sortable: false,
    resizable: false,
    cellClass: 'progress-actions-cell',
    cellRenderer: () => `
      <span class="progress-row-actions">
        <button class="progress-detail-btn detail-btn" type="button" title="打开详情" aria-label="打开详情">详情</button>
        ${hasPermission('project:list:delete') ? '<button class="pms-more-btn more-btn" type="button" title="更多操作" aria-label="更多操作"></button>' : ''}
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
  headerClass: 'progress-list-header-center',
  cellClassRules: {
    'progress-editable-cell': params => {
      const editable = params.colDef.editable
      return typeof editable === 'function' ? Boolean(editable(params as any)) : editable === true
    },
  },
}

const defaultColGroupDef: Partial<ColGroupDef<ProjectRow>> = {
  headerClass: 'progress-list-header-center',
}

function refreshListScrollbar() {
  nextTick(() => projectListRef.value?.refreshScrollbar())
}

function columnPreferenceStorageKey() {
  if (columnPreferenceOwnerId.value == null) return null
  return `${COLUMN_STORAGE_KEY}:${columnPreferenceOwnerId.value}`
}

async function resolveColumnPreferenceOwner() {
  if (!authStore.user) {
    try {
      await authStore.fetchUser()
    } catch {
      return
    }
  }
  columnPreferenceOwnerId.value = authStore.user?.id ?? null
}

function readStoredColumnPreferences(): ColumnPreferenceState | null {
  const storageKey = columnPreferenceStorageKey()
  if (!storageKey) return null
  const raw = localStorage.getItem(storageKey)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function persistColumnPreferences() {
  if (!columnPreferencesReady.value || !columnPreferenceWritesEnabled.value) return
  const storageKey = columnPreferenceStorageKey()
  if (!storageKey) return
  const state: ColumnPreferenceState = {
    selected_sheet_field_keys: [...selectedSheetFieldKeys.value],
    columnState: gridApi.value?.getColumnState?.() || [],
  }
  localStorage.setItem(storageKey, JSON.stringify(state))
}

function restoreColumnState() {
  if (!columnPreferencesReady.value || !gridApi.value || columnStateRestored.value) return
  columnStateRestored.value = true
  const saved = readStoredColumnPreferences()
  if (!saved?.columnState?.length) return
  restoringColumnState.value = true
  try {
    const availableSheetIds = new Set(sheetFieldMetas.value.filter(field => field.list_available).map(field => sheetColumnId(field.key)))
    const sanitizedState = saved.columnState.filter((state) => {
      if (!state.colId.startsWith('sheet:')) return true
      return availableSheetIds.has(state.colId)
    })
    gridApi.value.applyColumnState({ state: sanitizedState, applyOrder: true })
  } finally {
    restoringColumnState.value = false
  }
  refreshListScrollbar()
}

function restoreSelectedSheetFieldKeys() {
  const saved = readStoredColumnPreferences()
  const availableKeys = new Set(sheetFieldMetas.value.filter(field => field.list_available).map(field => field.key))
  const savedKeys = Array.isArray(saved?.selected_sheet_field_keys)
    ? saved.selected_sheet_field_keys.filter(key => availableKeys.has(key))
    : [...defaultSelectedSheetFieldKeys.value]
  selectedSheetFieldKeys.value = savedKeys
}

function completeColumnPreferenceRestore() {
  if (!columnPreferencesReady.value || !gridApi.value) return
  restoreColumnState()
  columnPreferenceWritesEnabled.value = true
}

function onGridReady(params: GridReadyEvent<ProjectRow>) {
  gridApi.value = params.api
  completeColumnPreferenceRestore()
  refreshListScrollbar()
}

function handleGridStructureChanged() {
  refreshListScrollbar()
  if (!columnPreferenceWritesEnabled.value || restoringColumnState.value) return
  persistColumnPreferences()
}

function handleColumnResized(event: any) {
  refreshListScrollbar()
  if (!event?.finished || !columnPreferenceWritesEnabled.value || restoringColumnState.value) return
  persistColumnPreferences()
}

async function fetchList() {
  const requestSerial = ++listRequestSerial.value
  const params: Record<string, unknown> = { page: 1, page_size: 1000 }
  if (requestedSheetFieldKeys.value.length) {
    params.sheet_field_keys = requestedSheetFieldKeys.value.join(',')
  }
  const res: any = await request.get('/projects', { params })
  if (requestSerial !== listRequestSerial.value) return
  rowData.value = res.items.map(normalizeProjectRow)
  serverTotal.value = res.total
  if (selectedProject.value) {
    selectedProject.value = rowData.value.find(row => row.id === selectedProject.value?.id) || null
  }
  refreshListScrollbar()
}

async function fetchOptions() {
  archiveList.value = (await request.get('/projects/archives/options')) as any

  try {
    const [productLineDefinition, projectStatusDefinition] = await Promise.all([
      loadEnumOptions('product_line'),
      loadEnumOptions('project_status'),
    ])
    productLineOptions.value = productLineDefinition.items
    Object.keys(productLineLabelMap).forEach(key => delete productLineLabelMap[key])
    Object.assign(productLineLabelMap, productLineDefinition.label_map)
    projectStatusOptions.splice(
      0,
      projectStatusOptions.length,
      ...projectStatusDefinition.items.map(item => ({ label: item.label, value: Number(item.value) })),
    )
    Object.keys(projectStatusLabelMap).forEach(key => delete projectStatusLabelMap[key])
    Object.assign(projectStatusLabelMap, projectStatusDefinition.label_map)
  } catch {
    productLineOptions.value = []
    projectStatusOptions.splice(0)
  }

  try {
    const plRes: any = await request.get('/auth/product-lines')
    allowedProductLines.value = plRes.unrestricted ? null : (plRes.items || [])
  } catch {
    allowedProductLines.value = null
  }

  const deptOptions = (await request.get('/depts/options')) as any[]
  const deptMap = new Map(deptOptions.map(item => [item.id, { ...item, children: [] as any[] }]))
  const roots: any[] = []
  deptMap.forEach((item) => {
    const parent = deptMap.get(item.parent_id)
    if (parent) parent.children.push(item)
    else roots.push(item)
  })
  deptList.value = roots
  const flat = deptOptions
  deptFlatList.value = flat
  deptNames.value = flat.map((d: any) => d.dept_name)

  const users: any = await request.get('/users/options')
  userList.value = users
  userNames.value = users.map((u: any) => u.real_name)
}

async function fetchSheetFieldMetadata() {
  try {
    const res: any = await request.get('/projects/sheet-fields')
    progressFieldPolicies.value = Object.fromEntries(
      (Array.isArray(res?.policies) ? res.policies : []).map((field: EffectiveProgressFieldPolicy) => [field.field_key, field]),
    )
    sheetFieldGroupsMeta.value = normalizeSheetMetadata(res)
    await loadSheetFieldEnums()
  } catch {
    progressFieldPolicies.value = {}
    sheetFieldGroupsMeta.value = buildFallbackSheetGroupMetas()
  } finally {
    sheetMetadataLoaded.value = true
  }
}

async function loadSheetFieldEnums() {
  const enumCodes = Array.from(new Set(
    sheetFieldMetas.value.map(field => field.enum_code).filter((code): code is string => Boolean(code)),
  ))
  const definitions = await Promise.all(enumCodes.map(code => loadEnumOptions(code)))
  definitions.forEach(definition => {
    sheetEnumDefinitions[definition.dict_code] = definition
  })
}

async function onCellValueChanged(event: CellValueChangedEvent<ProjectRow>) {
  const field = event.colDef.field
  if (!field) return
  try {
    await saveProjectField(event.data, field as EditableProjectFieldKey, event.newValue)
  } catch {
    ;(event.data as any)[field] = event.oldValue
    event.api.refreshCells({
      rowNodes: event.node ? [event.node] : undefined,
      columns: event.column ? [event.column] : undefined,
      force: true,
    })
  }
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
  void row
  ElMessage.success('已自动保存')
  refreshListScrollbar()
}

async function openProjectDrawer(row: ProjectRow) {
  selectedProject.value = rowData.value.find(item => item.id === row.id) || row
  drawerOpenGroups.value = [...drawerDefaultExpandedGroupKeys]
  drawerEditingField.value = null
  drawerEditingFieldData.value = null
  drawerDraftValue.value = null
  drawerPendingChanges.value = {}
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
  if (field.enum_code && sheetEnumDefinitions[field.enum_code]) {
    const numeric = typeof field.value === 'number'
    return sheetEnumDefinitions[field.enum_code].items.map(item => ({
      label: item.label,
      value: numeric ? Number(item.value) : item.value,
    }))
  }
  return uniqueSheetFieldOptions(field.key)
}

function sheetFieldFilterOptions(field: ProjectSheetFieldMeta): ListFilterOption[] {
  if (field.enum_code && sheetEnumDefinitions[field.enum_code]) {
    return sheetEnumDefinitions[field.enum_code].items
  }
  return uniqueSheetFieldOptions(field.key)
}

function sheetProgressValue(field: ProjectSheetField) {
  if (field.value == null || field.value === '') return null
  return clampProgress(numberValue(field.value))
}

function formatSheetFieldValue(field: ProjectSheetField) {
  const value = field.value
  if (value == null || value === '') return field.computed ? '待计算' : '-'
  if (field.enum_code) {
    return sheetEnumDefinitions[field.enum_code]?.label_map?.[String(value)] || String(value)
  }
  if (field.value_type === 'progress') return `${sheetProgressValue(field)}%`
  if (field.value_type === 'percent') return `${numberValue(value).toFixed(2)}%`
  return String(value)
}

function productLineLabel(value: unknown) {
  if (value === null || value === undefined || value === '') return '未设置产品类'
  return productLineLabelMap[String(value)] || String(value)
}

function startSheetFieldEdit(field: ProjectSheetField) {
  if (!selectedProject.value || !field.editable || !hasPermission('project:list:edit')) return
  if (drawerEditingField.value && drawerEditingField.value !== field.key) {
    commitDrawerEdit()
  }
  drawerEditingField.value = field.key
  drawerEditingFieldData.value = field
  drawerDraftValue.value = drawerPendingChanges.value[field.key]?.value ?? field.value ?? null
}

function cancelDrawerEdit() {
  drawerEditingField.value = null
  drawerEditingFieldData.value = null
  drawerDraftValue.value = null
}

function normalizeDrawerFieldValue(field: ProjectSheetField, value: unknown) {
  if (field.value_type === 'progress') return normalizeProgressInput(value)
  if (field.value_type === 'number' || field.value_type === 'percent') {
    return value === '' || value == null ? null : Number(value)
  }
  return value ?? ''
}

function isSameDrawerValue(left: unknown, right: unknown) {
  return String(left ?? '') === String(right ?? '')
}

function commitDrawerEdit() {
  if (!selectedProject.value || !drawerEditingField.value || !drawerEditingFieldData.value) return
  const field = drawerEditingFieldData.value
  const existingChange = drawerPendingChanges.value[field.key]
  const originalValue = existingChange?.originalValue ?? field.value
  const value = normalizeDrawerFieldValue(field, drawerDraftValue.value)

  if (isSameDrawerValue(value, originalValue)) {
    const nextChanges = { ...drawerPendingChanges.value }
    delete nextChanges[field.key]
    drawerPendingChanges.value = nextChanges
  } else {
    drawerPendingChanges.value = {
      ...drawerPendingChanges.value,
      [field.key]: { field, value, originalValue },
    }
  }
  patchSheetFieldValue(field.key, value)
  cancelDrawerEdit()
}

function handleDrawerEditorEnter(field: ProjectSheetField, event: KeyboardEvent) {
  if (field.value_type === 'long_text') return
  event.preventDefault()
  commitDrawerEdit()
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

function drawerProjectPayloadValue(projectField: EditableProjectFieldKey, value: unknown) {
  if (isProgressField(projectField)) return normalizeProgressInput(value)
  if (projectField === 'status') return normalizeStatus(value as number | string | null | undefined)
  return value
}

async function saveDrawerChanges() {
  if (!selectedProject.value || drawerSaving.value || !hasPermission('project:list:edit')) return
  if (drawerEditingField.value) commitDrawerEdit()
  if (!drawerPendingChangeCount.value) return

  const projectValues: Partial<Record<EditableProjectFieldKey, unknown>> = {}
  const detailValues: Record<string, unknown> = {}
  Object.values(drawerPendingChanges.value).forEach(({ field, value }) => {
    const projectField = sheetProjectFieldMap[field.key]
    if (field.source_type === 'project' && projectField) {
      projectValues[projectField] = drawerProjectPayloadValue(projectField, value)
    } else if (field.source_type === 'detail') {
      detailValues[field.key] = value
    }
  })

  const savedCount = drawerPendingChangeCount.value
  drawerSaving.value = true
  try {
    await request.put(`/projects/${selectedProject.value.id}/sheet-detail`, { values: detailValues, project_values: projectValues })
    drawerPendingChanges.value = {}
    await fetchList()
    if (selectedProject.value) await fetchProjectSheetDetail(selectedProject.value.id)
    ElMessage.success(`已保存 ${savedCount} 项修改`)
  } catch {
    ElMessage.error('保存失败，草稿已保留')
  } finally {
    drawerSaving.value = false
  }
}

function onProjectCellDoubleClicked(event: CellDoubleClickedEvent<ProjectRow>) {
  if (!hasPermission('project:list:edit')) return
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
  if (drawerEditingField.value) commitDrawerEdit()
  if (drawerPendingChangeCount.value) {
    try {
      await ElMessageBox.confirm('当前抽屉有未保存的修改。', '未保存修改', {
        confirmButtonText: '保存并收起',
        cancelButtonText: '放弃修改',
        distinguishCancelAndClose: true,
        type: 'warning',
      })
      await saveDrawerChanges()
      if (drawerPendingChangeCount.value) return
    } catch (action: any) {
      if (action !== 'cancel') return
      drawerPendingChanges.value = {}
      await fetchList()
      if (selectedProject.value) await fetchProjectSheetDetail(selectedProject.value.id)
    }
  }
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
  if (!hasPermission('project:list:delete')) {
    openProjectDrawer(row)
    return
  }
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
  if (!hasPermission('project:list:delete')) return
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
  if (!hasPermission('project:list:add')) return
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
    project_values: {},
    sheet_values: {},
  })
  dialogVisible.value = true
}

function policyValidationFieldKeys(error: any): string[] {
  const detail = error?.response?.data?.detail
  if (!['FIELD_POLICY_VALIDATION_FAILED', 'FIELD_POLICY_INVALID'].includes(detail?.code)) return []
  if (!Array.isArray(detail?.fields)) return []
  return detail.fields
    .map((field: any) => String(field?.field_key || '').trim())
    .filter(Boolean)
}

async function focusProjectPolicyValidation(error: any) {
  const fieldKeys = policyValidationFieldKeys(error)
  if (!fieldKeys.length) return

  await fetchSheetFieldMetadata()
  await nextTick()
  const directFieldMap: Record<string, string> = {
    archive_id: 'archive_id',
    dept_id: 'dept_id',
    pm_id: 'pm_id',
    project_start_date: 'start_date',
    original_planned_ship_date: 'end_date',
    budget: 'budget',
  }
  const props = fieldKeys.map((fieldKey) => {
    if (directFieldMap[fieldKey]) return directFieldMap[fieldKey]
    const sheetField = sheetFieldMetaMap.value.get(fieldKey)
    if (sheetField?.source_type === 'detail') return `sheet_values.${fieldKey}`
    if (progressPolicy(fieldKey)?.source_type === 'project') return `project_values.${fieldKey}`
    return ''
  }).filter(Boolean)
  if (!props.length) return

  await formRef.value?.validateField(props).catch(() => false)
  formRef.value?.scrollToField(props[0])
}

async function handleSubmit() {
  if (!hasPermission('project:list:add')) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  const payload: Record<string, unknown> = {
    archive_id: form.archive_id,
    project_code: form.project_code,
    project_name: form.project_name,
    dept_id: form.dept_id,
    pm_id: form.pm_id,
    ...form.project_values,
    sheet_values: { ...form.sheet_values },
  }
  if (isProgressPolicyEditable('node_status')) payload.status = form.status
  if (isProgressPolicyEditable('project_start_date')) payload.start_date = form.start_date || null
  if (isProgressPolicyEditable('original_planned_ship_date')) payload.end_date = form.end_date || null
  if (isProgressPolicyEditable('budget')) payload.budget = form.budget
  try {
    await request.post('/projects', payload)
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchList()
  } catch (error) {
    await focusProjectPolicyValidation(error)
  }
}

onMounted(async () => {
  await Promise.all([fetchOptions(), fetchSheetFieldMetadata(), resolveColumnPreferenceOwner()])
  restoreSelectedSheetFieldKeys()
  columnPreferencesReady.value = true
  await nextTick()
  completeColumnPreferenceRestore()
})
</script>

<style scoped>
.project-progress-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.project-progress-workbench.is-drawer-open {
  grid-template-columns: minmax(0, 1fr) 312px;
}

.progress-list-shell,
.project-list-page {
  min-width: 0;
  min-height: 0;
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

:deep(.progress-workbench-grid .ag-cell-inline-editing) {
  padding: 0;
  border: 0;
  border-radius: 0;
  box-shadow: inset 0 0 0 1px rgba(79, 70, 229, 0.42);
  background: #f8fbff;
}

:deep(.progress-workbench-grid .ag-cell-inline-editing .ag-cell-edit-wrapper),
:deep(.progress-workbench-grid .ag-cell-inline-editing .ag-cell-editor),
:deep(.progress-workbench-grid .ag-cell-inline-editing .ag-cell-editor .ag-wrapper),
:deep(.progress-workbench-grid .ag-cell-inline-editing .ag-cell-editor input),
:deep(.progress-workbench-grid .ag-cell-inline-editing .ag-picker-field-wrapper) {
  width: 100%;
  min-height: 100%;
  height: 100%;
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

:deep(.progress-list-header-center .ag-header-cell-label),
:deep(.progress-list-header-center .ag-header-group-cell-label) {
  justify-content: center;
}

:deep(.progress-row-actions) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 100%;
}

:deep(.progress-actions-cell) {
  padding-right: 4px !important;
  padding-left: 4px !important;
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

:deep(.pms-progress-empty) {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  color: var(--pms-text-muted);
  font-variant-numeric: tabular-nums;
}

.progress-detail-drawer {
  display: flex;
  flex-direction: column;
  height: 100%;
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

.drawer-identity {
  flex: 1 1 auto;
  min-width: 0;
}

.drawer-title {
  min-width: 0;
  color: var(--pms-text);
  font-size: 14px;
  font-weight: 750;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.drawer-close {
  flex: 0 0 auto;
  margin-top: -2px;
}

.drawer-save {
  width: 100%;
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
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding: 8px 12px;
  padding-bottom: 16px;
}

.drawer-savebar {
  flex: 0 0 auto;
  padding: 10px 12px;
  border-top: 1px solid var(--pms-border-soft);
  background: var(--pms-surface);
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

.drawer-group-heading {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.drawer-group-summary {
  min-width: 0;
  overflow: hidden;
  color: var(--pms-text-muted);
  font-size: 12px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-field-count {
  color: var(--pms-text-muted);
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
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
  position: relative;
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
  padding-right: 20px;
  font-size: 12px;
  line-height: 1.5;
}

.drawer-field-reason {
  position: absolute;
  top: 50%;
  right: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: 0;
  border-radius: var(--pms-radius-sm);
  background: transparent;
  color: var(--pms-text-muted);
  font-size: 13px;
  cursor: help;
  transform: translateY(-50%);
}

.drawer-field-reason:hover,
.drawer-field-reason:focus-visible {
  color: var(--pms-primary);
  background: var(--pms-primary-soft);
  outline: none;
}

.drawer-field-content {
  position: relative;
  min-width: 0;
}

.drawer-field-content.has-quick-toggle .drawer-field-value-button,
.drawer-field-content.has-quick-toggle .drawer-field-value-static {
  padding-right: 28px;
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

.drawer-field-empty {
  display: block;
  min-height: 28px;
  padding: 4px 0;
  color: var(--pms-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.drawer-field-row:not(.is-long-text) .drawer-field-text {
  white-space: normal;
}

.drawer-field-editor {
  padding: 2px 0;
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
  right: 0;
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
</style>
