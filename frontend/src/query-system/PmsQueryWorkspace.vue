<script setup lang="ts">
import { computed, nextTick, ref, watch, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Search, RefreshLeft, Setting, Plus, ArrowUp, ArrowDown, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { PmsSelectControl, PmsTextControl, PmsCheckboxControl, PmsFormDrawer, PmsFormField } from '@/form-system'
import { cloneQuery, operatorsForField, operatorLabel, type QueryCondition, type QueryField } from './core'
import { instantiateDefinitions, activeQuery, loadPersonalSchemes, saveScheme, deleteScheme, selectScheme, schemeStorageKey, settingsDefinitions, validateDefinitions, validateReferences, prepareDefinitions, type QueryDefinition, type QueryScheme } from './workspace'
import PmsQueryConditionRow from './PmsQueryConditionRow.vue'
const props=withDefaults(defineProps<{listKey:string;fields:QueryField[];defaults:QueryDefinition[];entryMode?:'document'|'report';ready?:boolean;loading?:boolean;modelValue?:QueryCondition[];snapshot?:()=>object;legacySchemes?:(storage:Pick<Storage,'getItem'>,userId:number|string,listKey:string)=>{schemes:QueryScheme[];warnings:string[]}}>(),{entryMode:'report',ready:true,loading:false})
const emit=defineEmits<{'update:modelValue':[value:QueryCondition[]];query:[conditions:QueryCondition[],preferences:object];clearColumns:[]}>()
const auth=useAuthStore(),schemes=ref<QueryScheme[]>([]),selected=ref(''),definitions=ref<QueryDefinition[]>([]),conditions=ref<QueryCondition[]>([])
const opened=ref(false),name=ref(''),originalName=ref(''),isDefault=ref(false),editDefinitions=ref<QueryDefinition[]>([]),errors=ref<Record<number,string>>({}),configErrors=ref<Record<string,string>>({}),busy=ref(false),host=ref<HTMLElement|null>(null)
const schemeWarning=ref('')
const storageWarning=ref(''),storageError=ref(''),storageWritable=ref(true),pendingQuery=ref(false)
const creating=ref(false),deleting=ref(false),editorWarning=ref(''),editBaseline=ref<QueryScheme|null>(null),editorSnapshot=ref('')
let settingsRun=0,settingsPreferences:object={},discardPromise:Promise<boolean>|null=null
const canEdit=computed(()=>creating.value||!!originalName.value)
const editorValue=()=>JSON.stringify({name:name.value,isDefault:isDefault.value,definitions:editDefinitions.value})
const settingsDirty=computed(()=>opened.value&&canEdit.value&&editorValue()!==editorSnapshot.value)
const messageOf=(error:unknown,fallback:string)=>typeof (error as Error)?.message==='string'?(error as Error).message:fallback
const pendingEntry=ref('')
let run=0,initializedKey='',settingsOwner='',preferences:object={}
const key=computed(()=>auth.user?.id?schemeStorageKey(auth.user.id,props.listKey):'')
const available=computed(()=>props.fields.filter(f=>!conditions.value.some(c=>c.field===f.field)))
const dirty=computed(()=>JSON.stringify(conditions.value)!==JSON.stringify(instantiateDefinitions(definitions.value)))
function change(value:QueryCondition[]){run++;busy.value=false;pendingEntry.value='';conditions.value=cloneQuery(value);errors.value={};emit('update:modelValue',cloneQuery(value))}
function load(){
  const restored=selectScheme(schemes.value,selected.value,props.defaults)
  const prepared=prepareDefinitions(restored.definitions,props.fields)
  definitions.value=prepared.definitions;preferences=restored.preferences
  schemeWarning.value=prepared.invalidFields.length?'此方案包含已取消的字段，请在方案设置中确认并保存后查询；原方案尚未修改':''
  change(instantiateDefinitions(definitions.value));emit('clearColumns')
}
function closeSettings(){settingsRun++;discardPromise=null;settingsOwner='';name.value='';originalName.value='';isDefault.value=false;editDefinitions.value=[];configErrors.value={};creating.value=false;deleting.value=false;editorWarning.value='';editBaseline.value=null;editorSnapshot.value='';settingsPreferences={};opened.value=false}
watch(key,()=>{run++;busy.value=false;pendingEntry.value='';schemeWarning.value='';storageError.value='';storageWarning.value='';pendingQuery.value=false;closeSettings();schemes.value=[];selected.value='';definitions.value=[];preferences={};change([]);initializedKey=''},{flush:'sync'})
watch(opened,value=>{if(!value)closeSettings()},{flush:'sync'})
function refreshSchemes(){
  try{
    const legacy=props.legacySchemes&&auth.user?.id?()=>props.legacySchemes!(localStorage,auth.user!.id,props.listKey):undefined
    const loaded=loadPersonalSchemes(localStorage,key.value,legacy)
    schemes.value=loaded.schemes;storageWarning.value=loaded.warnings.join('；');storageWritable.value=loaded.writable;storageError.value=''
    return true
  }catch(error){storageWritable.value=false;storageError.value=messageOf(error,'方案读取失败，原记录保留');return false}
}
watch([key,()=>props.ready,()=>props.fields.length],()=>{
  if(!key.value||!props.ready||!props.fields.length||initializedKey===key.value)return
  initializedKey=key.value
  const readable=refreshSchemes()
  selected.value=schemes.value.find(p=>p.isDefault)?.name||'';load()
  if(readable&&props.entryMode==='document')pendingEntry.value=key.value
},{immediate:true})
watch([pendingEntry,()=>props.ready,()=>props.loading,()=>props.fields],async()=>{
  const owner=pendingEntry.value
  if(!owner||!props.ready||props.loading)return
  await nextTick()
  if(owner!==pendingEntry.value||owner!==key.value||initializedKey!==owner||!props.ready||props.loading)return
  await query()
},{flush:'post',immediate:true,deep:true})
watch(()=>props.modelValue,value=>{if(value&&JSON.stringify(value)!==JSON.stringify(conditions.value))change(value)},{deep:true})
watch(()=>props.fields,()=>{run++;busy.value=false},{deep:true})
onBeforeUnmount(()=>{run++;pendingEntry.value='';initializedKey=''})
function reset(){load()}
function update(c:QueryCondition,value:QueryCondition){change(conditions.value.map(row=>row.id===c.id?value:row))}
function removable(c:QueryCondition){const f=props.fields.find(f=>f.field===c.field);return !f?.required&&(!f?.requiredGroup||conditions.value.filter(row=>props.fields.find(field=>field.field===row.field)?.requiredGroup===f.requiredGroup).length>1)}
function add(){const f=available.value[0];if(!f||conditions.value.length>=20)return;change([...conditions.value,{id:Math.max(0,...conditions.value.map(c=>c.id))+1,field:f.field,operator:f.type==='enum'?'in':operatorsForField(f).find(op=>op!=='reference')!,value:null,valueEnd:null,schemaVersion:2}]);nextTick(()=>host.value?.querySelector<HTMLInputElement>(`[data-field="${f.field}"] input`)?.focus())}
async function query(){
  if(!props.ready||busy.value||props.loading||schemeWarning.value||storageError.value)return
  const snapshot=cloneQuery(conditions.value),validation=activeQuery(snapshot,props.fields)
  errors.value=validation.errors;if(Object.keys(errors.value).length)return
  const currentRun=++run;busy.value=true
  try{const failures=await validateReferences(validation.conditions,props.fields,()=>currentRun===run);if(currentRun!==run||!failures)return;errors.value=failures;if(!Object.keys(failures).length){pendingEntry.value='';pendingQuery.value=false;emit('query',validation.conditions,cloneQuery(preferences))}}
  catch{if(currentRun===run)errors.value[0]='引用校验失败，请重试；原查询结果保持不变'}finally{if(currentRun===run)busy.value=false}
}
function loadEditor(target:string,useCurrent=false,asNew=false){
  const saved=schemes.value.find(p=>p.name===target),source=saved?.definitions||props.defaults
  const prepared=prepareDefinitions(source,props.fields)
  creating.value=asNew;originalName.value=asNew?'':saved?.name||'';name.value=asNew?'':saved?.name||'';isDefault.value=asNew?false:!!saved?.isDefault
  editBaseline.value=asNew?null:cloneQuery(saved||null)
  const fromPage=asNew||useCurrent&&!!saved&&target===selected.value
  editDefinitions.value=fromPage?settingsDefinitions(definitions.value,conditions.value,props.fields):settingsDefinitions(prepared.definitions,instantiateDefinitions(prepared.definitions),props.fields)
  settingsPreferences=cloneQuery(fromPage?(props.snapshot?.()||preferences):(saved?.preferences||{}))
  editorWarning.value=prepared.invalidFields.length?'此方案含已取消的字段，保存将移除这些条件；请核对后确认保存':''
  configErrors.value={};editorSnapshot.value=editorValue()
}
function openSettings(){if(!key.value||!props.ready||initializedKey!==key.value)return;settingsRun++;discardPromise=null;refreshSchemes();settingsOwner=key.value;loadEditor(selected.value,true);opened.value=true}
async function canDiscard(){
  if(!settingsDirty.value)return true
  if(!discardPromise){const confirmation=ElMessageBox.confirm('放弃尚未保存的方案修改？','未保存修改',{type:'warning',confirmButtonText:'放弃修改',cancelButtonText:'取消'}).then(()=>true,()=>false).finally(()=>{if(discardPromise===confirmation)discardPromise=null});discardPromise=confirmation}
  return discardPromise
}
function sameSettings(owner:string,ticket:number){return opened.value&&settingsOwner===owner&&key.value===owner&&initializedKey===owner&&ticket===settingsRun}
function ownsSettings(owner:string,ticket:number){return sameSettings(owner,ticket)&&props.ready}
async function selectEditor(value:unknown){
  if(deleting.value)return
  const owner=settingsOwner,ticket=++settingsRun
  if(await canDiscard()&&ownsSettings(owner,ticket))loadEditor(typeof value==='string'?value:'')
}
async function newScheme(){
  if(deleting.value)return
  const owner=settingsOwner,ticket=++settingsRun
  if(await canDiscard()&&ownsSettings(owner,ticket))loadEditor('',false,true)
}
async function beforeClose(done:()=>void){
  if(deleting.value)return
  const owner=settingsOwner,ticket=++settingsRun
  if(await canDiscard()&&ownsSettings(owner,ticket))done()
}
function requestClose(){return beforeClose(()=>{opened.value=false})}
onBeforeRouteLeave(async()=>{
  if(!opened.value)return true
  if(deleting.value)return false
  const owner=settingsOwner,ticket=++settingsRun
  return await canDiscard()&&ownsSettings(owner,ticket)
})
function move(i:number,delta:number){const next=i+delta;if(next<0||next>=editDefinitions.value.length)return;const values=[...editDefinitions.value];[values[i],values[next]]=[values[next]!,values[i]!];editDefinitions.value=values}
function save(){
  if(!opened.value||!settingsOwner||settingsOwner!==key.value||initializedKey!==settingsOwner||!props.ready){closeSettings();return}
  if(!canEdit.value||deleting.value)return
  if(!storageWritable.value){configErrors.value.name=storageError.value||storageWarning.value||'方案暂不能保存，原数据保留';return}
  configErrors.value=validateDefinitions(editDefinitions.value,props.fields);if(!name.value.trim())configErrors.value.name='请填写方案名称';if(Object.keys(configErrors.value).length)return
  try{
    const active=creating.value||originalName.value===selected.value
    schemes.value=saveScheme(localStorage,key.value,schemes.value,{name:name.value,definitions:editDefinitions.value,isDefault:isDefault.value,preferences:active?(props.snapshot?.()||preferences):settingsPreferences},props.fields,originalName.value,editBaseline.value)
    if(active){selected.value=name.value.trim();load();pendingQuery.value=true}
    opened.value=false;ElMessage.success(active?'方案已保存，点击查询后生效':'方案已保存')
  }
  catch(error){configErrors.value.name=messageOf(error,'保存失败，请检查浏览器存储空间')}
}
async function deleteCurrent(){
  if(!originalName.value||!editBaseline.value||creating.value||deleting.value||!storageWritable.value)return
  const owner=settingsOwner,ticket=++settingsRun,target=originalName.value,baseline=cloneQuery(editBaseline.value)
  deleting.value=true
  try{
    await ElMessageBox.confirm(`删除查询方案“${target}”？${settingsDirty.value?'未保存的修改也将放弃。':''}`,'删除个人方案',{type:'warning',confirmButtonText:'删除方案',cancelButtonText:'取消'})
    if(!ownsSettings(owner,ticket))return
    try{
      schemes.value=deleteScheme(localStorage,owner,target,baseline)
      if(selected.value===target||baseline.isDefault||!schemes.value.length){selected.value='';load();pendingQuery.value=true}
      opened.value=false;ElMessage.success('方案已删除')
    }catch(error){configErrors.value.name=messageOf(error,'删除失败，原方案保留')}
  }catch{/* Cancellation keeps the original scheme and editor. */}
  finally{if(sameSettings(owner,ticket))deleting.value=false}
}
defineExpose({getConditions:()=>cloneQuery(conditions.value),reset,query})
function defaultValue(d:QueryDefinition){
  const field=props.fields.find(f=>f.field===d.field)
  const label=(value:unknown)=>value==null||value===''?'不限':field?.options?.find(o=>o.value===value)?.label??String(value)
  return Array.isArray(d.value)?d.value.length?d.value.map(label).join('、'):'不限':d.operator==='between'?`${label(d.value)} 至 ${label(d.valueEnd)}`:label(d.value)
}
</script>
<template>
  <section ref="host" class="pms-query-workspace pms-query-density" aria-label="查询方案">
    <div class="pms-query-workspace-toolbar">
      <slot name="before" />
      <div class="pms-query-scheme-select"><PmsSelectControl v-model="selected" :options="schemes.map(p=>({value:p.name,label:p.name+(p.isDefault?' · 默认':'' )}))" size="compact" clearable placeholder="系统默认" aria-label="查询方案" :disabled="!ready" @update:model-value="load" @option-select="load" /></div>
      <el-button class="pms-button-auxiliary" :icon="Setting" :disabled="!ready" @click="openSettings">方案设置</el-button>
      <el-button type="primary" :icon="Search" :loading="loading||busy" :disabled="!ready || !!schemeWarning || !!storageError || Object.keys(activeQuery(conditions,fields).errors).length>0" @click="query">查询</el-button>
      <el-button class="pms-button-auxiliary" :icon="RefreshLeft" :disabled="!ready" @click="reset">重置</el-button>
      <el-button class="pms-button-auxiliary" :icon="Plus" :disabled="!ready || !available.length || conditions.length>=20" @click="add">添加条件</el-button>
      <span v-if="dirty||pendingQuery" class="pms-query-dirty" role="status">{{pendingQuery?'条件已变更，待查询':'条件已修改'}}</span><slot name="after" />
    </div>
    <form class="pms-query-workspace-fields" aria-label="统一查询条件" @submit.prevent="query">
      <PmsQueryConditionRow v-for="(c,i) in conditions" :key="c.id" :condition="c" :fields="fields" :conditions="conditions" :removable="removable(c)" :error="errors[c.id]" :prefix="`查询${i+1}`" @update="update(c,$event)" @remove="change(conditions.filter(row=>row.id!==c.id))" />
      <p v-if="errors[0]" class="pms-query-error" role="alert">{{errors[0]}}</p>
      <p v-if="schemeWarning" class="pms-query-warning" role="alert">{{schemeWarning}}</p>
      <p v-if="storageError||storageWarning" class="pms-query-warning" role="alert">{{storageError||storageWarning}}</p>
    </form>
    <PmsFormDrawer v-model="opened" class="pms-query-settings-drawer" title="查询方案设置" :busy="deleting" :before-close="beforeClose">
      <PmsFormField label="我的方案" field-id="query-scheme-editor"><PmsSelectControl id="query-scheme-editor" :model-value="originalName||null" :options="schemes.map(p=>({value:p.name,label:p.name+(p.isDefault?' · 默认':'' )}))" clearable :placeholder="creating?'新建方案':'系统默认'" aria-label="维护查询方案" :disabled="deleting" @update:model-value="selectEditor" /></PmsFormField>
      <div class="pms-query-settings-name"><PmsFormField label="方案名称" field-id="query-scheme-name" :required="canEdit" :error="configErrors.name"><PmsTextControl id="query-scheme-name" v-model="name" :readonly="!canEdit" :maxlength="60" placeholder="系统默认" aria-label="方案名称" /></PmsFormField><PmsCheckboxControl v-model="isDefault" :disabled="!canEdit||deleting" aria-label="默认方案">默认方案</PmsCheckboxControl><el-button type="primary" :icon="Plus" :disabled="deleting||!storageWritable" @click="newScheme">新建方案</el-button></div>
      <p v-if="storageError||storageWarning||editorWarning" class="pms-query-warning" role="alert">{{storageError||storageWarning||editorWarning}}</p>
      <template v-if="canEdit">
      <div class="pms-query-settings-labels"><span>默认展示</span><span>字段名 / 条件 / 默认值</span><span>顺序</span></div>
      <div v-for="(d,i) in editDefinitions" :key="d.field" class="pms-query-settings-row">
        <PmsCheckboxControl v-model="d.shown" :disabled="fields.find(f=>f.field===d.field)?.required" :aria-label="`${fields.find(f=>f.field===d.field)?.label}默认展示`" />
        <PmsQueryConditionRow :condition="{...d,id:i+1}" :fields="fields" :conditions="editDefinitions.filter(v=>v.shown).map((v,i)=>({...v,id:i+1}))" regular fixed-field :error="configErrors[d.field]" :prefix="`默认${fields.find(f=>f.field===d.field)?.label}`" @update="value=>Object.assign(d,value)" />
        <div class="pms-query-order"><el-button type="primary" text :icon="ArrowUp" :disabled="i===0" title="上移" :aria-label="`上移${d.field}`" @click="move(i,-1)" /><el-button type="primary" text :icon="ArrowDown" :disabled="i===editDefinitions.length-1" title="下移" :aria-label="`下移${d.field}`" @click="move(i,1)" /></div>
      </div>
      </template>
      <div v-else class="pms-query-system-default" aria-label="系统默认只读条件"><div v-for="d in editDefinitions.filter(d=>d.shown)" :key="d.field"><span>{{fields.find(f=>f.field===d.field)?.label}}</span><span>{{operatorLabel(d.operator,fields.find(f=>f.field===d.field)?.type||'text')}}</span><span>{{defaultValue(d)}}</span></div></div>
      <template #secondary><span class="pms-query-personal">仅当前用户 · {{editDefinitions.filter(d=>d.shown).length}} 个默认条件</span><el-button v-if="originalName&&!creating" type="danger" plain :icon="Delete" :disabled="!storageWritable" :loading="deleting" @click="deleteCurrent">删除方案</el-button></template>
      <template #footer><div class="pms-query-settings-actions"><el-button class="pms-button-auxiliary" :disabled="deleting" @click="requestClose">取消</el-button><el-button type="primary" :disabled="!canEdit||!storageWritable||deleting" @click="save">保存方案</el-button></div></template>
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
.pms-query-system-default>div{display:grid;grid-template-columns:110px 80px minmax(0,1fr);gap:8px;padding:8px 0;border-bottom:1px solid var(--pms-border-soft);font-size:13px;color:var(--pms-text-secondary);}
.pms-query-system-default span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.pms-query-settings-name{display:flex;align-items:center;gap:12px;padding-bottom:8px;}.pms-query-settings-name>.pms-form-field{flex:1;min-width:0;}.pms-query-settings-name>.el-button{margin:0;}
.pms-query-settings-name,.pms-query-settings-row{--pms-form-control-height-regular:32px;--pms-font-size-base:13px;}
.pms-query-settings-name>.el-button{height:32px;}
.pms-query-settings-labels,.pms-query-settings-row{display:grid;grid-template-columns:64px minmax(0,1fr) 44px;gap:8px;padding:8px 0;border-bottom:1px solid var(--pms-border-soft);}
.pms-query-settings-labels{font-size:12px;color:var(--pms-text-muted);}.pms-query-settings-row{align-items:start;}.pms-query-settings-row>.pms-form-control{padding-top:6px;}
.pms-query-order{display:flex;}.pms-query-order>.el-button{width:22px;padding:0;margin:0;}
.pms-query-settings-actions{display:flex;gap:8px;}.pms-query-settings-actions>.el-button{height:32px;margin:0;}
.pms-query-settings-drawer :deep(.pms-form-drawer__footer){flex-wrap:wrap;}
.pms-query-settings-drawer :deep(.pms-form-drawer__secondary){display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
@media(max-width:700px){.pms-query-settings-name{flex-wrap:wrap;}.pms-query-settings-name>.pms-form-field{flex-basis:100%;}.pms-query-settings-row{grid-template-columns:24px minmax(0,1fr) 24px;gap:4px;}.pms-query-order{flex-direction:column;}}
@media(max-width:560px){.pms-query-workspace-fields>.pms-condition-row{max-width:none;flex-basis:100%;}}
</style>
<style>.pms-query-settings-drawer{--pms-drawer-width:740px;}</style>
