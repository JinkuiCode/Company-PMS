<template>
  <div class="pms-list-filter-section">
    <div class="filter-bar pms-filter-bar pms-list-filter-bar">
      <slot />
      <el-button size="small" plain @click="handleAddFilter">
        <el-icon style="margin-right:4px;"><Filter /></el-icon>
        添加筛选
      </el-button>
      <el-button v-if="filters.length" size="small" text @click="emit('update:filters', [])">
        清空筛选
      </el-button>
      <span v-if="activeCount" class="pms-list-filter-summary">
        已启用 {{ activeCount }} 个自定义条件
      </span>
    </div>

    <div v-if="filters.length" class="pms-list-custom-filters" aria-label="自定义筛选条件">
      <div v-for="filter in filters" :key="filter.id" class="pms-list-custom-filter-row">
        <el-select
          :model-value="filter.field"
          size="small"
          style="width: 132px;"
          @update:model-value="handleFieldModelChange(filter.id, $event)"
        >
          <el-option
            v-for="field in fields"
            :key="field.field"
            :label="field.label"
            :value="field.field"
          />
        </el-select>
        <el-select
          :model-value="filter.operator"
          size="small"
          style="width: 96px;"
          @update:model-value="handleOperatorModelChange(filter.id, $event)"
        >
          <el-option
            v-for="operator in getOperators(filter.field)"
            :key="operator"
            :label="listFilterOperatorLabels[operator]"
            :value="operator"
          />
        </el-select>
        <template v-if="getField(filter.field)?.type === 'select'">
          <el-select
            :model-value="filter.value"
            size="small"
            clearable
            filterable
            placeholder="选择值"
            style="width: 164px;"
            @update:model-value="handleValueChange(filter.id, $event)"
          >
            <el-option
              v-for="option in getOptions(filter.field)"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </template>
        <template v-else-if="getField(filter.field)?.type === 'date'">
          <div v-if="filter.operator === 'between'" class="pms-list-filter-range">
            <el-date-picker
              :model-value="filter.value"
              type="date"
              size="small"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
              style="width: 136px;"
              @update:model-value="handleValueChange(filter.id, $event)"
            />
            <span class="pms-list-filter-separator">至</span>
            <el-date-picker
              :model-value="filter.valueEnd"
              type="date"
              size="small"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
              style="width: 136px;"
              @update:model-value="handleValueEndChange(filter.id, $event)"
            />
          </div>
          <el-date-picker
            v-else
            :model-value="filter.value"
            type="date"
            size="small"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 150px;"
            @update:model-value="handleValueChange(filter.id, $event)"
          />
        </template>
        <template v-else-if="getField(filter.field)?.type === 'number'">
          <div v-if="filter.operator === 'between'" class="pms-list-filter-range">
            <el-input-number
              :model-value="filter.value as number | null"
              size="small"
              placeholder="最小值"
              style="width: 120px;"
              @update:model-value="handleValueChange(filter.id, $event)"
            />
            <span class="pms-list-filter-separator">至</span>
            <el-input-number
              :model-value="filter.valueEnd as number | null"
              size="small"
              placeholder="最大值"
              style="width: 120px;"
              @update:model-value="handleValueEndChange(filter.id, $event)"
            />
          </div>
          <el-input-number
            v-else
            :model-value="filter.value as number | null"
            size="small"
            placeholder="输入数值"
            style="width: 140px;"
            @update:model-value="handleValueChange(filter.id, $event)"
          />
        </template>
        <el-input
          v-else
          :model-value="filter.value"
          size="small"
          clearable
          placeholder="输入筛选值"
          style="width: 180px;"
          @update:model-value="handleValueChange(filter.id, $event)"
        />
        <el-button type="danger" size="small" link @click="removeFilter(filter.id)">
          删除
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Filter } from '@element-plus/icons-vue'
import {
  createListFilter,
  defaultListFilterOperators,
  getListFilterField,
  listFilterOperatorLabels,
  type ListCustomFilter,
  type ListFilterField,
  type ListFilterOperator,
  type ListFilterValue,
} from '@/composables/useListFilters'

const props = defineProps<{
  filters: ListCustomFilter[]
  fields: ListFilterField[]
  activeCount?: number
}>()

const emit = defineEmits<{
  'update:filters': [filters: ListCustomFilter[]]
}>()

function getField(field: string) {
  return getListFilterField(props.fields, field)
}

function getOperators(field: string) {
  const filterField = getField(field)
  if (!filterField) return []
  return filterField.operators || defaultListFilterOperators(filterField.type)
}

function getOptions(field: string) {
  return getField(field)?.options?.() || []
}

function nextFilterId() {
  return props.filters.reduce((maxId, filter) => Math.max(maxId, filter.id), 0) + 1
}

function handleAddFilter() {
  const firstField = props.fields[0]
  if (!firstField) return
  emit('update:filters', [...props.filters, createListFilter(firstField, nextFilterId())])
}

function patchFilter(id: number, patch: Partial<ListCustomFilter>) {
  emit('update:filters', props.filters.map(filter => (
    filter.id === id ? { ...filter, ...patch } : filter
  )))
}

function toListFilterValue(value: unknown): ListFilterValue {
  if (typeof value === 'string' || typeof value === 'number') return value
  return null
}

function handleFieldModelChange(id: number, value: string | number) {
  handleFieldChange(id, String(value))
}

function handleOperatorModelChange(id: number, value: string | number) {
  handleOperatorChange(id, value as ListFilterOperator)
}

function handleValueChange(id: number, value: unknown) {
  patchFilter(id, { value: toListFilterValue(value) })
}

function handleValueEndChange(id: number, value: unknown) {
  patchFilter(id, { valueEnd: toListFilterValue(value) })
}

function handleFieldChange(id: number, fieldName: string) {
  const field = getField(fieldName)
  const operator = field ? (field.operators || defaultListFilterOperators(field.type))[0] : 'contains'
  const emptyValue = field?.type === 'number' ? null : ''
  patchFilter(id, {
    field: fieldName,
    operator,
    value: emptyValue,
    valueEnd: emptyValue,
  })
}

function handleOperatorChange(id: number, operator: ListFilterOperator) {
  const currentFilter = props.filters.find(filter => filter.id === id)
  const field = currentFilter ? getField(currentFilter.field) : undefined
  const emptyValue = field?.type === 'number' ? null : ''
  patchFilter(id, {
    operator,
    valueEnd: operator === 'between' ? currentFilter?.valueEnd ?? emptyValue : emptyValue,
  })
}

function removeFilter(id: number) {
  emit('update:filters', props.filters.filter(filter => filter.id !== id))
}
</script>

<style scoped>
.pms-list-filter-section {
  margin-bottom: 12px;
}

.pms-list-filter-section .pms-filter-bar {
  margin-bottom: 0;
}

.pms-list-filter-summary {
  color: var(--pms-text-secondary);
  font-size: 12px;
  line-height: 1;
}

.pms-list-custom-filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0 12px;
  border-bottom: 1px solid var(--pms-border-soft);
}

.pms-list-custom-filter-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 32px;
}

.pms-list-filter-range {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.pms-list-filter-separator {
  color: var(--pms-text-muted);
  font-size: 12px;
}
</style>
