<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  fieldId: string
  label: string
  required?: boolean
  hint?: string
  error?: string
  span?: 1 | 2
}

const props = withDefaults(defineProps<Props>(), {
  required: false,
  hint: '',
  error: '',
  span: 1,
})

defineSlots<{
  default(props: { describedBy?: string; invalid: boolean }): unknown
}>()

const hintId = computed(() => `${props.fieldId}-hint`)
const errorId = computed(() => `${props.fieldId}-error`)
const describedBy = computed(() => [
  props.hint ? hintId.value : '',
  props.error ? errorId.value : '',
].filter(Boolean).join(' ') || undefined)
</script>

<template>
  <div
    class="pms-form-field"
    :class="{ 'pms-form-field--span-2': span === 2, 'is-error': Boolean(error) }"
    :aria-describedby="describedBy"
  >
    <label :for="fieldId" class="pms-form-field__label">
      {{ label }}<span v-if="required" class="pms-form-field__required" aria-hidden="true">*</span>
    </label>
    <p v-if="hint" :id="hintId" class="pms-form-field__hint">{{ hint }}</p>
    <div class="pms-form-field__control">
      <slot :described-by="describedBy" :invalid="Boolean(error)" />
    </div>
    <p v-if="error" :id="errorId" class="pms-form-field__error" role="alert">{{ error }}</p>
  </div>
</template>
