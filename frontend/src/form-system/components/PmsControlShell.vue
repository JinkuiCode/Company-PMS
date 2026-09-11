<script setup lang="ts">
import { computed } from 'vue'
import type { PmsControlStateProps } from '../types'

const props = withDefaults(defineProps<PmsControlStateProps>(), {
  size: 'regular',
  variant: 'field',
  disabled: false,
  readonly: false,
  loading: false,
  error: '',
  ariaLabel: '',
})

const classes = computed(() => ({
  [`pms-form-control--${props.size}`]: true,
  [`pms-form-control--${props.variant}`]: true,
  'is-error': Boolean(props.error),
  'is-disabled': props.disabled,
  'is-readonly': props.readonly,
  'is-loading': props.loading,
}))
</script>

<template>
  <div
    class="pms-form-control"
    :class="classes"
    :aria-label="ariaLabel || undefined"
    :aria-busy="loading || undefined"
  >
    <slot />
    <span v-if="loading" class="pms-form-control__loading" aria-hidden="true" />
  </div>
</template>
