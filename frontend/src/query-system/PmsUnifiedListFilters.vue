<script setup lang="ts">
import { computed, ref, nextTick, watch } from 'vue'
import { Filter } from '@element-plus/icons-vue'
import type { ListFilterField } from '@/composables/useListFilters'
import PmsQueryConditions from './PmsQueryConditions.vue'
import { toQueryFields } from './list-adapter'
import { operatorLabel, validateConditions, type QueryCondition } from './core'
const props = defineProps<{ filters:QueryCondition[]; fields:ListFilterField[]; disabled?:boolean; readonly?:boolean }>()
const emit = defineEmits<{ 'update:filters':[value:QueryCondition[]] }>()
const fields = computed(() => toQueryFields(props.fields))
const opened = ref(false), trigger = ref<{ $el:HTMLElement } | null>(null)
const editor = ref<InstanceType<typeof PmsQueryConditions> | null>(null)
watch(opened, async open => { if (open) { await nextTick(); editor.value?.focus() } })
const invalid = computed(() => Object.values(validateConditions(props.filters,fields.value)).join('；'))
async function close() { opened.value = false; await nextTick(); trigger.value?.$el?.focus() }
function apply(value: QueryCondition[]) { emit('update:filters',value); void close() }
function summary(c: QueryCondition) {
  const f = fields.value.find(f=>f.field===c.field)
  if (!f) return '失效字段'
  if(c.operator==='reference') return `${f.label} 引用 · 已选 ${Array.isArray(c.value)?c.value.length:0} 条`
  const label = (v:unknown) => f.options?.find(o=>o.value===v)?.label ?? String(v ?? '')
  const value = Array.isArray(c.value) ? c.value.map(label).join('、') : label(c.value)
  return `${f.label} ${operatorLabel(c.operator,f.type)}${['isEmpty','notEmpty'].includes(c.operator) ? '' : ` ${value}${c.operator === 'between' ? ` 至 ${label(c.valueEnd)}` : ''}`}`
}
</script>
<template>
  <div class="pms-unified-list-filters pms-query-density">
    <el-config-provider size="small">
      <div class="pms-filter-bar">
        <slot />
        <el-popover :visible="opened" :width="740" placement="bottom-start" popper-class="pms-query-condition-popper">
          <template #reference><el-button ref="trigger" class="pms-unified-filter-trigger" type="primary" plain :icon="Filter" :disabled="disabled || !fields.length" :aria-expanded="opened" @click="opened = !opened">添加筛选<span v-if="filters.length">（{{ filters.length }}）</span></el-button></template>
          <PmsQueryConditions ref="editor" :opened="opened" :model-value="filters" :fields="fields" :disabled="disabled" :readonly="readonly" @apply="apply" @cancel="close" />
        </el-popover>
        <el-button v-if="filters.length" type="warning" plain :disabled="disabled || readonly" @click="emit('update:filters',[])">清空筛选</el-button>
      </div>
      <div v-if="filters.length" class="pms-query-condition-summary">
        <button v-for="c in filters" :key="c.id" class="pms-query-condition-chip pms-unified-filter-trigger" type="button" :disabled="disabled" @click="opened = true">{{ summary(c) }}</button>
      </div>
      <p v-if="invalid" role="alert" class="pms-query-condition-invalid">{{ invalid }}</p>
    </el-config-provider>
  </div>
</template>
<style scoped>
.pms-filter-bar { margin-bottom:0; }
.pms-query-condition-summary { display:flex; flex-wrap:wrap; gap:6px; padding:4px 0; }
.pms-query-condition-chip { min-width:0; max-width:100%; border:1px solid var(--pms-primary-soft); border-radius:4px; padding:2px 6px; font:inherit; font-size:12px; line-height:18px; color:var(--pms-primary); background:var(--pms-primary-soft); overflow-wrap:anywhere; text-align:left; cursor:pointer; }
.pms-query-condition-chip:focus-visible { outline:2px solid var(--pms-primary); outline-offset:1px; }
.pms-query-condition-invalid { color:var(--pms-danger); font-size:12px; margin:4px 0; }
</style>
<style>
.pms-query-condition-popper.el-popover { max-width:calc(100vw - 16px); padding:12px; border-radius:6px; }
</style>
