<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {useAuthStore} from '@/stores/auth'
import PmsDataList from '@/components/PmsDataList.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import PmsDocumentHistory from '@/document-history/PmsDocumentHistory.vue'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import PmsQueryColumnHeader from '@/query-system/PmsQueryColumnHeader.vue'
import {useSystemQuery,loadCompleteDataset} from '@/query-system/system-adapter'
import type {QueryCondition} from '@/query-system/core'
import {DEFAULT_PAGE_SIZE,PAGE_SIZE_OPTIONS,pmsActionColumn} from '@/config/listUi'
import {PmsFormDrawer,PmsFormField,PmsTextControl,PmsTextareaControl} from '@/form-system'
import {createDetailSwitch} from '@/utils/detailSwitch'
import {archiveDraftManagementApi as api,type ManagedDraft,type ManagedDraftDetail} from '@/api/archiveDraftManagement'

const auth=useAuthStore()
const allowed=computed(()=>auth.hasPermission('project:archive:view')&&auth.hasPermission('project:archive:draft:manage'))
const items=ref<ManagedDraft[]>([]),loading=ref(false),failed=ref(false),denied=ref(false),ready=ref(false)
const page=ref(1),pageSize=ref(DEFAULT_PAGE_SIZE),busy=ref(false),error=ref(''),unknownDelete=ref('')
const detailOpen=ref(false),detailLoading=ref(false),detailFailed=ref(false),detailTab=ref('content')
const selected=ref<ManagedDraftDetail|null>(null),selectedSummary=ref<ManagedDraft|null>(null)
const fields=()=>[
 {field:'project_code',label:'项目编号',type:'text' as const},
 {field:'project_name',label:'项目名称',type:'text' as const},
 {field:'creator_name',label:'创建人',type:'text' as const},
 {field:'product_line_id',label:'产品线',type:'enum' as const,options:[...new Map(items.value.map(row=>[row.product_line_id,row.product_line_name])).entries()].map(([value,label])=>({value,label}))},
]
const query=useSystemQuery(fields,['project_code'],{ready:()=>ready.value&&!loading.value&&!failed.value&&!denied.value,requireQuery:true,pagination:{page,size:pageSize}})
const filtered=computed(()=>query.submitted.value?query.topRows(items.value):[])
const visible=computed(()=>query.submitted.value?query.pageRows(items.value):[])
let listTicket=0,entryLoaded=false
function clearSnapshot(){
 listTicket++;loading.value=false;items.value=[];selected.value=null;selectedSummary.value=null;detailOpen.value=false
 detailSwitch.invalidate();detailLoading.value=false;query.clearColumns()
}
function forbid(){
 denied.value=true;clearSnapshot()
}
function historyDenied(status:403|404){
 if(status===403)forbid()
 else{clearSnapshot();error.value='草稿不存在或已无权访问，请重新查询。'}
}
async function load(){
 if(!allowed.value){forbid();return}
 const ticket=++listTicket
 loading.value=true;failed.value=false;query.clearColumns()
 try{
  const result=await loadCompleteDataset<ManagedDraft,{items:ManagedDraft[];total:number}>(api.list,500,()=>ticket===listTicket,row=>row.id)
  if(ticket!==listTicket)return
  items.value=result.items;denied.value=false;unknownDelete.value=''
  page.value=Math.min(page.value,Math.max(1,Math.ceil(filtered.value.length/pageSize.value)))
 }catch(e:any){
  if(ticket!==listTicket)return
  items.value=[]
  if(e.response?.status===403)forbid();else failed.value=true
 }finally{if(ticket===listTicket)loading.value=false}
}
async function initialize(){
 await load()
 if(!failed.value&&!denied.value){entryLoaded=true;ready.value=true}
}
async function runQuery(conditions:QueryCondition[],preferences:object={}){
 if(busy.value)return
 query.submit(conditions)
 const size=(preferences as {pageSize?:number}).pageSize
 if(size&&PAGE_SIZE_OPTIONS.includes(size))pageSize.value=size
 page.value=1;error.value=''
 if(entryLoaded)entryLoaded=false
 else await load()
}
const detailSwitch=createDetailSwitch<ManagedDraft>(async()=>!busy.value,async(row,current)=>{
 selectedSummary.value=row;selected.value=null;detailTab.value='content';detailLoading.value=true;detailFailed.value=false;error.value=''
 try{
  const result=await api.get(row.id)
  if(current())selected.value=result
 }catch(e:any){
  if(!current())return
  if([403,404].includes(e.response?.status)){
   if(e.response.status===403)forbid()
   else{clearSnapshot();error.value='草稿不存在或已无权查看，请重新查询。'}
  }else{detailFailed.value=true;error.value='草稿加载失败，请重试。'}
 }finally{if(current())detailLoading.value=false}
})
async function open(row:ManagedDraft){
 if(busy.value||!allowed.value)return
 detailOpen.value=true
 await detailSwitch.select(row)
}
function selectRow(row:ManagedDraft){if(detailOpen.value&&!busy.value)void detailSwitch.select(row)}
function closeDetail(done?:()=>void){
 if(busy.value)return
 detailSwitch.invalidate();detailOpen.value=false;detailLoading.value=false;selected.value=null;selectedSummary.value=null;done?.()
}
async function remove(row:ManagedDraft|undefined=selected.value??undefined){
 if(!row||busy.value||detailLoading.value||!allowed.value||unknownDelete.value)return
 busy.value=true
 try{
  try{await ElMessageBox.confirm(`确定删除草稿“${row.project_code} · ${row.project_name}”吗？删除后不能继续填写，操作记录保留。`,'删除草稿',{type:'warning',confirmButtonText:'确认删除',cancelButtonText:'取消',confirmButtonClass:'el-button--danger'})}catch{return}
  error.value=''
  await api.delete(row.id,row.version)
  if(selectedSummary.value?.id===row.id){detailSwitch.invalidate();detailOpen.value=false;selected.value=null;selectedSummary.value=null}
  items.value=items.value.filter(item=>item.id!==row.id);query.clearColumns()
  ElMessage.success('草稿已删除')
  await load()
 }catch(e:any){
  const status=e.response?.status
  if(status===403){forbid();return}
  if(status===409)error.value='草稿已有更新，本次删除未执行；请重新查询后再处理。'
  else if(status===404){clearSnapshot();error.value='草稿已删除或已无权访问，请重新查询。'}
  else{unknownDelete.value=row.id;error.value='删除结果暂未确认，请重新查询后核对，不要重复点击。'}
 }finally{busy.value=false}
}
function savedTime(value:string){return new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})}
onMounted(initialize)
watch(allowed,value=>{if(!value)forbid()})
watch(()=>JSON.stringify({dept:auth.user?.dept_id,scope:auth.user?.data_scope,lines:auth.user?.product_line_ids,all:auth.hasPermission('business:data:all')}),()=>{
 if(allowed.value){clearSnapshot();error.value='数据范围已变化，请重新查询。'}
})
onBeforeUnmount(()=>{listTicket++;detailSwitch.invalidate()})
</script>
<template>
 <section class="draft-management-page">
  <p v-if="denied||!allowed" role="alert" class="pms-list-load-error">当前无权管理草稿，请联系管理员核对权限。</p>
  <PmsDataList v-else :show-scrollbar="false" class="pms-system-page">
   <template #toolbar-right><PmsPageGuide page="archiveDrafts"/></template>
   <template #filters><PmsQueryWorkspace v-model="query.draft.value" entry-mode="document" list-key="archive-draft-management" :fields="query.fields.value" :defaults="query.defaults.value" :ready="ready" :loading="loading||busy" @query="runQuery" @clear-columns="query.clearColumns"/></template>
   <template #grid>
    <p v-if="error&&!detailOpen" role="alert" class="pms-form-field__error">{{error}}</p>
    <p v-if="unknownDelete&&!error&&!detailOpen" role="alert" class="pms-form-field__error">有一份草稿的删除结果暂未确认，请重新查询后核对。</p>
    <p v-if="failed" role="alert" class="pms-list-load-error">草稿加载失败 <el-button class="pms-button-navigation" @click="ready?load():initialize()">重试</el-button></p>
    <el-table v-else :data="visible" v-loading="loading" height="100%" border stripe class="pms-dense-table" row-key="id" :row-class-name="({row}:any)=>selectedSummary?.id===row.id?'current-row':''" @row-click="selectRow">
     <el-table-column prop="project_code" label="项目编号" width="180" header-align="center"><template #header><PmsQueryColumnHeader :params="{contextQuery:()=>query.columnContext,field:'project_code',displayName:'项目编号'}"/></template></el-table-column>
     <el-table-column prop="project_name" label="项目名称" min-width="210" header-align="center"><template #header><PmsQueryColumnHeader :params="{contextQuery:()=>query.columnContext,field:'project_name',displayName:'项目名称'}"/></template></el-table-column>
     <el-table-column label="创建人" prop="creator_name" width="180" header-align="center"><template #header><PmsQueryColumnHeader :params="{contextQuery:()=>query.columnContext,field:'creator_name',displayName:'创建人'}"/></template><template #default="{row}">{{row.creator_name}}<span v-if="!row.creator_enabled" class="draft-management-inactive">已停用</span></template></el-table-column>
     <el-table-column prop="product_line_name" label="产品线" width="140" header-align="center"><template #header><PmsQueryColumnHeader :params="{contextQuery:()=>query.columnContext,field:'product_line_id',displayName:'产品线'}"/></template></el-table-column>
     <el-table-column label="保存时间" width="165" header-align="center"><template #default="{row}">{{savedTime(row.updated_at)}}</template></el-table-column>
     <el-table-column label="操作" :width="pmsActionColumn(2).width" fixed="right" header-align="center"><template #default="{row}"><div class="draft-management-row-actions"><span><el-button link size="small" class="pms-button-navigation" :disabled="busy" @click.stop="open(row)">查看</el-button></span><span><el-button link size="small" type="danger" :disabled="busy||detailLoading||Boolean(unknownDelete)" @click.stop="remove(row)">删除</el-button></span></div></template></el-table-column>
    </el-table>
   </template>
   <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="filtered.length"/></template>
  </PmsDataList>
  <PmsFormDrawer v-model="detailOpen" title="草稿详情" :busy="busy" penetrable :before-close="closeDetail">
   <p v-if="detailLoading" role="status">正在加载草稿内容</p>
   <p v-if="error" role="alert" class="pms-form-field__error">{{error}}</p>
   <p v-if="unknownDelete&&!error" role="alert" class="pms-form-field__error">有一份草稿的删除结果暂未确认，请重新查询后核对，再继续删除。</p>
   <el-button v-if="detailFailed&&selectedSummary" class="pms-button-navigation" :disabled="busy" @click="open(selectedSummary)">重新加载</el-button>
   <template v-if="selected&&!detailLoading">
    <el-tabs v-model="detailTab"><el-tab-pane label="草稿内容" name="content"/><el-tab-pane label="操作记录" name="history"/></el-tabs>
    <template v-if="detailTab==='content'">
     <p v-for="warning in selected.warnings" :key="warning" role="status" class="draft-management-warning">{{warning}}</p>
     <div class="draft-management-fields"><PmsFormField v-for="field in selected.fields" :key="field.key" :field-id="'managed-draft-'+field.key" :label="field.label"><PmsTextareaControl v-if="field.display.length>100||field.display.includes('\n')" :id="'managed-draft-'+field.key" :model-value="field.display" :aria-label="field.label" :rows="3" readonly/><PmsTextControl v-else :id="'managed-draft-'+field.key" :model-value="field.display" :aria-label="field.label" readonly/></PmsFormField></div>
    </template>
    <PmsDocumentHistory v-else :key="selected.id" resource="draft_management" :entity-id="selected.id" :revision="selected.version" @access-denied="historyDenied"/>
   </template>
   <template #footer><el-button v-if="selected" type="danger" plain :disabled="busy||detailLoading||Boolean(unknownDelete)" @click="remove()">删除</el-button></template>
  </PmsFormDrawer>
 </section>
</template>
<style scoped>
.draft-management-page{height:100%;min-height:0;display:flex;flex-direction:column}
.draft-management-fields{display:grid;gap:16px}
.draft-management-inactive{margin-left:8px;font-size:12px;color:var(--pms-warning)}
.draft-management-warning{font-size:13px;line-height:1.6;color:var(--pms-warning)}
.draft-management-row-actions{display:inline-flex;align-items:center;flex-wrap:nowrap;gap:var(--pms-action-gap);white-space:nowrap}
</style>
