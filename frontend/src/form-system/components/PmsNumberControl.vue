<script setup lang="ts">
import type { PmsControlStateProps } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: number | null
  min?: number
  max?: number
  step?: number
  precision?: number
}

defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [value: number | null | undefined] }>()
</script>

<template>
  <PmsControlShell
    :size="size"
    :variant="variant"
    :disabled="disabled"
    :readonly="readonly"
    :loading="loading"
    :error="error"
    :aria-label="ariaLabel"
  >
    <el-input-number
      :model-value="modelValue"
      :min="min"
      :max="max"
      :step="step"
      :precision="precision"
      v-bind="$attrs"
      :disabled="disabled || readonly"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </PmsControlShell>
</template>
