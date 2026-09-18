<script setup lang="ts">
withDefaults(defineProps<{
  modelValue: boolean
  title: string
  busy?: boolean
  beforeClose?: (done: () => void) => void
}>(), { busy: false })
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="title"
    size="492px"
    class="pms-form-drawer"
    :modal="false"
    :before-close="beforeClose"
    :close-on-click-modal="false"
    :close-on-press-escape="!busy"
    :show-close="!busy"
    destroy-on-close
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="pms-form-drawer__heading">
        <h2>{{ title }}</h2>
        <slot name="actions" />
      </div>
    </template>
    <div class="pms-form-drawer__content" :aria-busy="busy"><slot /></div>
    <template #footer>
      <div class="pms-form-drawer__footer">
        <div class="pms-form-drawer__secondary"><slot name="secondary" /></div>
        <div class="pms-form-drawer__primary"><slot name="footer" /></div>
      </div>
    </template>
  </el-drawer>
</template>

<style>
/* Shared User-B container: controls keep their existing form-system tokens. */
.pms-form-drawer.el-drawer { max-width: calc(100vw - 32px); font-family: var(--pms-font); top: 72px; right: 16px; height: calc(100% - 88px); border: 1px solid var(--pms-border); border-radius: var(--pms-radius-sm); box-shadow: -4px 0 18px rgba(16, 24, 40, 0.04); }
.pms-form-drawer .el-drawer__header { padding: 20px 24px; margin: 0; border-bottom: 1px solid var(--pms-border); gap: 16px; }
.pms-form-drawer .el-drawer__body { min-height: 0; padding: 0; overflow-y: auto; }
.pms-form-drawer .el-drawer__footer { padding: 16px 24px; border-top: 1px solid var(--pms-border); background: var(--pms-surface); }
.pms-form-drawer__heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-width: 0; }
.pms-form-drawer__heading h2 { margin: 0; font-size: 16px; font-weight: 600; color: var(--pms-text); }
.pms-form-drawer__content { padding: 8px 24px 24px; }
.pms-form-drawer__footer, .pms-form-drawer__primary { display: flex; align-items: center; gap: 8px; }
.pms-form-drawer__footer { justify-content: space-between; }
.pms-form-drawer__secondary { min-width: 0; }
.pms-form-drawer__section { margin: 0; padding: 20px 0 12px; font-size: 13px; font-weight: 600; color: var(--pms-text); border-bottom: 1px solid var(--pms-border); }
.pms-form-drawer .pms-form-field { display: grid; grid-template-columns: 98px minmax(0, 1fr); align-items: start; column-gap: 12px; row-gap: 4px; padding: 8px 0; border-bottom: 1px solid var(--pms-border); }
.pms-form-drawer .pms-form-field__label { grid-column: 1; grid-row: 1; padding-top: 7px; margin: 0; }
.pms-form-drawer .pms-form-field__control { grid-column: 2; grid-row: 1; min-width: 0; }
.pms-form-drawer .pms-form-field__hint, .pms-form-drawer .pms-form-field__error { grid-column: 2; margin: 0; }
.pms-form-drawer__reference.el-button { color: var(--pms-primary); background: var(--pms-primary-soft); border-color: var(--pms-primary); }
@media (max-width: 400px) {
  .pms-form-drawer .el-drawer__header, .pms-form-drawer .el-drawer__footer { padding: 16px; }
  .pms-form-drawer__content { padding: 8px 16px 16px; }
  .pms-form-drawer .pms-form-field { grid-template-columns: 86px minmax(0, 1fr); gap: 8px; }
}
</style>
