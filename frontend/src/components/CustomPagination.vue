<template>
  <div class="custom-pagination">
    <div class="pagination-left">
      <span class="pagination-total">共 {{ total }} 条</span>
    </div>
    <div class="pagination-center">
      <button class="page-btn nav-btn" :disabled="modelValue === 1" @click="$emit('update:modelValue', modelValue - 1)">‹</button>
      <template v-for="p in visiblePages" :key="p">
        <button v-if="p === -1" class="page-btn ellipsis" disabled>···</button>
        <button v-else class="page-btn" :class="{ active: p === modelValue }" @click="$emit('update:modelValue', p)">{{ p }}</button>
      </template>
      <button class="page-btn nav-btn" :disabled="modelValue === totalPages" @click="$emit('update:modelValue', modelValue + 1)">›</button>
    </div>
    <div class="pagination-right">
      <PmsSelectControl class="page-size-select" size="compact" :model-value="pageSize" :options="sizeOptions" aria-label="每页条数" @update:model-value="value => emit('update:pageSize', Number(value))" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PAGE_SIZE_OPTIONS } from '../config/listUi.ts'
import {PmsSelectControl} from '@/form-system'
const sizeOptions=PAGE_SIZE_OPTIONS.map(value=>({value,label:`${value} 条/页`}))

const props = defineProps<{
  total: number
  modelValue: number
  pageSize: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
  'update:pageSize': [value: number]
}>()

const totalPages = computed(() => Math.ceil(props.total / props.pageSize) || 1)

const visiblePages = computed(() => {
  const pages: number[] = []
  pages.push(1)
  let start = Math.max(2, props.modelValue - 1)
  let end = Math.min(totalPages.value - 1, props.modelValue + 1)
  if (props.modelValue <= 3) { start = 2; end = Math.min(5, totalPages.value - 1) }
  else if (props.modelValue >= totalPages.value - 2) { start = Math.max(totalPages.value - 4, 2); end = totalPages.value - 1 }
  if (start > 2) pages.push(-1)
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < totalPages.value - 1) pages.push(-1)
  if (totalPages.value > 1) pages.push(totalPages.value)
  return [...new Set(pages)]
})
</script>

<style scoped>
.custom-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--pms-query-inset);
  margin-top: var(--pms-query-inset);
  min-height: 32px;
  flex-wrap: wrap;
  gap: 6px;
  border-top: 1px solid var(--pms-border-soft);
}
.pagination-left { display: flex; align-items: center; }
.pagination-total { font-size: 12px; color: var(--pms-text-secondary); font-weight: 500; }
.pagination-center { display: flex; align-items: center; gap: 4px; }
.pagination-right { display: flex; align-items: center; width:100px; --pms-form-control-height-compact:var(--pms-pagination-height); --pms-font-size-base:12px; }
.page-btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: var(--pms-pagination-height); height: var(--pms-pagination-height); padding: 0 6px;
  border: 1px solid var(--pms-border); border-radius: var(--pms-radius-sm);
  background: var(--pms-surface); color: var(--pms-text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer;
  transition: background-color 120ms ease-out, border-color 120ms ease-out, color 120ms ease-out;
  line-height: 1;
}
.page-btn:hover:not(:disabled):not(.active) { background: var(--pms-surface-muted); border-color: var(--pms-text-muted); color: var(--pms-text); }
.page-btn.active { background: var(--pms-primary); color: #fff; border-color: var(--pms-primary); font-weight: 700; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-btn.ellipsis { border: none; background: transparent; color: var(--pms-text-muted); cursor: default; min-width: 24px; }
.page-btn.nav-btn { font-size: 16px; font-weight: 500; min-width: 28px; }
.page-size-select {
  width:100px;font-size:12px;
}
@media (max-width: 600px) {
  .pagination-center { order: 3; width: 100%; justify-content: center; }
}
</style>
