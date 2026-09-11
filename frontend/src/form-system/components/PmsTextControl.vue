<script setup lang="ts">
import type { PmsControlStateProps } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: string | number | null
}

defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
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
    <el-input
      :model-value="modelValue == null ? '' : String(modelValue)"
      v-bind="$attrs"
      :disabled="disabled"
      :readonly="readonly"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <template v-if="$slots.prefix" #prefix><slot name="prefix" /></template>
      <template v-if="$slots.suffix" #suffix><slot name="suffix" /></template>
      <template v-if="$slots.prepend" #prepend><slot name="prepend" /></template>
      <template v-if="$slots.append" #append><slot name="append" /></template>
    </el-input>
  </PmsControlShell>
</template>
