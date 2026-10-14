<script setup lang="ts">
import {computed,defineComponent,h,onMounted,onBeforeUnmount,ref} from 'vue'
import {ElMessage} from 'element-plus'
import {Back} from '@element-plus/icons-vue'
import PmsDataList from '@/components/PmsDataList.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import {AgGridVue} from 'ag-grid-vue3'
import {AllCommunityModule,ModuleRegistry,type GridApi,type GridReadyEvent,type RowClickedEvent} from 'ag-grid-community'
import {decorateQueryColumns} from '@/query-system/column-grid'
import {chineseLocaleText} from '@/utils/agGridLocale'
import {useSystemQuery} from '@/query-system/system-adapter'
import {type QueryCondition,type QueryField} from '@/query-system/core'
import PmsPageGuide from '@/page-guide/PmsPageGuide.vue'
import BusinessExportControl from '@/business-export/BusinessExportControl.vue'
import {businessExportSnapshot} from '@/business-export/snapshot'
import {DEFAULT_PAGE_SIZE,PMS_GRID_OPTIONS,pmsActionColumn} from '@/config/listUi'
import {PmsFormField,PmsTextareaControl} from '@/form-system'
import {useEnumOptions} from '@/composables/useEnumOptions'
import {createDetailSwitch} from '@/utils/detailSwitch'
import {confirmDetailSwitch} from '@/composables/confirmDetailSwitch'
import request from '@/utils/request'

const emit=defineEmits<{'back':[];'changed':[]}>()
ModuleRegistry.registerModules([AllCommunityModule])
const enums=useEnumOptions(['archive_change_status']),ready=ref(false),metaFailed=ref(false)
const columns=[{field:'project_code',label:'项目编号',width:130},{field:'author_name',label:'提交人',width:110},{field:'approver_name',label:'审批人',width:110},{field:'reason',label:'变更原因',width:240},{field:'status',label:'审批状态',width:100},{field:'created_at',label:'申请时间',width:155}]
const page=ref(1),pageSize=ref(DEFAULT_PAGE_SIZE),rows=ref<any[]>([]),total=ref(0),loading=ref(false),failed=ref(false)
const query=useSystemQuery(()=>columns.map(column=>({field:column.field,label:column.label,type:column.field==='status'?'enum':column.field==='created_at'?'date':'text',...(column.field==='status'?{options:enums.options('archive_change_status',true)}:{})} as QueryField)),['project_code','status'],{ready:()=>ready.value,requireQuery:true})
const {fields,defaults,draft,applied,columnContext,clearColumns}=query
const visibleRows=computed(()=>query.filterRows(rows.value))
const gridApi=ref<GridApi|null>(null),selectedColumns=ref(columns.map(column=>column.field))
const columnGroups=[{key:'change',label:'变更申请',fields:columns.map(column=>({key:column.field,label:column.label,value_type:'text',list_available:true,quick_addable:true}))}]
const sort=ref<Array<{colId:string;sort:'asc'|'desc'}>>([])
const selected=ref<any>(null),detailOpen=ref(false),opinion=ref(''),busy=ref(false),error=ref('')
let requestSerial=0
async function loadMetadata(){metaFailed.value=false;try{await enums.load();ready.value=true}catch{metaFailed.value=true}}
async function fetchRows(){const serial=++requestSerial;loading.value=true;failed.value=false;clearColumns();try{const result:any=await request.get('/projects/archive-changes',{params:{page:page.value,page_size:pageSize.value,sort:JSON.stringify(sort.value),filters:JSON.stringify(applied.value.map(condition=>({...condition,schemaVersion:2})))}});if(serial!==requestSerial)return;rows.value=result.items;total.value=result.total}catch{if(serial===requestSerial)failed.value=true}finally{if(serial===requestSerial)loading.value=false}}
async function runQuery(conditions:QueryCondition[]){query.submit(conditions);page.value=1;await fetchRows()}
async function guard(){if(busy.value)return false;if(!opinion.value.trim())return true;const decision=await confirmDetailSwitch();if(decision==='save'){ElMessage.info('请先通过或退回当前申请，再切换记录');return false}return decision==='discard'}
const detailSwitch=createDetailSwitch<any>(guard,async row=>{selected.value=row;opinion.value='';error.value=''})
async function openDetail(row:any){await detailSwitch.select(row);if(selected.value?.id===row.id)detailOpen.value=true}
async function onRowClick(row:any){if(detailOpen.value)await detailSwitch.select(row)}
async function closeDetail(done?:()=>void){if(await guard()){detailSwitch.invalidate();detailOpen.value=false;done?.()}}
async function decide(decision:'approve'|'reject'){if(!selected.value?.can_approve||busy.value)return;if(decision==='reject'&&!opinion.value.trim()){error.value='请填写退回原因';return}busy.value=true;try{const result:any=await request.post(`/projects/archive-changes/requests/${selected.value.id}/decide`,{decision,expected_version:selected.value.version,opinion:opinion.value});Object.assign(selected.value,result,{can_approve:false,can_withdraw:false});opinion.value='';error.value='';await fetchRows();emit('changed');ElMessage.success(decision==='approve'?'审批通过，正式档案已更新':'已退回，正式档案未改变')}catch{error.value='操作失败，意见已保留，请刷新核对后重试'}finally{busy.value=false}}
async function withdraw(row:any){if(!row.can_withdraw||busy.value)return;busy.value=true;try{await request.post(`/projects/archive-changes/requests/${row.id}/withdraw`,{expected_version:row.version});await fetchRows();emit('changed');ElMessage.success('已撤回，记录保留')}catch{/* Shared handler reports failure. */}finally{busy.value=false}}
const Actions=defineComponent({props:['params'],setup(props){return()=>h('div',{class:'archive-row-actions'},[
 h('button',{type:'button',class:'pms-table-action',style:{color:'var(--pms-info)'},onClick:(event:Event)=>{event.stopPropagation();openDetail(props.params.data)}},'查看'),
 props.params.data.can_withdraw?h('button',{type:'button',class:'pms-table-action',style:{color:'var(--pms-warning)'},disabled:busy.value,onClick:(event:Event)=>{event.stopPropagation();withdraw(props.params.data)}},'撤回'):null,
])}})
const Status=defineComponent({props:['params'],setup(props){return()=>h('span',{class:['pms-status',props.params.value===3?'pms-status-success':props.params.value===2?'pms-status-warning':'pms-status-neutral']},enums.label('archive_change_status',props.params.value))}})
const columnDefs=computed(()=>decorateQueryColumns<any>([...columns.map(column=>({field:column.field,headerName:column.label,initialWidth:column.width,hide:!selectedColumns.value.includes(column.field),cellRenderer:column.field==='status'?Status:undefined,valueFormatter:column.field==='status'?(params:any)=>enums.label('archive_change_status',params.value):undefined})),
 {colId:'archive_actions',headerName:'操作',...pmsActionColumn(2),pinned:'right' as const,lockPosition:'right' as const,lockVisible:true,suppressMovable:true,sortable:false,cellClass:'pms-actions-cell',cellRenderer:Actions}],()=>columnContext))
function gridReady(event:GridReadyEvent){gridApi.value=event.api}
function gridRowClicked(event:RowClickedEvent){onRowClick(event.data)}
async function sortChanged(){sort.value=(gridApi.value?.getColumnState()||[]).filter(state=>state.sort==='asc'||state.sort==='desc').map(state=>({colId:state.colId,sort:state.sort as 'asc'|'desc'}));page.value=1;await fetchRows()}
function exportSnapshot(){return businessExportSnapshot(applied.value,[],gridApi.value)}
onMounted(loadMetadata)
onBeforeUnmount(()=>{requestSerial++;detailSwitch.invalidate()})
</script>

<template>
 <PmsDataList scrollbar-label="档案变更表格横向滚动条">
  <template #toolbar-left><el-button type="primary" plain :icon="Back" :disabled="busy" @click="emit('back')">项目档案</el-button><strong>变更审批</strong></template>
  <template #toolbar-right><BusinessExportControl :resource="{kind:'archive_changes'}" :snapshot="exportSnapshot" :disabled="loading||failed||!query.submitted.value||!total"/><PmsListColumnPicker v-model="selectedColumns" :groups="columnGroups" :column-definitions="columnDefs" :default-keys="columns.map(column=>column.field)" :get-grid-api="()=>gridApi" aria-label="档案变更列设置"/><PmsPageGuide page="archiveChanges"/></template>
  <template #filters><PmsQueryWorkspace entry-mode="document" v-model="draft" list-key="archive-changes" :fields="fields" :defaults="defaults" :ready="ready" :loading="loading" @query="runQuery" @clear-columns="clearColumns"/></template>
  <template #grid>
   <div v-if="failed||metaFailed" class="pms-list-load-error" role="alert">加载失败，请重试 <el-button class="pms-button-auxiliary" @click="metaFailed?loadMetadata():fetchRows()">重试</el-button></div>
   <AgGridVue class="ag-theme-alpine pms-ag-grid" :row-data="visibleRows" :column-defs="columnDefs" :grid-options="PMS_GRID_OPTIONS" :locale-text="chineseLocaleText" :loading="loading" :default-col-def="{resizable:true,sortable:true,filter:false,comparator:()=>0}" :get-row-id="params=>String(params.data.id)" @grid-ready="gridReady" @sort-changed="sortChanged" @row-clicked="gridRowClicked"/>
  </template>
  <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" @update:model-value="fetchRows" @update:page-size="()=>{page=1;fetchRows()}"/></template>
  <el-dialog v-model="detailOpen" title="档案变更审批" width="min(760px,94vw)" :modal="false" modal-penetrable align-center :before-close="closeDetail" :show-close="!busy" :close-on-press-escape="!busy" :close-on-click-modal="false">
   <p>{{selected?.project_code}} · {{enums.label('archive_change_status',selected?.status)}}</p><p>{{selected?.reason}}</p>
   <el-table :data="selected?.differences||[]" border class="pms-dense-table"><el-table-column prop="field_label" label="字段" width="130"/><el-table-column prop="before_display" label="修改前"/><el-table-column prop="after_display" label="修改后"/></el-table>
   <PmsFormField v-if="selected?.can_approve" field-id="archive-review-opinion" label="审批意见" :error="error"><PmsTextareaControl id="archive-review-opinion" v-model="opinion" aria-label="审批意见" :rows="3" :maxlength="1024" :disabled="busy" placeholder="退回时必输"/></PmsFormField>
   <p v-else-if="selected?.opinion">审批意见：{{selected.opinion}}</p>
   <template #footer><el-button type="warning" plain :disabled="busy" @click="closeDetail()">关闭</el-button><template v-if="selected?.can_approve"><el-button type="danger" plain :disabled="busy" @click="decide('reject')">退回</el-button><el-button type="success" :loading="busy" @click="decide('approve')">通过</el-button></template></template>
  </el-dialog>
 </PmsDataList>
</template>
