<script setup lang="ts">
import type { PmsControlStateProps, PmsOption } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

type GroupValue = Array<string | number | boolean>

interface Props extends PmsControlStateProps {
  modelValue?: GroupValue
  options: PmsOption[]
}

defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [value: GroupValue] }>()
</script>

<template>
  <PmsControlShell
    variant="binary"
    :size="size"
    :disabled="disabled"
    :readonly="readonly"
    :loading="loading"
    :error="error"
    :aria-label="ariaLabel"
  >
    <el-checkbox-group
      :model-value="modelValue || []"
      v-bind="$attrs"
      :disabled="disabled || readonly"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <el-checkbox
        v-for="option in options"
        :key="String(option.value)"
        :value="option.value"
        :disabled="option.disabled"
      >
        {{ option.label }}
      </el-checkbox>
    </el-checkbox-group>
  </PmsControlShell>
</template>
