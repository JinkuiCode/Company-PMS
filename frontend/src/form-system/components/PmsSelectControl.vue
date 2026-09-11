<script setup lang="ts">
import type { PmsControlStateProps, PmsControlValue, PmsOption } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: PmsControlValue
  options: PmsOption[]
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
    <el-select
      :model-value="modelValue"
      v-bind="$attrs"
      :disabled="disabled || readonly"
      :loading="loading"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <el-option
        v-for="option in options"
        :key="String(option.value)"
        :label="option.label"
        :value="option.value"
        :disabled="option.disabled"
      />
    </el-select>
  </PmsControlShell>
</template>
