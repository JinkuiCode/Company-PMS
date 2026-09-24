<script setup lang="ts">
import { computed, ref } from 'vue'
import { Filter, Plus, Delete } from '@element-plus/icons-vue'
import { PmsTextControl, PmsNumberControl, PmsSelectControl, PmsDateControl } from '@/form-system'
import { cloneQuery, operatorsFor, operatorLabels, validateConditions, type ReportCondition, type ReportField } from './state'
const props = withDefaults(defineProps<{ modelValue: ReportCondition[]; fields: ReportField[]; disabled?: boolean; triggerLabel?: string }>(), {triggerLabel:'更多条件'})
const emit = defineEmits<{ 'update:modelValue': [value: ReportCondition[]] }>()
const opened = ref(false), draft = ref<ReportCondition[]>([]), error = ref('')
// Keep child popups inside this popover's click boundary, outside the scrolling rows.
const popupHost = ref<HTMLElement>()
const options = computed(() => props.fields.map(f => ({value:f.field,label:f.label})))
const field = (c: ReportCondition) => props.fields.find(f => f.field === c.field)
const ops = (c: ReportCondition) => (field(c)?.operators || operatorsFor(field(c)?.type || 'text')).map(value => ({value,label:operatorLabels[value]}))
function open() { draft.value = cloneQuery(props.modelValue); error.value = '' }
function change(c: ReportCondition) { c.operator = ops(c)[0]!.value; clearValue(c) }
function clearValue(c: ReportCondition) { c.value = null; c.valueEnd = null; error.value = '' }
function add() { const f = props.fields[0]; if (f) draft.value.push({id:Math.max(0,...draft.value.map(c=>c.id))+1,field:f.field,operator:(f.operators || operatorsFor(f.type))[0]!,value:null,valueEnd:null}) }
function apply() { error.value = validateConditions(draft.value, props.fields); if (!error.value) { emit('update:modelValue', cloneQuery(draft.value)); opened.value = false } }
</script>
<template>
  <el-popover v-model:visible="opened" trigger="click" placement="bottom-end" :width="730" popper-class="pms-report-condition-popper">
    <template #reference><el-button size="small" :icon="Filter" :disabled="disabled" @click="open">{{ triggerLabel }}{{ modelValue.length ? ` (${modelValue.length})` : '' }}</el-button></template>
    <section ref="popupHost" class="pms-report-conditions" role="dialog" aria-label="更多条件">
      <header><strong>筛选条件</strong><span>同时满足全部条件</span></header>
      <div class="pms-report-condition-labels"><span>字段</span><span>运算符</span><span>值</span></div>
      <div class="pms-report-condition-rows">
        <p v-if="!draft.length" class="pms-report-condition-empty">尚未添加条件</p>
        <div v-for="(c,i) in draft" :key="c.id" class="pms-report-condition-row">
          <PmsSelectControl v-model="c.field" :append-to="popupHost" :options="options" filterable size="compact" :aria-label="`条件${i+1}字段`" @update:model-value="change(c)" />
          <PmsSelectControl v-model="c.operator" :append-to="popupHost" :options="ops(c)" size="compact" :aria-label="`条件${i+1}运算符`" @update:model-value="clearValue(c)" />
          <div class="pms-report-condition-value">
            <span v-if="['isEmpty','notEmpty'].includes(c.operator)">无需填写值</span>
            <PmsSelectControl v-else-if="field(c)?.type === 'enum'" v-model="c.value" :append-to="popupHost" :options="field(c)?.options || []" size="compact" :aria-label="`条件${i+1}值`" />
            <template v-else-if="field(c)?.type === 'date'">
              <PmsDateControl v-model="c.value" :append-to="popupHost" size="compact" :aria-label="`条件${i+1}值`" />
              <template v-if="c.operator === 'between'"><span>至</span><PmsDateControl v-model="c.valueEnd" :append-to="popupHost" size="compact" :aria-label="`条件${i+1}结束值`" /></template>
            </template>
            <template v-else-if="field(c)?.type === 'number'">
              <PmsNumberControl v-model="c.value as number | null" :controls="false" size="compact" :aria-label="`条件${i+1}值`" />
              <template v-if="c.operator === 'between'"><span>至</span><PmsNumberControl v-model="c.valueEnd as number | null" :controls="false" size="compact" :aria-label="`条件${i+1}结束值`" /></template>
            </template>
            <PmsTextControl v-else v-model="c.value" size="compact" clearable :aria-label="`条件${i+1}值`" placeholder="输入筛选值" />
          </div>
          <el-button text :icon="Delete" :aria-label="`删除条件${i+1}`" title="删除条件" @click="draft.splice(i,1)" />
        </div>
      </div>
      <p v-if="error" role="alert" class="pms-report-condition-error">{{ error }}</p>
      <el-button class="pms-report-condition-add" text type="primary" size="small" :icon="Plus" :disabled="draft.length >= 20" @click="add">添加条件</el-button>
      <footer><el-button size="small" text @click="draft = []; error = ''">清空条件</el-button><div><el-button size="small" @click="opened = false">取消</el-button><el-button type="primary" size="small" @click="apply">应用条件</el-button></div></footer>
    </section>
  </el-popover>
</template>
<style>
.pms-report-condition-popper { max-width: calc(100vw - 28px); padding: 0 !important; border-radius: 8px; }
.pms-report-conditions header, .pms-report-conditions footer { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:14px 18px; }
.pms-report-conditions header { border-bottom:1px solid var(--pms-border-soft); }
.pms-report-conditions header span, .pms-report-condition-labels, .pms-report-condition-value>span { font-size:11px; color:var(--pms-text-muted); }
.pms-report-condition-labels, .pms-report-condition-row { display:grid; grid-template-columns:155px 118px minmax(0,1fr) 30px; gap:10px; align-items:center; }
.pms-report-condition-labels { padding:14px 18px 8px; }
.pms-report-condition-rows { padding:0 18px; max-height:320px; overflow:auto; }
.pms-report-condition-row { margin-bottom:10px; }
.pms-report-condition-value { display:flex; min-width:0; align-items:center; gap:6px; }
.pms-report-condition-value>.pms-form-control { flex:1; min-width:0; width:0; }
.pms-report-condition-empty { padding:20px; text-align:center; color:var(--pms-text-muted); }
.pms-report-condition-error { color:var(--pms-danger); padding:0 18px; }
.pms-report-condition-add { margin:0 0 8px 12px; }
.pms-report-conditions footer { border-top:1px solid var(--pms-border-soft); }
@media(max-width:700px) { .pms-report-condition-labels { display:none; } .pms-report-condition-rows { padding-top:12px; } .pms-report-condition-row { grid-template-columns:minmax(0,1fr) minmax(0,1fr) 28px; } .pms-report-condition-value { grid-row:2; grid-column:1/3; } .pms-report-condition-row>.el-button { grid-row:1/3; grid-column:3; } }
</style>
