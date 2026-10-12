<script setup lang="ts">
import { ref } from 'vue'
import PmsQueryColumnHeader from '../../src/query-system/PmsQueryColumnHeader.vue'
import PmsQueryConditionRow from '../../src/query-system/PmsQueryConditionRow.vue'
const fields = [
  { field: 'code', label: '项目编码', type: 'text', reference: {
    title: '项目档案', keyField: 'code', keyType: 'string',
    lineOptions: () => [{ value: 1, label: '8吋Bench' }, { value: 2, label: 'Single' }],
    load: async () => ({ items: [{ value: 'A-202503', code: 'A-202503', name: '清洗项目', lineName: 'Single' }], total: 1 }),
  } },
  { field: 'name', label: '物料名称', type: 'text' },
  { field: 'organization_ids', label: '产品线', type: 'enum', options: [{ value: 499413, label: '8吋Bench' }, { value: 100002, label: 'Single' }] },
  { field: 'date', label: '日期', type: 'date' },
  { field: 'quantity', label: '数量', type: 'number' },
]
const shown = ref(true), filters = ref<any[]>([]), condition = ref<any>({ id: 1, field: 'organization_ids', operator: 'reference', value: [], valueEnd: null, schemaVersion: 2 })
const context = { fields: () => fields as any, filters: () => filters.value,
  load: async (field: string) => (await fetch('/__popup-candidates?field=' + field)).json(),
  apply: (field: string, filter: any) => { filters.value = [...filters.value.filter(f => f.field !== field), ...(filter ? [filter] : [])] },
}
</script>
<template>
  <main style="padding:24px">
    <div v-if="shown" style="display:flex;width:950px;gap:20px;margin-bottom:40px">
      <PmsQueryColumnHeader v-for="field in fields" :key="field.field" :params="{ field: field.field, contextQuery: () => context }" />
    </div>
    <div style="position:fixed;bottom:24px;right:24px"><button @click="shown=!shown">切换表格</button><button>外部区域</button></div>
    <output aria-label="已应用筛选">{{ JSON.stringify(filters) }}</output>
    <div style="width:326px;margin-top:32px"><PmsQueryConditionRow :condition="condition" :fields="fields as any" prefix="查询" @update="condition=$event" /></div>
    <output aria-label="已选值">{{ JSON.stringify(condition.value) }}</output>
  </main>
</template>
