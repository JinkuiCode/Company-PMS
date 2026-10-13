<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { PmsFormDrawer } from '@/form-system'
import { downloadFeedbackFile, retryFeedbackMail, type FeedbackRow } from '@/api/feedback'
import { useAuthStore } from '@/stores/auth'
import { mailLabels, feedbackTone } from '@/feedback/model'
const props=defineProps<{modelValue:boolean;row:FeedbackRow|null;loading:boolean;error:string;label:(code:string,value:unknown,fallback?:string)=>string}>()
const emit=defineEmits<{'update:modelValue':[boolean];edit:['handle'|'supplement'];refresh:[]}>()
const auth=useAuthStore(), busy=ref(false)
const tab=ref('内容')
watch(()=>props.row?.id,()=>{tab.value='内容'})
const date=(value:string)=>value?.replace('T',' ').slice(0,19)||''
async function download(file:any){busy.value=true;try{await downloadFeedbackFile(file.id,file.filename)}catch{ElMessage.error('附件下载失败，请重试')}finally{busy.value=false}}
async function retry(id:number){busy.value=true;try{await retryFeedbackMail(id);ElMessage.success('已重新加入通知队列');emit('refresh')}catch{ElMessage.error('通知重试失败，请刷新后检查权限与状态')}finally{busy.value=false}}
</script>
<template>
 <PmsFormDrawer penetrable :model-value="modelValue" title="提报详情" :busy="busy" @update:model-value="emit('update:modelValue',$event)">
  <div v-loading="loading" class="feedback-detail" :aria-busy="loading">
   <div v-if="error" role="alert">{{error}} <el-button link type="primary" @click="emit('refresh')">重试</el-button></div>
   <template v-else-if="row">
    <div class="feedback-detail-heading"><span>{{row.report_no}}</span><span class="pms-status" :class="'pms-status-'+feedbackTone(row.status_id)">{{label('feedback_status',row.status_id)}}</span></div>
    <h3>{{row.title}}</h3>
    <dl class="feedback-facts">
     <dt>提报类型</dt><dd>{{label('feedback_type',row.type_id)}}</dd><dt>涉及模块</dt><dd>{{label('feedback_module',row.module_id)}}</dd>
     <dt>具体类别</dt><dd>{{row.category_name}}</dd><dt>影响程度</dt><dd>{{label('feedback_impact',row.impact_id)}}</dd>
     <dt>提报人</dt><dd>{{row.author_name}}</dd><dt>提报时间</dt><dd>{{date(row.created_at)}}</dd><dt>处理人</dt><dd>{{row.handler_name||'尚未受理'}}</dd>
    </dl>
    <div class="feedback-detail-tabs" role="tablist" aria-label="提报详情页签"><button v-for="name in ['内容','跟进记录','邮件通知']" :key="name" role="tab" :aria-selected="tab===name" :class="{active:tab===name}" @click="tab=name">{{name}}</button></div>
    <template v-if="tab==='内容'">
    <section v-for="field in [{key:'description',label:'详细说明'},{key:'steps',label:'复现步骤'},{key:'expected_result',label:'期望结果'}]" :key="field.key" v-show="(row as any)[field.key]"><h4>{{field.label}}</h4><p>{{(row as any)[field.key]}}</p></section>
    <section><h4>附件 <span>{{row.attachments?.length||0}} / 5</span></h4><p v-if="!row.attachments?.length" class="feedback-muted">暂无附件</p><div v-for="file in row.attachments" :key="file.id" class="feedback-file"><span>{{file.filename}}</span><el-button link type="primary" :disabled="busy" @click="download(file)">下载</el-button></div></section>
    <section><h4>处理意见与结论</h4><p>{{row.opinion||'尚未填写处理意见'}}</p><p v-if="row.outcome_id">结论：{{label('feedback_outcome',row.outcome_id)}} · 归因：{{label('feedback_cause',row.cause_id)}}</p></section>
    </template>
    <section v-else-if="tab==='跟进记录'"><h4>跟进记录</h4><article v-for="event in row.followups" :key="event.id" class="feedback-event"><div><strong>{{({create:'提交提报',handle:'处理提报',supplement:'补充信息'} as Record<string,string>)[event.action]||event.action}}</strong><span>{{event.actor_name}}</span><span>{{date(event.created_at)}}</span><span class="pms-status" :class="'pms-status-'+feedbackTone(event.status_id)">{{label('feedback_status',event.status_id)}}</span></div><p>{{event.description}}</p><small v-if="event.outcome_id">结论：{{label('feedback_outcome',event.outcome_id)}} · 归因：{{label('feedback_cause',event.cause_id)}}</small></article></section>
    <section v-else><h4>邮件通知</h4><div v-for="notice in row.notifications" :key="notice.id" class="feedback-notice"><div><span>{{notice.audience==='admins'?'系统管理员':'提报人'}}</span><span>{{mailLabels[notice.status]||notice.status}}</span><small>{{date(notice.sent_at||notice.created_at)}}</small><p v-if="notice.error_message">{{notice.error_message}}</p></div><el-button v-if="auth.hasPermission('feedback:notification:retry')&&auth.hasPermission('feedback:handle')&&['waiting','failed','unknown'].includes(notice.status)" link type="primary" :disabled="busy" @click="retry(notice.id)">重试</el-button></div></section>
   </template>
  </div>
  <template #footer><el-button type="warning" plain :disabled="busy" @click="emit('update:modelValue',false)">关闭</el-button><el-button v-if="row&&row.author_id===auth.user?.id&&auth.hasPermission('feedback:supplement')" type="primary" plain :disabled="loading||busy||!!error" @click="emit('edit','supplement')">补充信息</el-button><el-button v-if="auth.hasPermission('feedback:handle')&&row" type="success" :disabled="loading||busy||!!error" @click="emit('edit','handle')">处理提报</el-button></template>
 </PmsFormDrawer>
</template>
<style scoped>
.feedback-detail{min-height:120px;padding-top:12px}.feedback-detail-heading,.feedback-event>div,.feedback-file,.feedback-notice{display:flex;align-items:center;gap:8px;justify-content:space-between;min-width:0}.feedback-detail h3{font-size:16px;overflow-wrap:anywhere;margin:10px 0}.feedback-facts{display:grid;grid-template-columns:80px minmax(0,1fr);gap:6px;margin:12px 0}.feedback-facts dt,.feedback-muted,.feedback-event span,.feedback-notice small{color:var(--pms-text-secondary)}.feedback-facts dd{margin:0;overflow-wrap:anywhere}.feedback-detail section{border-top:1px solid var(--pms-border-soft);padding:8px 0}.feedback-detail h4{margin:0 0 6px;font-size:13px}.feedback-detail h4 span{font-weight:400;color:var(--pms-text-secondary)}.feedback-detail p{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;margin:4px 0}.feedback-file>span{min-width:0;overflow-wrap:anywhere}.feedback-event{border-left:2px solid var(--pms-primary-soft);padding:6px 0 8px 10px}.feedback-event>div{justify-content:flex-start;flex-wrap:wrap}.feedback-event small{color:var(--pms-text-secondary)}.feedback-notice{border-bottom:1px solid var(--pms-border-soft);padding:6px 0}.feedback-notice>div{display:flex;flex-wrap:wrap;align-items:center;gap:8px;min-width:0}.feedback-notice p{flex-basis:100%}.feedback-notice .el-button{flex-shrink:0}
</style>
<style scoped>.feedback-detail-tabs{display:flex;gap:8px;border-top:1px solid var(--pms-border-soft);padding:8px 0}.feedback-detail-tabs button{border:0;border-radius:4px;background:var(--pms-surface);color:var(--pms-text-secondary);font:inherit;padding:4px 10px;cursor:pointer}.feedback-detail-tabs button.active{background:var(--pms-primary-soft);color:var(--pms-primary)}</style>
