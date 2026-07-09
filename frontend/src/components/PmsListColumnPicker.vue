<template>
  <el-popover
    placement="bottom-end"
    trigger="click"
    :width="332"
    popper-class="pms-list-column-picker-popper"
  >
    <template #reference>
      <el-button
        size="small"
        plain
        class="column-picker-trigger"
        aria-label="打开列设置"
      >
        <el-icon style="margin-right:4px;"><Setting /></el-icon>
        列设置
      </el-button>
    </template>

    <div class="column-picker-panel" aria-label="项目进度列设置">
      <div class="column-picker-toolbar">
        <el-input
          v-model="keyword"
          size="small"
          clearable
          placeholder="搜索字段"
        />
        <span class="column-picker-count">已选 {{ selectedCount }} 项</span>
      </div>

      <div class="column-picker-actions">
        <el-button size="small" text @click="restoreDefaults">恢复默认</el-button>
      </div>

      <div class="column-picker-groups">
        <section
          v-for="group in visibleGroups"
          :key="group.key"
          class="column-picker-group"
        >
          <header class="column-picker-group-title">{{ group.label }}</header>
          <label
            v-for="field in group.fields"
            :key="field.key"
            class="column-picker-field"
          >
            <el-checkbox
              :model-value="isSelected(field.key)"
              :label="field.key"
              @update:model-value="toggleField(field.key, $event)"
            >
              <span class="column-picker-field-label">{{ field.label }}</span>
            </el-checkbox>
            <span
              v-if="field.quick_addable"
              class="column-picker-field-hint"
            >
              快捷加入
            </span>
            <span
              v-else-if="field.value_type === 'long_text'"
              class="column-picker-field-hint"
            >
              长文本
            </span>
          </label>
        </section>

        <div v-if="!visibleGroups.length" class="column-picker-empty">
          没有匹配的字段
        </div>
      </div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Setting } from '@element-plus/icons-vue'

type ColumnPickerField = {
  key: string
  label: string
  value_type: string
  list_available: boolean
  quick_addable: boolean
}

type ColumnPickerGroup = {
  key: string
  label: string
  fields: ColumnPickerField[]
}

const props = defineProps<{
  modelValue: string[]
  groups: ColumnPickerGroup[]
  defaultKeys: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const keyword = ref('')

const normalizedKeyword = computed(() => keyword.value.trim().toLowerCase())

const visibleGroups = computed(() => {
  return props.groups
    .map(group => ({
      ...group,
      fields: group.fields.filter((field) => {
        if (!field.list_available) return false
        if (!normalizedKeyword.value) return true
        return field.label.toLowerCase().includes(normalizedKeyword.value)
          || field.key.toLowerCase().includes(normalizedKeyword.value)
      }),
    }))
    .filter(group => group.fields.length > 0)
})

const selectedCount = computed(() => props.modelValue.length)

function isSelected(key: string) {
  return props.modelValue.includes(key)
}

function toggleField(key: string, checked: unknown) {
  const next = new Set(props.modelValue)
  if (checked) next.add(key)
  else next.delete(key)
  emit('update:modelValue', Array.from(next))
}

function restoreDefaults() {
  emit('update:modelValue', [...props.defaultKeys])
}
</script>

<style scoped>
.column-picker-trigger {
  flex: 0 0 auto;
}

.column-picker-panel {
  display: grid;
  gap: 10px;
}

.column-picker-toolbar {
  display: grid;
  gap: 8px;
}

.column-picker-count {
  color: var(--pms-text-secondary);
  font-size: 12px;
  line-height: 1;
}

.column-picker-actions {
  display: flex;
  justify-content: flex-end;
}

.column-picker-groups {
  display: grid;
  gap: 12px;
  max-height: 360px;
  overflow: auto;
  padding-right: 4px;
}

.column-picker-group {
  display: grid;
  gap: 8px;
}

.column-picker-group-title {
  color: var(--pms-text);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
}

.column-picker-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.column-picker-field-label {
  color: var(--pms-text);
}

.column-picker-field-hint {
  flex: 0 0 auto;
  color: var(--pms-text-muted);
  font-size: 11px;
  line-height: 1;
}

.column-picker-empty {
  color: var(--pms-text-muted);
  font-size: 12px;
  line-height: 1.5;
}
</style>
