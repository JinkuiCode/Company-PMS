<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { Lock } from '@element-plus/icons-vue'

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

const props = withDefaults(defineProps<Props>(), {
  required: false,
  editable: false,
  editing: false,
  empty: false,
  readonlyReason: '',
  error: '',
  longText: false,
})

const emit = defineEmits<{ 'edit-request': [] }>()
const editorRef = ref<HTMLElement>()

watch(() => props.editing, async (editing) => {
  if (!editing) return
  await nextTick()
  const focusTarget = editorRef.value?.querySelector<HTMLElement>(
    'input:not([type="hidden"]), textarea, [role="combobox"], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
  )
  focusTarget?.focus()
})
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
        <el-icon aria-hidden="true"><Lock /></el-icon>
      </span>
    </div>

    <div v-if="editing" ref="editorRef" class="pms-inline-field__surface pms-inline-field__editor">
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
