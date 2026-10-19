<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { PmsTextControl, PmsNumberControl, PmsDateControl, PmsSelectControl } from '@/form-system'
import type { ICellEditorParams } from 'ag-grid-community'
import { productLines } from './fixtures'
const props=defineProps<{params:ICellEditorParams & {kind?:string}}>()
const value=ref<any>(props.params.value)
const host=ref<HTMLElement>()
defineExpose({getValue:()=>value.value})
onMounted(async()=>{await nextTick();host.value?.querySelector('input')?.focus()})
</script>
<template>
  <div ref="host" class="preview-grid-editor">
    <PmsNumberControl v-if="params.kind==='number'" v-model="value" size="compact" :min="0" :controls="false" aria-label="编辑数量" />
    <PmsDateControl v-else-if="params.kind==='date'" v-model="value" size="compact" aria-label="编辑登记日期" popper-class="ag-custom-component-popup" />
    <PmsSelectControl v-else-if="params.kind==='line'" v-model="value" :options="productLines" size="compact" aria-label="编辑产品线" popper-class="ag-custom-component-popup" />
    <PmsTextControl v-else v-model="value" size="compact" aria-label="编辑项目名称" />
  </div>
</template>
