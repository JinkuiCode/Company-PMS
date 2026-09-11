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
        <div class="pms-list-filter-control pms-list-filter-control--field">
          <PmsSelectControl
            :model-value="filter.field"
            size="compact"
            :options="fieldOptions"
            aria-label="筛选字段"
            @update:model-value="handleFieldModelChange(filter.id, $event)"
          />
        </div>
        <div class="pms-list-filter-control pms-list-filter-control--operator">
          <PmsSelectControl
            :model-value="filter.operator"
            size="compact"
            :options="operatorOptions(filter.field)"
            aria-label="筛选条件"
            @update:model-value="handleOperatorModelChange(filter.id, $event)"
          />
        </div>
        <template v-if="getField(filter.field)?.type === 'select'">
          <div class="pms-list-filter-control pms-list-filter-control--select-value">
            <PmsSelectControl
              :model-value="filter.value"
              size="compact"
              :options="getOptions(filter.field)"
              clearable
              filterable
              placeholder="选择值"
              aria-label="筛选值"
              @update:model-value="handleValueChange(filter.id, $event)"
            />
          </div>
        </template>
        <template v-else-if="getField(filter.field)?.type === 'date'">
          <div v-if="filter.operator === 'between'" class="pms-list-filter-range">
            <div class="pms-list-filter-control pms-list-filter-control--date-range">
              <PmsDateControl
                :model-value="filter.value"
                type="date"
                size="compact"
                value-format="YYYY-MM-DD"
                placeholder="开始日期"
                aria-label="筛选开始日期"
                @update:model-value="handleValueChange(filter.id, $event)"
              />
            </div>
            <span class="pms-list-filter-separator">至</span>
            <div class="pms-list-filter-control pms-list-filter-control--date-range">
              <PmsDateControl
                :model-value="filter.valueEnd"
                type="date"
                size="compact"
                value-format="YYYY-MM-DD"
                placeholder="结束日期"
                aria-label="筛选结束日期"
                @update:model-value="handleValueEndChange(filter.id, $event)"
              />
            </div>
          </div>
          <div v-else class="pms-list-filter-control pms-list-filter-control--date-value">
            <PmsDateControl
              :model-value="filter.value"
              type="date"
              size="compact"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              aria-label="筛选日期"
              @update:model-value="handleValueChange(filter.id, $event)"
            />
          </div>
        </template>
        <template v-else-if="getField(filter.field)?.type === 'number'">
          <div v-if="filter.operator === 'between'" class="pms-list-filter-range">
            <div class="pms-list-filter-control pms-list-filter-control--number-range">
              <PmsNumberControl
                :model-value="filter.value as number | null"
                size="compact"
                placeholder="最小值"
                aria-label="筛选最小值"
                @update:model-value="handleValueChange(filter.id, $event)"
              />
            </div>
            <span class="pms-list-filter-separator">至</span>
            <div class="pms-list-filter-control pms-list-filter-control--number-range">
              <PmsNumberControl
                :model-value="filter.valueEnd as number | null"
                size="compact"
                placeholder="最大值"
                aria-label="筛选最大值"
                @update:model-value="handleValueEndChange(filter.id, $event)"
              />
            </div>
          </div>
          <div v-else class="pms-list-filter-control pms-list-filter-control--number-value">
            <PmsNumberControl
              :model-value="filter.value as number | null"
              size="compact"
              placeholder="输入数值"
              aria-label="筛选数值"
              @update:model-value="handleValueChange(filter.id, $event)"
            />
          </div>
        </template>
        <div v-else class="pms-list-filter-control pms-list-filter-control--text-value">
          <PmsTextControl
            :model-value="filter.value"
            size="compact"
            clearable
            placeholder="输入筛选值"
            aria-label="筛选值"
            @update:model-value="handleValueChange(filter.id, $event)"
          />
        </div>
        <el-button type="danger" size="small" link @click="removeFilter(filter.id)">
          删除
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Filter } from '@element-plus/icons-vue'
import { PmsDateControl, PmsNumberControl, PmsSelectControl, PmsTextControl, type PmsOption } from '@/form-system'
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

const fieldOptions = computed<PmsOption[]>(() => props.fields.map(field => ({
  label: field.label,
  value: field.field,
})))

function operatorOptions(field: string): PmsOption[] {
  return getOperators(field).map(operator => ({
    label: listFilterOperatorLabels[operator],
    value: operator,
  }))
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

function handleFieldModelChange(id: number, value: unknown) {
  handleFieldChange(id, String(value))
}

function handleOperatorModelChange(id: number, value: unknown) {
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

.pms-list-filter-control {
  display: inline-flex;
  flex: 0 0 auto;
}

.pms-list-filter-control--field { width: 132px; }
.pms-list-filter-control--operator { width: 96px; }
.pms-list-filter-control--select-value { width: 164px; }
.pms-list-filter-control--date-range { width: 136px; }
.pms-list-filter-control--date-value { width: 150px; }
.pms-list-filter-control--number-range { width: 120px; }
.pms-list-filter-control--number-value { width: 140px; }
.pms-list-filter-control--text-value { width: 180px; }

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
