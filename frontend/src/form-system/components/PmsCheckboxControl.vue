<script setup lang="ts">
import type { PmsControlStateProps } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: boolean
  label?: string
}

defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
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
    <el-checkbox
      :model-value="modelValue"
      v-bind="$attrs"
      :disabled="disabled || readonly"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', Boolean($event))"
    >
      <slot>{{ label }}</slot>
    </el-checkbox>
  </PmsControlShell>
</template>
