<script setup lang="ts">
import { nextTick, useAttrs } from 'vue'
import type { PmsControlStateProps, PmsControlValue, PmsOption } from '../types'
import PmsControlShell from './PmsControlShell.vue'

defineOptions({ inheritAttrs: false })

interface Props extends PmsControlStateProps {
  modelValue?: PmsControlValue
  options: PmsOption[]
}

const props = defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [value: PmsControlValue]; 'optionSelect': [value: PmsControlValue] }>()
const attrs = useAttrs()
let popupVisible = false, keyboardSelection = false
function selectByKeyboard() {
  keyboardSelection = popupVisible && !attrs.multiple
}
async function visibilityChanged(visible: boolean) {
  popupVisible = visible
  if (!visible && keyboardSelection) {
    keyboardSelection = false
    await nextTick()
    emit('optionSelect', props.modelValue)
  }
}
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
      @keydown.enter.capture="selectByKeyboard"
      @visible-change="visibilityChanged"
    >
      <el-option
        v-for="option in options"
        :key="String(option.value)"
        :label="option.label"
        :value="option.value"
        :disabled="option.disabled"
        @click="!option.disabled && emit('optionSelect', option.value)"
      />
    </el-select>
  </PmsControlShell>
</template>
