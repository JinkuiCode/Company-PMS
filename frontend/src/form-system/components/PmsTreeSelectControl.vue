<script setup lang="ts">
import type { PmsControlStateProps, PmsControlValue } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: PmsControlValue
  data: Record<string, unknown>[]
}

defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [value: PmsControlValue] }>()
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
    <el-tree-select
      :model-value="modelValue"
      :data="data"
      v-bind="$attrs"
      :disabled="disabled || readonly"
      :loading="loading"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </PmsControlShell>
</template>
