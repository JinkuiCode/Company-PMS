<script setup lang="ts">
interface Props {
  label: string
  required?: boolean
  editable?: boolean
  editing?: boolean
  empty?: boolean
  readonlyReason?: string
  error?: string
  longText?: boolean
}

withDefaults(defineProps<Props>(), {
  required: false,
  editable: false,
  editing: false,
  empty: false,
  readonlyReason: '',
  error: '',
  longText: false,
})

const emit = defineEmits<{ 'edit-request': [] }>()
</script>

<template>
  <div
    class="pms-inline-field"
    :class="{
      'is-editable': editable,
      'is-editing': editing,
      'is-empty': empty,
      'is-error': Boolean(error),
      'is-long-text': longText,
    }"
  >
    <div class="pms-inline-field__label">
      <span>{{ label }}<span v-if="required" class="pms-inline-field__required" aria-hidden="true">*</span></span>
      <span
        v-if="!editable && readonlyReason"
        class="pms-inline-field__readonly"
        :title="readonlyReason"
        :aria-label="readonlyReason"
      >
        锁
      </span>
    </div>

    <div v-if="editing" class="pms-inline-field__surface pms-inline-field__editor">
      <slot name="editor" />
    </div>
    <button
      v-else-if="editable"
      type="button"
      class="pms-inline-field__value"
      :class="{ 'is-empty': empty }"
      :aria-label="`编辑${label}`"
      @click="emit('edit-request')"
    >
      <slot name="display" />
    </button>
    <div
      v-else
      class="pms-inline-field__value pms-inline-field__value--readonly"
      :class="{ 'is-empty': empty }"
      :title="readonlyReason || undefined"
    >
      <slot name="display" />
    </div>

    <p v-if="error" class="pms-inline-field__error" role="alert">{{ error }}</p>
  </div>
</template>
