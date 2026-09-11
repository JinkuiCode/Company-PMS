<script setup lang="ts">
import type { PmsControlScalar, PmsControlStateProps, PmsOption } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: PmsControlScalar
  options: PmsOption[]
}

defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [value: PmsControlScalar] }>()
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
    <el-segmented
      :model-value="modelValue"
      :options="options"
      v-bind="$attrs"
      :disabled="disabled || readonly"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </PmsControlShell>
</template>
