<script setup lang="ts">
import { computed, nextTick, ref, watch, onBeforeUnmount } from 'vue'
import { Search, RefreshLeft, Setting, Plus, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { PmsSelectControl, PmsTextControl, PmsCheckboxControl, PmsFormDrawer, PmsFormField } from '@/form-system'
import { cloneQuery, operatorsForField, type QueryCondition, type QueryField } from './core'
import { instantiateDefinitions, activeQuery, readSchemes, saveScheme, selectScheme, schemeStorageKey, settingsDefinitions, validateDefinitions, validateReferences, prepareDefinitions, type QueryDefinition, type QueryScheme } from './workspace'
import PmsQueryConditionRow from './PmsQueryConditionRow.vue'
const props=withDefaults(defineProps<{listKey:string;fields:QueryField[];defaults:QueryDefinition[];ready?:boolean;loading?:boolean;modelValue?:QueryCondition[];snapshot?:()=>object;legacySchemes?:(storage:Pick<Storage,'getItem'>,userId:number|string,listKey:string)=>{schemes:QueryScheme[];warnings:string[]}}>(),{ready:true,loading:false})
const emit=defineEmits<{'update:modelValue':[value:QueryCondition[]];query:[conditions:QueryCondition[],preferences:object];clearColumns:[]}>()
const auth=useAuthStore(),schemes=ref<QueryScheme[]>([]),selected=ref(''),definitions=ref<QueryDefinition[]>([]),conditions=ref<QueryCondition[]>([])
const opened=ref(false),name=ref(''),originalName=ref(''),isDefault=ref(false),editDefinitions=ref<QueryDefinition[]>([]),errors=ref<Record<number,string>>({}),configErrors=ref<Record<string,string>>({}),busy=ref(false),host=ref<HTMLElement|null>(null)
const schemeWarning=ref('')
let run=0,initializedKey='',settingsOwner='',preferences:object={}
const key=computed(()=>auth.user?.id?schemeStorageKey(auth.user.id,props.listKey):'')
const available=computed(()=>props.fields.filter(f=>!conditions.value.some(c=>c.field===f.field)))
const dirty=computed(()=>JSON.stringify(conditions.value)!==JSON.stringify(instantiateDefinitions(definitions.value)))
function change(value:QueryCondition[]){run++;busy.value=false;conditions.value=cloneQuery(value);errors.value={};emit('update:modelValue',cloneQuery(value))}
function load(){
  const restored=selectScheme(schemes.value,selected.value,props.defaults)
  const prepared=prepareDefinitions(restored.definitions,props.fields)
  definitions.value=prepared.definitions;preferences=restored.preferences
  schemeWarning.value=prepared.invalidFields.length?'此方案包含已取消的字段，请在方案设置中确认并保存后查询；原方案尚未修改':''
  change(instantiateDefinitions(definitions.value));emit('clearColumns')
}
function closeSettings(){settingsOwner='';name.value='';originalName.value='';isDefault.value=false;editDefinitions.value=[];configErrors.value={};opened.value=false}
watch(key,()=>{run++;busy.value=false;schemeWarning.value='';closeSettings();initializedKey=''},{flush:'sync'})
watch(opened,value=>{if(!value)closeSettings()},{flush:'sync'})
watch([key,()=>props.ready],()=>{
  if(!key.value||!props.ready||!props.fields.length||initializedKey===key.value)return
  initializedKey=key.value
  try{schemes.value=readSchemes(localStorage,key.value)}catch(error){schemes.value=[];ElMessage.warning(String(error))}
  if(props.legacySchemes && auth.user?.id){
    try{
      const legacy=props.legacySchemes(localStorage,auth.user.id,props.listKey)
      schemes.value.push(...legacy.schemes.filter(p=>!schemes.value.some(existing=>existing.name===p.name)))
      if(legacy.warnings.length)ElMessage.warning(legacy.warnings.join('；'))
    }catch{ElMessage.warning('旧个人方案未读取，原记录保留，请重新配置')}
  }
  selected.value=schemes.value.find(p=>p.isDefault)?.name||'';load()
},{immediate:true})
watch(()=>props.modelValue,value=>{if(value&&JSON.stringify(value)!==JSON.stringify(conditions.value))change(value)},{deep:true})
watch(()=>props.fields,()=>{run++;busy.value=false},{deep:true})
onBeforeUnmount(()=>{run++})
function reset(){load()}
function update(c:QueryCondition,value:QueryCondition){change(conditions.value.map(row=>row.id===c.id?value:row))}
function add(){const f=available.value[0];if(!f||conditions.value.length>=20)return;change([...conditions.value,{id:Math.max(0,...conditions.value.map(c=>c.id))+1,field:f.field,operator:f.type==='enum'?'in':operatorsForField(f).find(op=>op!=='reference')!,value:null,valueEnd:null,schemaVersion:2}]);nextTick(()=>host.value?.querySelector<HTMLInputElement>(`[data-field="${f.field}"] input`)?.focus())}
async function query(){
  if(!props.ready||busy.value||props.loading||schemeWarning.value)return
  const snapshot=cloneQuery(conditions.value),validation=activeQuery(snapshot,props.fields)
  errors.value=validation.errors;if(Object.keys(errors.value).length)return
  const currentRun=++run;busy.value=true
  try{const failures=await validateReferences(validation.conditions,props.fields,()=>currentRun===run);if(currentRun!==run||!failures)return;errors.value=failures;if(!Object.keys(failures).length)emit('query',validation.conditions,cloneQuery(preferences))}
  catch{if(currentRun===run)errors.value[0]='引用校验失败，请重试；原查询结果保持不变'}finally{if(currentRun===run)busy.value=false}
}
function openSettings(){if(!key.value||!props.ready||initializedKey!==key.value)return;settingsOwner=key.value;name.value=selected.value;originalName.value=selected.value;isDefault.value=!!schemes.value.find(p=>p.name===selected.value)?.isDefault;editDefinitions.value=settingsDefinitions(definitions.value,conditions.value,props.fields);configErrors.value={};opened.value=true}
function newScheme(){name.value='';originalName.value='';isDefault.value=false;configErrors.value={}}
function move(i:number,delta:number){const next=i+delta;if(next<0||next>=editDefinitions.value.length)return;const values=[...editDefinitions.value];[values[i],values[next]]=[values[next]!,values[i]!];editDefinitions.value=values}
function save(){
  if(!opened.value||!settingsOwner||settingsOwner!==key.value||initializedKey!==settingsOwner||!props.ready){closeSettings();return}
  configErrors.value=validateDefinitions(editDefinitions.value,props.fields);if(!name.value.trim())configErrors.value.name='请填写方案名称';if(Object.keys(configErrors.value).length)return
  try{schemes.value=saveScheme(localStorage,key.value,schemes.value,{name:name.value,definitions:editDefinitions.value,isDefault:isDefault.value,preferences:props.snapshot?.()||preferences},props.fields,originalName.value);selected.value=name.value.trim();load();opened.value=false;ElMessage.success('方案已保存，点击查询后生效')}
  catch(error){configErrors.value.name=error instanceof Error?error.message:'保存失败，请检查浏览器存储空间'}
}
defineExpose({getConditions:()=>cloneQuery(conditions.value),reset,query})
</script>
<template>
  <section ref="host" class="pms-query-workspace pms-query-density" aria-label="查询方案">
    <div class="pms-query-workspace-toolbar">
      <slot name="before" />
      <div class="pms-query-scheme-select"><PmsSelectControl v-model="selected" :options="schemes.map(p=>({value:p.name,label:p.name+(p.isDefault?' · 默认':'' )}))" size="compact" clearable placeholder="系统默认" aria-label="查询方案" :disabled="!ready" @update:model-value="load" @option-select="load" /></div>
      <el-button class="pms-button-auxiliary" :icon="Setting" :disabled="!ready" @click="openSettings">方案设置</el-button>
      <el-button type="primary" :icon="Search" :loading="loading||busy" :disabled="!ready || !!schemeWarning || Object.keys(activeQuery(conditions,fields).errors).length>0" @click="query">查询</el-button>
      <el-button class="pms-button-auxiliary" :icon="RefreshLeft" :disabled="!ready" @click="reset">重置</el-button>
      <el-button class="pms-button-auxiliary" :icon="Plus" :disabled="!ready || !available.length || conditions.length>=20" @click="add">添加条件</el-button>
      <span v-if="dirty" class="pms-query-dirty">条件已修改</span><slot name="after" />
    </div>
    <form class="pms-query-workspace-fields" aria-label="统一查询条件" @submit.prevent="query">
      <PmsQueryConditionRow v-for="(c,i) in conditions" :key="c.id" :condition="c" :fields="fields" :conditions="conditions" :removable="!fields.find(f=>f.field===c.field)?.required" :error="errors[c.id]" :prefix="`查询${i+1}`" @update="update(c,$event)" @remove="change(conditions.filter(row=>row.id!==c.id))" />
      <p v-if="errors[0]" class="pms-query-error" role="alert">{{errors[0]}}</p>
      <p v-if="schemeWarning" class="pms-query-warning" role="alert">{{schemeWarning}}</p>
    </form>
    <PmsFormDrawer v-model="opened" class="pms-query-settings-drawer" title="查询方案设置">
      <div class="pms-query-settings-name"><PmsFormField label="方案名称" field-id="query-scheme-name" required :error="configErrors.name"><PmsTextControl id="query-scheme-name" v-model="name" :maxlength="60" aria-label="方案名称" /></PmsFormField><PmsCheckboxControl v-model="isDefault" aria-label="默认方案">默认方案</PmsCheckboxControl><el-button type="primary" :icon="Plus" @click="newScheme">新建方案</el-button></div>
      <div class="pms-query-settings-labels"><span>默认展示</span><span>字段名 / 条件 / 默认值</span><span>顺序</span></div>
      <div v-for="(d,i) in editDefinitions" :key="d.field" class="pms-query-settings-row">
        <PmsCheckboxControl v-model="d.shown" :disabled="fields.find(f=>f.field===d.field)?.required" :aria-label="`${fields.find(f=>f.field===d.field)?.label}默认展示`" />
        <PmsQueryConditionRow :condition="{...d,id:i+1}" :fields="fields" :conditions="editDefinitions.map((v,i)=>({...v,id:i+1}))" regular fixed-field :error="configErrors[d.field]" :prefix="`默认${fields.find(f=>f.field===d.field)?.label}`" @update="value=>Object.assign(d,value)" />
        <div class="pms-query-order"><el-button type="primary" text :icon="ArrowUp" :disabled="i===0" title="上移" :aria-label="`上移${d.field}`" @click="move(i,-1)" /><el-button type="primary" text :icon="ArrowDown" :disabled="i===editDefinitions.length-1" title="下移" :aria-label="`下移${d.field}`" @click="move(i,1)" /></div>
      </div>
      <template #secondary><span class="pms-query-personal">仅当前用户 · {{editDefinitions.filter(d=>d.shown).length}} 个默认条件</span></template>
      <template #footer><div class="pms-query-settings-actions"><el-button class="pms-button-auxiliary" @click="opened=false">取消</el-button><el-button type="primary" @click="save">保存方案</el-button></div></template>
    </PmsFormDrawer>
  </section>
</template>
<style scoped>
.pms-query-workspace{min-width:0;}
.pms-query-workspace-toolbar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding-bottom:6px;border-bottom:1px solid var(--pms-border-soft);}
.pms-query-workspace-toolbar>.el-button{margin:0;}
.pms-query-scheme-select{width:132px;min-width:0;}.pms-query-scheme-select>.pms-form-control{width:100%;}
.pms-query-workspace-fields{display:flex;flex-wrap:wrap;gap:6px 10px;padding:6px 0;margin:0;}
.pms-query-workspace-fields>.pms-condition-row{flex:0 0 326px;max-width:100%;}.pms-query-workspace-fields>.is-range{flex-basis:434px;}
.pms-query-error{flex-basis:100%;color:var(--pms-danger);margin:0;}
.pms-query-warning{flex-basis:100%;color:var(--pms-warning);margin:0;font-size:12px;}
.pms-query-dirty,.pms-query-personal{font-size:12px;color:var(--pms-text-muted);}
.pms-query-settings-name{display:flex;align-items:center;gap:12px;padding-bottom:8px;}.pms-query-settings-name>.pms-form-field{flex:1;min-width:0;}.pms-query-settings-name>.el-button{margin:0;}
.pms-query-settings-name,.pms-query-settings-row{--pms-form-control-height-regular:32px;--pms-font-size-base:13px;}
.pms-query-settings-name>.el-button{height:32px;}
.pms-query-settings-labels,.pms-query-settings-row{display:grid;grid-template-columns:64px minmax(0,1fr) 44px;gap:8px;padding:8px 0;border-bottom:1px solid var(--pms-border-soft);}
.pms-query-settings-labels{font-size:12px;color:var(--pms-text-muted);}.pms-query-settings-row{align-items:start;}.pms-query-settings-row>.pms-form-control{padding-top:6px;}
.pms-query-order{display:flex;}.pms-query-order>.el-button{width:22px;padding:0;margin:0;}
.pms-query-settings-actions{display:flex;gap:8px;}.pms-query-settings-actions>.el-button{height:32px;margin:0;}
@media(max-width:700px){.pms-query-settings-name{flex-wrap:wrap;}.pms-query-settings-name>.pms-form-field{flex-basis:100%;}.pms-query-settings-row{grid-template-columns:24px minmax(0,1fr) 24px;gap:4px;}.pms-query-order{flex-direction:column;}}
@media(max-width:560px){.pms-query-workspace-fields>.pms-condition-row{max-width:none;flex-basis:100%;}}
</style>
<style>.pms-query-settings-drawer{--pms-drawer-width:740px;}</style>
