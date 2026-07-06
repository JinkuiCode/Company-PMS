<template>
  <div class="pms-data-list" :class="{ 'pms-page': surface }">
    <div v-if="$slots.header" class="pms-data-list-header">
      <slot name="header" />
    </div>

    <div v-if="$slots['toolbar-left'] || $slots['toolbar-right']" class="toolbar pms-toolbar pms-data-list-toolbar">
      <div class="toolbar-left pms-toolbar-left">
        <slot name="toolbar-left" />
      </div>
      <div class="toolbar-right pms-toolbar-right">
        <slot name="toolbar-right" />
      </div>
    </div>

    <slot name="filters" />

    <div v-if="$slots.grid" class="pms-data-list-grid-shell" :class="gridShellClass">
      <slot name="grid" />
      <GridHorizontalScrollbar v-if="showScrollbar" ref="scrollbarRef" :label="scrollbarLabel" />
    </div>

    <div v-if="$slots.pagination" class="pms-data-list-pagination">
      <slot name="pagination" />
    </div>

    <slot />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import GridHorizontalScrollbar from '@/components/GridHorizontalScrollbar.vue'

withDefaults(defineProps<{
  surface?: boolean
  showScrollbar?: boolean
  scrollbarLabel?: string
  gridShellClass?: string
}>(), {
  surface: true,
  showScrollbar: true,
  scrollbarLabel: '列表横向滚动条',
  gridShellClass: '',
})

const scrollbarRef = ref<InstanceType<typeof GridHorizontalScrollbar>>()

function refreshScrollbar() {
  scrollbarRef.value?.refresh()
}

defineExpose({ refreshScrollbar })
</script>

<style scoped>
.pms-data-list {
  min-height: 100%;
}

.pms-data-list-header {
  padding-bottom: 12px;
}

.pms-data-list-toolbar {
  padding-bottom: 12px;
}

.pms-data-list-grid-shell {
  width: 100%;
  min-width: 0;
}

.pms-data-list-grid-shell :deep(.pms-ag-grid) {
  min-height: 176px;
}

.pms-data-list-grid-shell :deep(.ag-body-horizontal-scroll) {
  height: 0 !important;
  min-height: 0 !important;
  opacity: 0;
  pointer-events: none;
  overflow: hidden;
}

.pms-data-list-grid-shell :deep(.ag-body-horizontal-scroll-viewport) {
  scrollbar-width: thin;
  scrollbar-color: #94a3b8 #e2e8f0;
}

.pms-data-list-grid-shell :deep(.ag-body-horizontal-scroll-viewport::-webkit-scrollbar) {
  height: 12px;
}

.pms-data-list-grid-shell :deep(.ag-body-horizontal-scroll-viewport::-webkit-scrollbar-track) {
  background: #e2e8f0;
  border-radius: 999px;
}

.pms-data-list-grid-shell :deep(.ag-body-horizontal-scroll-viewport::-webkit-scrollbar-thumb) {
  background: #94a3b8;
  border: 2px solid #e2e8f0;
  border-radius: 999px;
}

.pms-data-list-grid-shell :deep(.ag-body-horizontal-scroll-viewport::-webkit-scrollbar-thumb:hover) {
  background: #64748b;
}

.pms-data-list-pagination {
  margin-top: 6px;
}

.pms-data-list-pagination :deep(.custom-pagination) {
  margin-top: 0;
  padding-top: 8px;
}
</style>
