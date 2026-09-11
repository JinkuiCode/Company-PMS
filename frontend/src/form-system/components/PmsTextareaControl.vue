<script setup lang="ts">
import type { PmsControlStateProps } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: string | null
}

defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <PmsControlShell
    class="pms-form-control--textarea"
    :size="size"
    :variant="variant"
    :disabled="disabled"
    :readonly="readonly"
    :loading="loading"
    :error="error"
    :aria-label="ariaLabel"
  >
    <el-input
      type="textarea"
      :model-value="modelValue || ''"
      v-bind="$attrs"
      :disabled="disabled"
      :readonly="readonly"
      :aria-label="ariaLabel || undefined"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </PmsControlShell>
</template>
