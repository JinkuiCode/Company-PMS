<script setup lang="ts">
import type { PmsControlStateProps, PmsControlValue } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: PmsControlValue
  type?: 'date' | 'daterange'
  valueFormat?: string
}

withDefaults(defineProps<Props>(), {
  type: 'date',
  valueFormat: 'YYYY-MM-DD',
})
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
    <el-date-picker
      :model-value="modelValue"
      :type="type"
      :value-format="valueFormat"
      v-bind="$attrs"
      :disabled="disabled || readonly"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </PmsControlShell>
</template>
