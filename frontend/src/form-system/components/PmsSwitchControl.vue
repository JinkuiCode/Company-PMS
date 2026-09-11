<script setup lang="ts">
import type { PmsControlStateProps } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: boolean
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
    <el-switch
      :model-value="modelValue"
      v-bind="$attrs"
      :disabled="disabled || readonly"
      :loading="loading"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </PmsControlShell>
</template>
