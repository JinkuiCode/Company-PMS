<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { PmsFormDrawer, PmsFormField, PmsTextControl, PmsSelectControl, PmsTextareaControl, type PmsOption } from '@/form-system'
import { freshFeedback, categoryCode, allowedOutcomes, validateFeedback, newSubmissionId, type FeedbackMode } from '@/feedback/model'
import { submitFeedback, handleFeedback, supplementFeedback, uploadFeedbackFile, type FeedbackRow } from '@/api/feedback'
import { confirmDetailSwitch } from '@/composables/confirmDetailSwitch'
import { useAuthStore } from '@/stores/auth'
import { Paperclip } from '@element-plus/icons-vue'
const auth=useAuthStore()
const props=defineProps<{modelValue:boolean; mode:FeedbackMode; row:FeedbackRow|null; options:(code:string)=>PmsOption[]}>()
const emit=defineEmits<{'update:modelValue':[boolean]; saved:[FeedbackRow]}>()
const draft=ref<Record<string,any>>(freshFeedback()), initial=ref(''), errors=ref<Record<string,string>>({}), files=ref<File[]>([]), busy=ref(false), saved=ref<FeedbackRow|null>(null), banner=ref('')
const dirty=computed(()=>JSON.stringify(draft.value)!==initial.value || files.value.length>0)
const submissionId=ref('')
watch(()=>props.modelValue,value=>{if(value)submissionId.value=''})
const title=computed(()=>props.mode==='new'?'新增提报':props.mode==='handle'?'处理提报':'补充信息')
watch(draft,()=>{if(Object.keys(errors.value).length)errors.value=validateFeedback(draft.value,props.mode)},{deep:true})
watch(()=>props.modelValue,value=>{if(!value)return; saved.value=null; files.value=[]; errors.value={};banner.value='';draft.value=props.mode==='new'?freshFeedback():props.mode==='handle'?{status_id:props.row?.status_id===1?2:props.row?.status_id,outcome_id:props.row?.outcome_id||null,cause_id:props.row?.cause_id||null,opinion:''}:{description:''};initial.value=JSON.stringify(draft.value)})
const selects=computed(()=>props.mode==='new'?[{key:'type_id',label:'提报类型',code:'feedback_type'},{key:'module_id',label:'涉及模块',code:'feedback_module'},{key:'category_id',label:'具体类别',code:categoryCode(draft.value.type_id)},{key:'impact_id',label:'影响程度',code:'feedback_impact'}]:props.mode==='handle'?[{key:'status_id',label:'处理状态',code:'feedback_status'},{key:'outcome_id',label:'处理结论',code:'feedback_outcome'},{key:'cause_id',label:'处理归因',code:'feedback_cause'}]:[])
const texts=computed<{key:string;label:string;short?:boolean}[]>(()=>props.mode==='new'?[{key:'title',label:'标题',short:true},{key:'description',label:'详细说明'},...(draft.value.type_id===1?[{key:'steps',label:'复现步骤'}]:[]),{key:'expected_result',label:'期望结果'}]:props.mode==='handle'?[{key:'opinion',label:'处理意见'}]:[{key:'description',label:'补充信息'}])
function options(field:{key:string;code:string}) { return field.key==='outcome_id'?props.options(field.code).filter(option=>allowedOutcomes(draft.value.status_id).includes(Number(option.value))):props.options(field.code) }
function required(key:string) {return props.mode==='new'||props.mode==='supplement'||key==='status_id'||key==='opinion'||[5,6].includes(draft.value.status_id)}
function changed(key:string) {if(key==='type_id')draft.value.category_id=null;if(key==='status_id'&&draft.value.outcome_id&&!allowedOutcomes(draft.value.status_id).includes(draft.value.outcome_id))draft.value.outcome_id=null}
async function save() {
 if(busy.value)return false
 errors.value=validateFeedback(draft.value,props.mode); if(Object.keys(errors.value).length){await nextTick();document.getElementById('feedback-'+Object.keys(errors.value)[0])?.focus();return false}
 busy.value=true;banner.value=''
 try {
  let row:FeedbackRow
  if(!submissionId.value)submissionId.value=newSubmissionId()
  if(saved.value) row=saved.value
  else if(props.mode==='new') row=await submitFeedback({...draft.value,submission_id:submissionId.value})
  else if(!props.row) return false
  else row=props.mode==='handle'?await handleFeedback(props.row.id,{...draft.value,version:props.row.version}):await supplementFeedback(props.row.id,{...draft.value,version:props.row.version})
  saved.value=row;emit('saved',row)
  while(files.value.length){const result=await uploadFeedbackFile(row,files.value[0]!,props.mode==='new'?submissionId.value:undefined);row={...row,version:result.version};saved.value=row;files.value.shift()}
  initial.value=JSON.stringify(draft.value); submissionId.value='';emit('saved',row);emit('update:modelValue',false);ElMessage.success('已保存；邮件通知由后台独立处理');return true
 }catch(error:any){banner.value=saved.value?'提报内容已保存，部分附件尚未上传。可重试附件或取消后在详情中补传。':error.response?.status===409?'记录已被修改，请取消并刷新详情后重试':'保存失败，请检查填写内容后重试';return false}
 finally{busy.value=false}
}
async function guard() {
 if(busy.value)return false
 if(!dirty.value)return true
 const decision=await confirmDetailSwitch()
 if(decision==='save')return save()
 return decision==='discard'
}
async function close(done?:()=>void){if(await guard()){emit('update:modelValue',false);done?.()}}
function addFiles(event:Event){const input=event.target as HTMLInputElement; const incoming=Array.from(input.files||[]);input.value='';if(files.value.length+incoming.length+(props.row?.attachments?.length||0)>5||incoming.some(file=>file.size>10*1024*1024)){ElMessage.warning('每单最多5个附件，每个不超过10MB');return}files.value.push(...incoming)}
defineExpose({guard,save,dirty})
</script>
<template>
 <PmsFormDrawer penetrable :model-value="modelValue" :title="title" :busy="busy" :before-close="close" @update:model-value="emit('update:modelValue',$event)">
  <p v-if="banner" class="feedback-form-error" role="alert">{{banner}}</p>
  <form @submit.prevent="save" :aria-busy="busy">
   <h3 class="pms-form-drawer__section">{{mode==='new'?'分类与定位':row?.report_no}}</h3>
   <PmsFormField v-for="field in selects" :key="field.key" v-slot="{describedBy,invalid}" :field-id="'feedback-'+field.key" :label="field.label" :required="required(field.key)" :error="errors[field.key]">
    <PmsSelectControl :id="'feedback-'+field.key" v-model="draft[field.key]" :options="options(field)" :disabled="busy||!!saved||field.key==='category_id'&&!draft.type_id" :error="errors[field.key]" :aria-describedby="describedBy" :aria-invalid="invalid" :aria-required="required(field.key)" :aria-label="field.label" clearable placeholder="请选择" @update:model-value="changed(field.key)" />
   </PmsFormField>
   <h3 v-if="mode==='new'" class="pms-form-drawer__section">提报内容</h3>
   <PmsFormField v-for="field in texts" :key="field.key" v-slot="{describedBy,invalid}" :field-id="'feedback-'+field.key" :label="field.label" required :error="errors[field.key]">
    <PmsTextControl v-if="field.short" :id="'feedback-'+field.key" v-model="draft[field.key]" :disabled="busy||!!saved" :maxlength="200" :error="errors[field.key]" :aria-describedby="describedBy" :aria-invalid="invalid" :aria-label="field.label" aria-required="true" />
    <PmsTextareaControl v-else :id="'feedback-'+field.key" v-model="draft[field.key]" :disabled="busy||!!saved" :rows="4" :maxlength="10000" :error="errors[field.key]" :aria-describedby="describedBy" :aria-invalid="invalid" :aria-label="field.label" aria-required="true" />
   </PmsFormField>
   <PmsFormField field-id="feedback-files" label="截图与附件" hint="最多5个，每个10MB；图片、PDF、Excel、Word">
    <label class="feedback-upload pms-button-auxiliary" for="feedback-files"><el-icon><Paperclip /></el-icon>添加附件<input id="feedback-files" type="file" multiple accept=".png,.jpg,.jpeg,.gif,.webp,.pdf,.xls,.xlsx,.doc,.docx" :disabled="busy" @change="addFiles"></label>
    <ul class="feedback-files"><li v-for="(file,index) in files" :key="index"><span>{{file.name}}</span><el-button link type="danger" :disabled="busy" aria-label="移除附件" @click="files.splice(index,1)">移除</el-button></li></ul>
   </PmsFormField>
   <template v-if="mode==='new'">
    <h3 class="pms-form-drawer__section">提报人信息</h3>
    <PmsFormField field-id="feedback-author" label="提报人"><PmsTextControl id="feedback-author" :model-value="auth.user?.real_name||''" readonly /></PmsFormField>
    <PmsFormField field-id="feedback-email" label="接收邮箱"><PmsTextControl id="feedback-email" :model-value="auth.user?.email||''" readonly /><p v-if="!auth.user?.email" class="feedback-form-error">用户档案尚未维护邮箱，处理结果将无法通过邮件通知。</p></PmsFormField>
    <p class="feedback-mail-hint">提交后通知系统管理员，处理结果更新后通知提报人。通知由后台独立发送。</p>
   </template>
  </form>
  <template #footer><el-button type="warning" plain :disabled="busy" @click="close()">取消</el-button><el-button type="success" :loading="busy" @click="save">{{saved?'重试附件':mode==='new'?'提交提报':'保存'}}</el-button></template>
 </PmsFormDrawer>
</template>
<style scoped>
.feedback-form-error{color:var(--pms-danger);line-height:1.6}.feedback-files{padding:0;margin:4px 0;list-style:none}.feedback-files li{display:flex;align-items:center;gap:8px;min-width:0}.feedback-files span{min-width:0;overflow-wrap:anywhere;flex:1}.feedback-upload{display:inline-flex;align-items:center;gap:6px;position:relative;overflow:hidden;height:32px;padding:0 12px;border:1px solid var(--pms-border);border-radius:4px;cursor:pointer}.feedback-upload input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%}.feedback-upload:focus-within{outline:2px solid var(--pms-primary);outline-offset:2px}.feedback-mail-hint{color:var(--pms-text-secondary);font-size:12px;line-height:1.6}
</style>
