<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { Close, Collection } from '@element-plus/icons-vue'
import { PmsSelectControl, PmsTextControl, PmsNumberControl, PmsDateControl } from '@/form-system'
import { operatorsForField, operatorLabel, type QueryCondition, type QueryField, type QueryValue, type QueryOperator } from './core'
import { optionReference, type ReferenceRequest, type ReferenceRecord } from './reference'
import { referenceSummary } from './reference-summary'
import PmsQueryReference from './PmsQueryReference.vue'
const props=defineProps<{condition:QueryCondition;fields:QueryField[];conditions?:QueryCondition[];fixedField?:boolean;regular?:boolean;removable?:boolean;error?:string;prefix:string;appendTo?:HTMLElement|null}>()
const emit=defineEmits<{update:[value:QueryCondition];remove:[]}>()
const field=computed(()=>props.fields.find(f=>f.field===props.condition.field))
const referenceOpen=ref(false)
const resolved=ref<ReferenceRecord[]>([])
let resolution=0
const selectedValues=computed(() => props.condition.operator==='reference'&&Array.isArray(props.condition.value)?props.condition.value:[])
const summary=computed(() => referenceSummary(selectedValues.value,resolved.value,field.value?.field==='project_code',reference.value?.display==='name'?'名称不可用':undefined))
const reference=computed(()=>{
  const f=field.value;if(!f)return null
  const source=f.reference||(f.type==='enum'?optionReference(f.label,f.field,f.options||[]):null)
  return source?{...source,load:(q:ReferenceRequest)=>source.load({...q,conditions:props.conditions||[props.condition]})}:null
})
const controls=computed(()=>({size:props.regular?'regular' as const:'compact' as const}))
const textOperation=computed(()=>['contains','notContains','startsWith','endsWith'].includes(props.condition.operator))
const options=computed(()=>field.value?operatorsForField(field.value).map(op=>({value:op,label:operatorLabel(op,field.value!.type)})):[])
function update(key:string,value:unknown){emit('update',{...props.condition,[key]:(value??null) as QueryValue})}
function changeField(value:unknown){const f=props.fields.find(f=>f.field===value);if(!f)return;emit('update',{...props.condition,field:f.field,operator:f.type==='enum'?'in':operatorsForField(f).find(op=>op!=='reference')!,value:null,valueEnd:null,schemaVersion:2})}
function changeOperator(value:unknown){if(value==='reference'){referenceOpen.value=true;return}emit('update',{...props.condition,operator:value as QueryOperator,value:['in','notIn'].includes(String(value))?[]:null,valueEnd:null,schemaVersion:2})}
function confirmReference(value:(string|number)[],records:ReferenceRecord[]){resolved.value=records;emit('update',{...props.condition,operator:'reference',value,valueEnd:null,schemaVersion:2})}
watch(() => [props.condition.field,JSON.stringify(selectedValues.value),field.value,reference.value,props.conditions||[props.condition]],async () => {
  const version=++resolution, source=reference.value, ids=[...selectedValues.value]
  resolved.value=[]
  if(!source||!ids.length||ids.length>1000)return
  const records:ReferenceRecord[]=[]
  try {
    for(let page=1;;page++) {
      const result=await source.load({ids,page,pageSize:100})
      if(version!==resolution)return
      records.push(...result.items)
      if(records.length>=result.total||!result.items.length||records.length>=ids.length)break
    }
    if(version===resolution)resolved.value=records
  } catch { /* Stable values remain visible; submit still validates reference access. */ }
},{immediate:true,deep:true,flush:'sync'})
onBeforeUnmount(()=>resolution++)
</script>
<template>
  <div class="pms-condition-row" :class="{'is-range':condition.operator==='between','has-error':error,'is-regular':regular}" :data-field="condition.field">
    <div class="pms-condition-field">
      <span v-if="field?.required" class="pms-condition-required" aria-hidden="true">*</span>
      <span v-if="fixedField" class="pms-condition-label" :title="field?.label">{{field?.label || condition.field}}</span>
      <PmsSelectControl v-else :model-value="condition.field" :options="fields.map(f=>({value:f.field,label:f.label}))" v-bind="controls" :append-to="appendTo" :aria-required="field?.required||undefined" :aria-label="prefix+'字段名'" @update:model-value="changeField" />
    </div>
    <PmsSelectControl :model-value="referenceOpen?'reference':condition.operator" :options="options" v-bind="controls" :append-to="appendTo" :aria-label="prefix+'条件'" @update:model-value="changeOperator" />
    <div class="pms-condition-value">
      <span v-if="['isEmpty','notEmpty'].includes(condition.operator)" class="pms-condition-no-value">无需填写值</span>
      <button v-else-if="condition.operator==='reference'" type="button" class="pms-condition-reference pms-button-auxiliary" :aria-label="prefix+'引用值'" :title="summary.title" @click="referenceOpen=true"><el-icon><Collection /></el-icon><span>{{summary.text}}</span><small v-if="summary.count">{{summary.count}} 条</small></button>
      <PmsSelectControl v-else-if="field?.type==='enum'&&!textOperation" :key="condition.operator" :model-value="condition.value" :options="field.options||[]" :multiple="['in','notIn'].includes(condition.operator)" collapse-tags collapse-tags-tooltip clearable filterable placeholder="不限" v-bind="controls" :append-to="appendTo" :error="error" :aria-label="prefix+'值'" @update:model-value="update('value',$event)" />
      <PmsTextControl v-else-if="field?.type==='text'||textOperation" :model-value="condition.value as string|null" clearable placeholder="不限" v-bind="controls" :error="error" :aria-label="prefix+'值'" @update:model-value="update('value',$event)" />
      <template v-else-if="field?.type==='number'"><PmsNumberControl :model-value="condition.value as number|null" :controls="false" v-bind="controls" :error="error" :aria-label="prefix+'值'" @update:model-value="update('value',$event)" /><template v-if="condition.operator==='between'"><span>至</span><PmsNumberControl :model-value="condition.valueEnd as number|null" :controls="false" v-bind="controls" :error="error" :aria-label="prefix+'结束值'" @update:model-value="update('valueEnd',$event)" /></template></template>
      <template v-else><PmsDateControl :model-value="condition.value as string|null" value-format="YYYY-MM-DD" placeholder="不限" v-bind="controls" :append-to="appendTo" :error="error" :aria-label="prefix+'值'" @update:model-value="update('value',$event)" /><template v-if="condition.operator==='between'"><span>至</span><PmsDateControl :model-value="condition.valueEnd" value-format="YYYY-MM-DD" placeholder="结束日期" v-bind="controls" :append-to="appendTo" :error="error" :aria-label="prefix+'结束值'" @update:model-value="update('valueEnd',$event)" /></template></template>
    </div>
    <button v-if="removable" type="button" class="pms-condition-remove pms-button-dismiss" :aria-label="prefix+'移除条件'" title="移除条件" @click="emit('remove')"><el-icon><Close /></el-icon></button>
    <p v-if="error" class="pms-condition-error" role="alert">{{error}}</p>
    <PmsQueryReference v-if="reference" v-model="referenceOpen" :reference="reference" :value="condition.operator==='reference'&&Array.isArray(condition.value)?condition.value:[]" @confirm="confirmReference" />
  </div>
</template>
<style scoped>
.pms-condition-row{display:grid;grid-template-columns:96px 68px minmax(0,1fr) 18px;gap:4px;min-width:0;align-items:center;}
.pms-condition-row>.pms-form-control{width:100%;min-width:0;}
.pms-condition-field{display:flex;align-items:center;gap:3px;min-width:0;}
.pms-condition-field>.pms-form-control,.pms-condition-field>.pms-condition-label{flex:1;min-width:0;width:0;}
.pms-condition-required{flex-shrink:0;color:var(--pms-danger);font:500 12px/1 var(--pms-font);}
.pms-condition-value{display:flex;align-items:center;gap:4px;min-width:0;}
.pms-condition-value>.pms-form-control{flex:1;min-width:0;width:0;}
.pms-condition-value>span{flex-shrink:0;color:var(--pms-text-muted);line-height:24px;font-size:12px;}
.pms-condition-label{min-width:0;line-height:24px;color:var(--pms-text);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.pms-condition-reference{display:flex;align-items:center;gap:5px;height:var(--pms-query-height);width:100%;padding:0 7px;border:1px solid var(--pms-border);border-radius:4px;font:500 12px/18px var(--pms-font);min-width:0;overflow:hidden;margin:0;cursor:pointer;}
.pms-condition-reference>span{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.pms-condition-reference>small{flex-shrink:0;font:inherit;color:var(--pms-text-muted);}
.pms-condition-reference>.el-icon{flex-shrink:0;font-size:13px;}
.pms-condition-remove{width:18px;min-width:18px;height:var(--pms-query-height);padding:0;margin:0;}
.is-regular{grid-template-columns:108px 80px minmax(108px,1fr) 20px;}
.is-regular .pms-condition-label{line-height:32px;font-size:13px;}
.is-regular .pms-condition-remove{width:20px;min-width:20px;}
.is-regular .pms-condition-reference{height:32px;font-size:13px;}
.pms-condition-error{grid-column:1/-1;margin:0;font-size:12px;color:var(--pms-danger);}
@media(max-width:560px){.pms-condition-row{grid-template-columns:92px 64px minmax(0,1fr) 18px;}.is-regular{grid-template-columns:96px 76px minmax(0,1fr) 20px;}.is-range .pms-condition-value{flex-wrap:wrap;}.is-range .pms-condition-value>.pms-form-control{flex-basis:100%;}.is-range .pms-condition-value>span{display:none;}}
</style>
