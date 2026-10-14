<script setup lang="ts">
import {ref} from 'vue'
import {type FormInstance,type FormRules} from 'element-plus'
import {PmsFormField,PmsTextControl,PmsSelectControl,PmsDateControl,PmsNumberControl,PmsTextareaControl,type PmsOption} from '@/form-system'
interface ArchiveField {key:string;label:string;value_type:'text'|'select'|'number'|'date'|'datetime'|'user'|'long_text';source_type:'archive'|'system'}
const props=defineProps<{
 model:Record<string,any>;groups:Array<{key:string;label:string;fields:ArchiveField[]}>;rules:FormRules;
 required:(field:ArchiveField)=>boolean;editable:(field:ArchiveField)=>boolean;
 options:(key:string)=>PmsOption[];format?:(field:ArchiveField)=>string;
 errors:Record<string,string>;idPrefix:string;
}>()
const emit=defineEmits<{'field-change':[key:string,value:any]}>()
const form=ref<FormInstance>()
function value(field:ArchiveField){return field.source_type==='system'&&props.format?props.format(field):props.model[field.key]}
defineExpose({validate:()=>form.value?.validate(),validateField:(keys:string[])=>form.value?.validateField(keys),clearValidate:(keys?:string[])=>form.value?.clearValidate(keys),scrollToField:(key:string)=>form.value?.scrollToField(key),resetFields:()=>form.value?.resetFields()})
</script>
<template>
 <el-form ref="form" :model="model" :rules="rules" label-position="top" class="pms-standard-dialog-form">
  <section v-for="group in groups" :key="group.key"><h3 class="pms-form-drawer__section">{{group.label}}</h3>
   <el-form-item v-for="field in group.fields" :key="field.key" :prop="field.key">
    <PmsFormField :field-id="`${idPrefix}-${field.key}`" :label="field.label" :required="required(field)" :error="errors[field.key]">
     <template #default="{describedBy,invalid}">
      <PmsSelectControl v-if="['select','user'].includes(field.value_type)&&field.source_type!=='system'" :id="`${idPrefix}-${field.key}`" :model-value="value(field)" :options="options(field.key)" filterable clearable :disabled="!editable(field)" :aria-label="field.label" :aria-required="required(field)" :aria-describedby="describedBy" :aria-invalid="invalid||undefined" placeholder="请选择" @update:model-value="emit('field-change',field.key,$event)" />
      <PmsNumberControl v-else-if="field.value_type==='number'" :id="`${idPrefix}-${field.key}`" :model-value="value(field)" :disabled="!editable(field)" :aria-label="field.label" @update:model-value="emit('field-change',field.key,$event)" />
      <PmsDateControl v-else-if="field.value_type==='date'" :id="`${idPrefix}-${field.key}`" :model-value="value(field)" value-format="YYYY-MM-DD" type="date" :disabled="!editable(field)" :aria-label="field.label" @update:model-value="emit('field-change',field.key,$event)" />
      <PmsTextareaControl v-else-if="field.value_type==='long_text'" :id="`${idPrefix}-${field.key}`" :model-value="value(field)" :readonly="!editable(field)" :rows="3" :aria-label="field.label" @update:model-value="emit('field-change',field.key,$event)" />
      <PmsTextControl v-else :id="`${idPrefix}-${field.key}`" :model-value="value(field)" :readonly="!editable(field)" :aria-label="field.label" :aria-required="required(field)" :aria-describedby="describedBy" :aria-invalid="invalid||undefined" @update:model-value="emit('field-change',field.key,$event)" />
     </template>
    </PmsFormField>
   </el-form-item>
  </section>
  <slot />
 </el-form>
</template>
