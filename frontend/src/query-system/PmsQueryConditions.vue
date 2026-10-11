<script setup lang="ts">
import { computed, ref, watch, nextTick, useId } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import { ClickOutside as vClickOutside } from 'element-plus'
import { PmsSelectControl, PmsTextControl, PmsNumberControl, PmsDateControl } from '@/form-system'
import { cloneQuery, adaptConditions, operatorsFor, operatorsForField, operatorLabel, validateConditions, type QueryCondition, type QueryField, type QueryOperator, type QueryScalar } from './core'
import PmsQueryReference from './PmsQueryReference.vue'
import { optionReference, type QueryReference } from './reference'
const props = defineProps<{ modelValue: QueryCondition[]; fields: QueryField[]; opened: boolean; disabled?: boolean; readonly?: boolean }>()
const emit = defineEmits<{ apply:[value:QueryCondition[]]; cancel:[] }>()
const draft = ref<QueryCondition[]>([]), errors = ref<Record<number,string>>({}), popupHost = ref<HTMLElement | null>(null)
const errorPrefix = useId()
const referenceCondition=ref<QueryCondition|null>(null),referenceOpened=ref(false),applying=ref(false)
const activeReference=computed<QueryReference|null>(()=>{
  const f=referenceCondition.value&&fieldOf(referenceCondition.value)
  if(!f)return null
  const source=f.reference || (f.type==='enum'?optionReference(f.label,f.field,f.options||[]):null)
  return source ? {...source,load:q=>source.load({...q,conditions:draft.value})} : null
})
function openReference(c:QueryCondition){referenceCondition.value=c;referenceOpened.value=true}
function confirmReference(value:(string|number)[]){
  if(!referenceCondition.value)return
  Object.assign(referenceCondition.value,{operator:'reference',value,valueEnd:null,schemaVersion:2});errors.value={}
}
const isTextOperator=(c:QueryCondition)=>['contains','notContains','startsWith','endsWith'].includes(c.operator)
defineExpose({ focus: () => popupHost.value?.focus() })
let application = 0
watch([() => props.opened, () => props.modelValue], ([open]) => {
  application++
  applying.value = false
  referenceOpened.value = false
  referenceCondition.value = null
  if (open) { draft.value = adaptConditions(props.modelValue); errors.value = {} }
}, { immediate:true, deep:true, flush:'sync' })
const locked = computed(() => props.disabled || props.readonly || applying.value)
const controls = computed(() => ({ size:'compact' as const, disabled:props.disabled || applying.value, readonly:props.readonly }))
const fieldOf = (c: QueryCondition) => props.fields.find(f => f.field === c.field)
function availableOperators(c: QueryCondition) {
  const f = fieldOf(c)
  if (!f) return []
  const operators = operatorsForField(f)
  if (c.schemaVersion !== 2 && ['before','after'].includes(c.operator)) operators.push(c.operator)
  return operators.map(op => ({ value:op, label:operatorLabel(op,f.type) }))
}
function add() {
  const field = props.fields[0]
  if (!field) return
  draft.value.push({id:Math.max(0,...draft.value.map(c=>c.id))+1,field:field.field,operator:operatorsFor(field.type)[0]!,value:null,valueEnd:null,schemaVersion:2})
}
function changeField(c: QueryCondition, value: unknown) {
  c.field = String(value)
  c.operator = operatorsFor(fieldOf(c)?.type || 'text')[0]!
  c.value = null; c.valueEnd = null; c.schemaVersion = 2; errors.value = {}
}
function changeOperator(c: QueryCondition, value: unknown) {
  if(value==='reference'){openReference(c);return}
  c.operator = value as QueryOperator; c.schemaVersion = 2
  c.value = ['in','notIn'].includes(c.operator) ? [] : null; c.valueEnd = null; errors.value = {}
}
async function apply() {
  if (!props.opened || locked.value) return
  const snapshot = cloneQuery(draft.value)
  errors.value = validateConditions(snapshot,props.fields)
  if (!Object.keys(errors.value).length) {
    const run = ++application
    const current = () => run === application && props.opened
    const failures: Record<number,string> = {}
    applying.value=true
    try{
      for(const c of snapshot.filter(c=>c.operator==='reference'&&fieldOf(c)?.reference)) {
        const source=fieldOf(c)!.reference!,ids=c.value as (string|number)[],available=new Set<string|number>()
        for(let page=1;;page++) {
          const result=await source.load({ids,conditions:snapshot,page,pageSize:100})
          if (!current()) return
          result.items.forEach(r=>available.add(r.value))
          if(available.size>=result.total||!result.items.length)break
        }
        if(ids.some(id=>!available.has(id)))failures[c.id]='部分引用记录不在当前产品线或权限范围，请重新选择'
      }
      if (!current()) return
      errors.value = failures
      if(!Object.keys(failures).length)emit('apply',snapshot)
    }catch{if (current()) errors.value[0]='引用校验失败，请重试；原筛选条件保持不变'}
    finally{if (run === application) applying.value=false}
  }
  else { await nextTick(); popupHost.value?.querySelector<HTMLInputElement>('.condition-row:has(.condition-error) input')?.focus() }
}
function outside(event: MouseEvent) {
  if(referenceOpened.value||applying.value)return
  if (props.opened && !event.composedPath().some(node => node instanceof HTMLElement && node.classList.contains('pms-unified-filter-trigger'))) emit('cancel')
}
function escape(){if(!referenceOpened.value&&!applying.value)emit('cancel')}
</script>
<template>
  <el-config-provider size="small">
    <section ref="popupHost" v-click-outside="outside" class="condition-editor pms-query-density" role="dialog" tabindex="-1" aria-label="统一筛选条件" @keydown.esc.stop="escape">
      <header><strong>筛选条件</strong><span>全部条件同时满足</span><el-button type="warning" plain :disabled="locked" @click="draft = []; errors = {}">清空</el-button></header>
      <div class="condition-labels" aria-hidden="true"><span>字段</span><span>匹配方式</span><span>条件值</span></div>
      <p v-if="errors[0]" class="condition-error" role="alert">{{ errors[0] }}</p>
      <div class="condition-scroll">
        <div v-for="(c,i) in draft" :key="c.id" class="condition-row">
          <PmsSelectControl :model-value="c.field" :options="fields.map(f=>({value:f.field,label:f.label}))" v-bind="controls" :append-to="popupHost" :aria-label="`条件${i+1}字段`" @update:model-value="changeField(c,$event)" />
          <PmsSelectControl :model-value="c.operator" :options="availableOperators(c)" v-bind="controls" :append-to="popupHost" :aria-label="`条件${i+1}匹配方式`" @update:model-value="changeOperator(c,$event)" />
          <div class="condition-value">
            <span v-if="['isEmpty','notEmpty'].includes(c.operator)" class="no-value">无需填写值</span>
            <template v-else>
              <el-button v-if="c.operator==='reference'" class="reference-value" type="primary" plain :disabled="locked" :aria-label="`条件${i+1}引用值`" @click="openReference(c)">{{ Array.isArray(c.value)&&c.value.length ? `已选 ${c.value.length} 条 · 修改引用` : '选择引用记录' }}</el-button>
              <PmsSelectControl v-else-if="fieldOf(c)?.type === 'enum'&&!isTextOperator(c)" :key="c.operator" v-model="c.value" :options="fieldOf(c)?.options || []" :multiple="['in','notIn'].includes(c.operator)" collapse-tags collapse-tags-tooltip clearable filterable placeholder="请选择" v-bind="controls" :append-to="popupHost" :error="errors[c.id]" :aria-label="`条件${i+1}值`" :aria-invalid="Boolean(errors[c.id])" :aria-describedby="errors[c.id] ? `${errorPrefix}-${c.id}` : undefined" />
              <PmsTextControl v-else-if="!fieldOf(c) || fieldOf(c)?.type === 'text'||isTextOperator(c)" v-model="c.value as QueryScalar" placeholder="请输入条件值" v-bind="controls" :error="errors[c.id]" :aria-label="`条件${i+1}值`" :aria-invalid="Boolean(errors[c.id])" :aria-describedby="errors[c.id] ? `${errorPrefix}-${c.id}` : undefined" />
              <template v-else-if="fieldOf(c)?.type === 'number'">
                <PmsNumberControl v-model="c.value as number | null" :controls="false" v-bind="controls" :error="errors[c.id]" :aria-label="`条件${i+1}值`" :aria-invalid="Boolean(errors[c.id])" :aria-describedby="errors[c.id] ? `${errorPrefix}-${c.id}` : undefined" />
                <template v-if="c.operator === 'between'"><span class="range-separator">至</span><PmsNumberControl v-model="c.valueEnd as number | null" :controls="false" v-bind="controls" :error="errors[c.id]" :aria-label="`条件${i+1}结束值`" :aria-invalid="Boolean(errors[c.id])" :aria-describedby="errors[c.id] ? `${errorPrefix}-${c.id}` : undefined" /></template>
              </template>
              <template v-else-if="fieldOf(c)?.type === 'date'">
                <PmsDateControl v-model="c.value as QueryScalar" placeholder="选择日期" v-bind="controls" :append-to="popupHost" :error="errors[c.id]" :aria-label="`条件${i+1}值`" :aria-invalid="Boolean(errors[c.id])" :aria-describedby="errors[c.id] ? `${errorPrefix}-${c.id}` : undefined" />
                <template v-if="c.operator === 'between'"><span class="range-separator">至</span><PmsDateControl v-model="c.valueEnd" placeholder="结束日期" v-bind="controls" :append-to="popupHost" :error="errors[c.id]" :aria-label="`条件${i+1}结束值`" :aria-invalid="Boolean(errors[c.id])" :aria-describedby="errors[c.id] ? `${errorPrefix}-${c.id}` : undefined" /></template>
              </template>
            </template>
          </div>
          <el-button class="remove-condition" type="danger" plain :icon="Delete" :disabled="locked" :aria-label="`删除条件${i+1}`" title="删除条件" @click="draft.splice(i,1)" />
          <p v-if="errors[c.id]" :id="`${errorPrefix}-${c.id}`" class="condition-error" role="alert">{{ errors[c.id] }}</p>
        </div>
        <p v-if="!draft.length" class="empty-conditions">暂无附加条件</p>
      </div>
      <footer><el-button type="primary" plain :icon="Plus" :disabled="locked || applying || !fields.length || draft.length >= 20" @click="add">增加条件</el-button><div><el-button type="warning" plain :disabled="applying" @click="emit('cancel')">取消</el-button><el-button type="success" :loading="applying" :disabled="locked" @click="apply">应用条件</el-button></div></footer>
      <PmsQueryReference v-if="activeReference" v-model="referenceOpened" :reference="activeReference" :value="referenceCondition?.operator==='reference'&&Array.isArray(referenceCondition.value)?referenceCondition.value:[]" @confirm="confirmReference" />
    </section>
  </el-config-provider>
</template>
<style scoped>
.condition-editor { font-size:12px; color:var(--pms-text-secondary); }
header { display:flex; align-items:center; gap:12px; padding-bottom:10px; border-bottom:1px solid var(--pms-border-soft); }
header strong { color:var(--pms-text); font-size:13px; font-weight:500; }
header span { flex:1; color:var(--pms-text-muted); }
.condition-labels,.condition-row { display:grid; grid-template-columns:140px 112px minmax(0,1fr) 24px; gap:8px; }
.condition-labels { padding:10px 0 6px; color:var(--pms-text-muted); }
.condition-scroll { max-height:330px; overflow:auto; }
.condition-row { align-items:start; margin-bottom:8px; }
.condition-value { display:flex; align-items:center; gap:6px; min-width:0; }
.condition-value>.pms-form-control { flex:1; min-width:0; width:0; }
.reference-value { width:100%; min-width:0; overflow:hidden; text-overflow:ellipsis; }
.range-separator { color:var(--pms-text-muted); }
.no-value { line-height:24px; color:var(--pms-text-muted); }
.condition-error { grid-column:3; margin:0; color:var(--pms-danger); line-height:18px; }
.remove-condition { width:24px; padding:0; }
.empty-conditions { padding:16px; text-align:center; color:var(--pms-text-muted); }
footer { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:10px; padding-top:10px; border-top:1px solid var(--pms-border-soft); }
footer>div { display:flex; gap:8px; }
@media(max-width:700px) {
  .condition-labels { display:none; }
  .condition-row { grid-template-columns:minmax(0,1fr) minmax(0,1fr) 24px; border-bottom:1px solid var(--pms-border-soft); padding:8px 0; margin:0; }
  .condition-value { grid-row:2; grid-column:1/3; }
  .remove-condition { grid-row:1; grid-column:3; }
  .condition-error { grid-column:1/3; }
  header span { display:none; } header { justify-content:space-between; }
}
</style>
