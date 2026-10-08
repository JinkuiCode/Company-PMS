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
      <select class="page-size-select" :value="pageSize" @change="$emit('update:pageSize', Number(($event.target as HTMLSelectElement).value))">
        <option :value="15">15 条/页</option>
        <option :value="20">20 条/页</option>
        <option :value="50">50 条/页</option>
        <option :value="100">100 条/页</option>
      </select>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

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
.pagination-right { display: flex; align-items: center; }
.page-btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: var(--pms-pagination-height); height: var(--pms-pagination-height); padding: 0 6px;
  border: 1px solid var(--pms-border); border-radius: var(--pms-radius-sm);
  background: var(--pms-surface); color: var(--pms-text-secondary); font-size: 12px; font-weight: 500;
  cursor: pointer;
  transition: background-color 120ms ease-out, border-color 120ms ease-out, color 120ms ease-out;
  line-height: 1;
}
.page-btn:hover:not(:disabled):not(.active) { background: var(--pms-surface-muted); border-color: #cbd5e1; color: var(--pms-text); }
.page-btn.active { background: var(--pms-primary); color: #fff; border-color: var(--pms-primary); font-weight: 700; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-btn.ellipsis { border: none; background: transparent; color: var(--pms-text-muted); cursor: default; min-width: 24px; }
.page-btn.nav-btn { font-size: 16px; font-weight: 500; min-width: 28px; }
.page-size-select {
  height: var(--pms-pagination-height); padding: 0 24px 0 8px; border: 1px solid var(--pms-border); border-radius: var(--pms-radius-sm);
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%236B7280' d='M6 8.825L1.175 4 2.238 2.938 6 6.7l3.763-3.763L10.825 4z'/%3E%3C/svg%3E") no-repeat right 8px center;
  color: var(--pms-text-secondary); font-size: 12px; cursor: pointer; appearance: none;
}
.page-size-select:hover { border-color: #cbd5e1; }
@media (max-width: 600px) {
  .pagination-center { order: 3; width: 100%; justify-content: center; }
}
</style>
