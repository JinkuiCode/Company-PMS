<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Download, DataAnalysis } from '@element-plus/icons-vue'
import { AgGridVue } from 'ag-grid-vue3'
import { AllCommunityModule, ModuleRegistry, type ColDef, type GridApi, type ColumnState } from 'ag-grid-community'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-alpine.css'
import PmsDataList from '@/components/PmsDataList.vue'
import CustomPagination from '@/components/CustomPagination.vue'
import PmsListColumnPicker from '@/components/PmsListColumnPicker.vue'
import PmsQueryWorkspace from '@/query-system/PmsQueryWorkspace.vue'
import { useSystemQuery, serverQueryParams } from '@/query-system/system-adapter'
import { usePageColumnFilter } from '@/query-system/page-column-filter'
import { decorateQueryColumns } from '@/query-system/column-grid'
import type { ColumnQueryContext } from '@/query-system/column-filters'
import { cloneQuery, hasConditionValue, type QueryField, type QueryCondition } from '@/query-system/core'
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS, PMS_GRID_OPTIONS } from '@/config/listUi'
import { chineseLocaleText } from '@/utils/agGridLocale'
import { createDetailSwitch } from '@/utils/detailSwitch'
import { useAuthStore } from '@/stores/auth'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { feedbackEnumCodes, categoryCode, mailLabels, feedbackTone, type FeedbackMode } from '@/feedback/model'
import { getFeedbackList, getFeedbackStats, getFeedback, exportFeedback, type FeedbackRow } from '@/api/feedback'
import FeedbackDetail from './FeedbackDetail.vue'
import FeedbackForm from './FeedbackForm.vue'

ModuleRegistry.registerModules([AllCommunityModule])
const auth=useAuthStore(), enums=useEnumOptions(feedbackEnumCodes)
const options=(code:string)=>enums.options(code,true), label=enums.label
const rows=ref<FeedbackRow[]>([]), total=ref(0), page=ref(1), pageSize=ref(DEFAULT_PAGE_SIZE)
const mine=ref(false), status=ref<number|null>(null), stats=ref<any>({total:0,open:0,completed:0,statuses:{},modules:[],categories:[]})
const loading=ref(false), failed=ref(false), ready=ref(false), exporting=ref(false), statsOpen=ref(false)
const detailOpen=ref(false), detail=ref<FeedbackRow|null>(null), detailLoading=ref(false), detailError=ref('')
const formOpen=ref(false), mode=ref<FeedbackMode>('new'), form=ref<InstanceType<typeof FeedbackForm>>()
const list=ref<InstanceType<typeof PmsDataList>>(), visible=ref<string[]>([])
const sort=ref<{colId:string;sort:'asc'|'desc'}[]>([])
let grid:GridApi<FeedbackRow>|null=null, sequence=0, statsSequence=0, active=true, restoring=false
const enumFields:Record<string,string>={type_id:'feedback_type',module_id:'feedback_module',impact_id:'feedback_impact',status_id:'feedback_status'}
const fields=computed<QueryField[]>(()=>[
 {field:'report_no',label:'提报编号',type:'text'}, {field:'title',label:'标题',type:'text'},
 ...Object.entries(enumFields).map(([field,code])=>({field,label:({type_id:'提报类型',module_id:'涉及模块',impact_id:'影响程度',status_id:'处理状态'} as Record<string,string>)[field]!,type:'enum' as const,options:options(code)})),
 {field:'category_name',label:'具体类别',type:'enum',options:[...new Set([...options('feedback_issue_category'),...options('feedback_request_category')].map(item=>item.label))].map(value=>({value,label:value}))},
 {field:'author_name',label:'提报人',type:'text'}, {field:'handler_name',label:'处理人',type:'text'},
 {field:'created_at',label:'提报时间',type:'date'}, {field:'updated_at',label:'更新时间',type:'date'},
 {field:'mail_status',label:'邮件通知',type:'enum',options:Object.entries(mailLabels).map(([value,label])=>({value,label}))},
])
const query=useSystemQuery(()=>fields.value,['title','type_id','module_id','status_id'])
const {draft:queryDraft,defaults:queryDefaults}=query
const columnsPage=usePageColumnFilter(rows,()=>fields.value,query.columnFilters,()=>[page.value,pageSize.value],undefined,()=>ready.value&&!loading.value&&!failed.value)
const visibleRows=columnsPage.visibleRows
const columnContext=():ColumnQueryContext=>({...columnsPage.context,sort:(field,direction)=>{if(loading.value)return;sort.value=[{colId:field,sort:direction}];restoring=true;grid?.applyColumnState({state:sort.value,defaultState:{sort:null}});restoring=false;page.value=1;saveColumns();void load()}})
const defaultKeys=['report_no','title','type_id','module_id','category_name','impact_id','status_id','author_name','handler_name','created_at','mail_status','updated_at']
const groups=computed(()=>[{key:'feedback',label:'问题提报',fields:fields.value.map(field=>({key:field.field,label:field.label,value_type:field.type,list_available:true,quick_addable:true}))}])
const storageKey=computed(()=>`pms:feedback:columns:v1:${auth.user?.id}`)
let savedColumns:ColumnState[]=[]
function display(row:FeedbackRow|undefined,key:string){if(!row)return '';const value=(row as any)[key];return enumFields[key]?label(enumFields[key]!,value):key==='mail_status'?mailLabels[value]||'':key.endsWith('_at')?String(value||'').replace('T',' ').slice(0,16):String(value??'')}
const columns=computed<ColDef<FeedbackRow>[]>(()=>decorateQueryColumns<FeedbackRow>([
 ...defaultKeys.map(key=>({field:key as keyof FeedbackRow,colId:key,headerName:fields.value.find(f=>f.field===key)?.label,initialWidth:key==='title'?240:key.endsWith('_at')?150:128,minWidth:90,hide:!visible.value.includes(key),valueFormatter:(p:any)=>display(p.data,key),tooltipValueGetter:(p:any)=>display(p.data,key),cellRenderer:key==='status_id'||key==='mail_status'?(p:any)=>{const span=document.createElement('span');span.className='pms-status pms-status-'+feedbackTone(p.value);span.textContent=display(p.data,key);return span}:undefined})),
 {colId:'feedback_actions',headerName:'操作',initialWidth:72,minWidth:72,initialPinned:'right',sortable:false,cellRenderer:(p:any)=>{const button=document.createElement('button');button.type='button';button.className='feedback-view';button.textContent='查看';button.addEventListener('click',()=>void openDetail(p.data));return button}},
],columnContext) as ColDef<FeedbackRow>[])
const defaultColDef:ColDef={resizable:true,sortable:true,editable:false,comparator:()=>0,cellStyle:{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}
function saveColumns(){if(restoring||!grid)return;try{localStorage.setItem(storageKey.value,JSON.stringify({visible:visible.value,columns:grid.getColumnState()}))}catch{ElMessage.warning('列设置保存失败')}void nextTick(()=>list.value?.refreshScrollbar())}
function gridReady(event:any){grid=event.api;restoring=true;grid!.applyColumnState({state:savedColumns,applyOrder:true});restoring=false;list.value?.refreshScrollbar()}
function sorted(event:any){if(restoring||event.source==='api'||event.source==='gridInitializing')return;sort.value=(grid?.getColumnState().filter(c=>c.sort).map(c=>({colId:c.colId,sort:c.sort!}))||[]);page.value=1;saveColumns();void load()}
const params=()=>({...serverQueryParams(query.applied.value.filter(hasConditionValue),[]),mine:mine.value,status_id:status.value??undefined,sort:JSON.stringify(sort.value)})
async function load(){if(!ready.value)return;columnsPage.clear();const ticket=++sequence;loading.value=true;failed.value=false;try{const data=await getFeedbackList({...params(),page:page.value,page_size:pageSize.value});if(!active||ticket!==sequence)return;rows.value=data.items;total.value=data.total;list.value?.refreshScrollbar()}catch{if(ticket===sequence){failed.value=true;rows.value=[]}}finally{if(ticket===sequence)loading.value=false}}
async function loadStats(){const ticket=++statsSequence;try{const data=await getFeedbackStats(mine.value);if(active&&ticket===statsSequence)stats.value=data}catch{if(active&&ticket===statsSequence)ElMessage.warning('统计读取失败，请刷新重试')}}
async function runQuery(conditions:QueryCondition[],preferences:object){query.submit(conditions);const size=(preferences as any).pageSize;if(PAGE_SIZE_OPTIONS.includes(size))pageSize.value=size;page.value=1;await load()}
async function scope(value:boolean){if(mine.value===value)return;mine.value=value;page.value=1;status.value=null;await Promise.all([load(),loadStats()])}
function quick(value:number|null){status.value=value;page.value=1;void load()}
const formGuards=ref(0)
async function guard(){if(!formOpen.value)return true;formGuards.value++;try{return !!await form.value?.guard()}finally{formGuards.value--}}
const selectedRow=ref<FeedbackRow|null>(null)
const switchDetail=createDetailSwitch<FeedbackRow>(guard,async(row,current)=>{formOpen.value=false;detailOpen.value=true;selectedRow.value=row;detailLoading.value=true;detailError.value='';detail.value=null;try{const result=await getFeedback(row.id);if(current()&&active)detail.value=result}catch{if(current()&&active)detailError.value='详情读取失败，请重试'}finally{if(current()&&active)detailLoading.value=false}})
async function openDetail(row:FeedbackRow){await switchDetail.select(row)}
function rowClicked(event:any){if((detailOpen.value||formOpen.value)&&event.data)void switchDetail.select(event.data)}
async function add(){if(!await guard())return;switchDetail.invalidate();detailOpen.value=false;detail.value=null;mode.value='new';formOpen.value=true}
function edit(value:'handle'|'supplement'){if(!detail.value)return;detailOpen.value=false;mode.value=value;formOpen.value=true}
async function saved(row:FeedbackRow){detail.value=row;await Promise.all([load(),loadStats()])}
async function formClosed(value:boolean){const wasOpen=formOpen.value;formOpen.value=value;if(wasOpen&&!value&&detail.value&&!formGuards.value){detailOpen.value=true;await switchDetail.select(detail.value)}}
async function refreshDetail(){if(selectedRow.value)await switchDetail.select(selectedRow.value)}
async function download(){exporting.value=true;try{await exportFeedback(params());ElMessage.success('提报与跟进记录已导出')}catch{ElMessage.error('导出失败，请重试')}finally{exporting.value=false}}
watch([page,pageSize],()=>{void load()})
watch(()=>auth.hasPermission('feedback:handle'),allowed=>{if(!allowed){mine.value=true;detailOpen.value=false;formOpen.value=false;detail.value=null;switchDetail.invalidate();void load();void loadStats()}},{flush:'sync'})
onBeforeRouteLeave(guard)
onUnmounted(()=>{active=false;++sequence;++statsSequence;switchDetail.invalidate();columnsPage.clear()})
onMounted(async()=>{visible.value=defaultKeys.filter(key=>key!=='updated_at');try{const prefs=JSON.parse(localStorage.getItem(storageKey.value)||'{}');if(Array.isArray(prefs.visible))visible.value=prefs.visible.filter((key:string)=>defaultKeys.includes(key));if(Array.isArray(prefs.columns))savedColumns=prefs.columns.filter((c:any)=>defaultKeys.includes(c.colId)||c.colId==='feedback_actions').map((c:any)=>({...c,sort:null}))}catch{savedColumns=[]}mine.value=!auth.hasPermission('feedback:handle');try{await enums.load();await nextTick();ready.value=true;query.applied.value=cloneQuery(queryDraft.value);await Promise.all([load(),loadStats()])}catch{failed.value=true}})
</script>
<template>
 <PmsDataList ref="list" class="feedback-list">
  <template #toolbar-left><el-button v-if="auth.hasPermission('feedback:add')" type="primary" size="small" :icon="Plus" @click="add">新增提报</el-button><div v-if="auth.hasPermission('feedback:handle')" class="feedback-scope"><el-button size="small" :type="!mine?'primary':undefined" :plain="mine" @click="scope(false)">全部提报</el-button><el-button size="small" :type="mine?'primary':undefined" :plain="!mine" @click="scope(true)">我的提报</el-button></div></template>
  <template #toolbar-right><span class="feedback-summary">{{stats.total}} 条提报 · 问题 {{stats.issues||0}} · 需求 {{stats.requests||0}} · 未完成 {{stats.open}} · 已完成 {{stats.completed}}</span><el-button size="small" class="pms-button-auxiliary" :icon="DataAnalysis" @click="statsOpen=true">分类统计</el-button><el-button v-if="auth.hasPermission('feedback:export')" size="small" type="success" plain :icon="Download" :loading="exporting" :disabled="!ready||loading||failed" @click="download">导出数据</el-button><PmsListColumnPicker v-model="visible" :groups="groups" :default-keys="defaultKeys" :column-definitions="columns" :get-grid-api="()=>grid" @layout-changed="saveColumns" /></template>
  <template #filters><PmsQueryWorkspace v-model="queryDraft" list-key="feedback" :fields="fields" :defaults="queryDefaults" :loading="loading||!ready" :snapshot="()=>({pageSize})" @query="runQuery" @clear-columns="columnsPage.clear" /><div class="feedback-status-tabs"><button :class="{active:status===null}" @click="quick(null)">全部状态</button><button :class="{active:status===0}" @click="quick(0)">未完成 <span>{{stats.open}}</span></button><button v-for="option in options('feedback_status')" :key="option.value" :class="{active:status===option.value}" @click="quick(Number(option.value))">{{option.label}} <span>{{stats.statuses[String(option.value)]||0}}</span></button></div><div v-if="failed" class="feedback-error" role="alert">提报读取失败 <el-button link type="primary" @click="load">重试</el-button></div></template>
  <template #grid><div v-loading="loading" class="feedback-grid"><AgGridVue class="ag-theme-alpine pms-ag-grid" theme="legacy" :row-data="visibleRows" :column-defs="columns" :default-col-def="defaultColDef" :grid-options="PMS_GRID_OPTIONS" :locale-text="chineseLocaleText" :get-row-id="(p:any)=>String(p.data.id)" @grid-ready="gridReady" @row-clicked="rowClicked" @sort-changed="sorted" @column-resized="(e:any)=>{if(e.finished)saveColumns()}" /></div></template>
  <template #pagination><CustomPagination v-model="page" v-model:page-size="pageSize" :total="total" /></template>
 </PmsDataList>
 <FeedbackDetail v-model="detailOpen" :row="detail" :loading="detailLoading" :error="detailError" :label="label" @edit="edit" @refresh="refreshDetail" />
 <FeedbackForm ref="form" :model-value="formOpen" :mode="mode" :row="detail" :options="options" @update:model-value="formClosed" @saved="saved" />
 <el-dialog v-model="statsOpen" title="分类统计" width="min(820px,calc(100vw - 24px))"><p class="feedback-summary">按当前可见范围统计，不受临时查询条件和本页列筛选影响</p><el-table :data="stats.modules" class="pms-dense-table"><el-table-column label="涉及模块" min-width="140"><template #default="{row}">{{label('feedback_module',row.module_id)}}</template></el-table-column><el-table-column v-for="column in [{key:'issues',label:'问题'},{key:'requests',label:'需求'},{key:'open',label:'未完成'},{key:'completed',label:'已完成'}]" :key="column.key" :prop="column.key" :label="column.label" align="right" header-align="center" /></el-table><section class="feedback-categories"><h3>具体类别</h3><div v-for="item in stats.categories" :key="item.type_id+'-'+item.category_id"><span>{{label('feedback_type',item.type_id)}} · {{label(categoryCode(item.type_id),item.category_id)}}</span><meter min="0" :max="stats.total||1" :value="item.count" /><strong>{{item.count}}</strong></div></section></el-dialog>
</template>
<style scoped>
.feedback-grid,.feedback-grid .ag-grid-vue,.feedback-grid .ag-theme-alpine{width:100%;height:100%;min-height:0}.feedback-summary{font-size:12px;color:var(--pms-text-secondary)}.feedback-scope{display:flex;align-items:center;gap:0}.feedback-scope .el-button+.el-button{margin-left:0}.feedback-status-tabs{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:4px 0 0;border-bottom:1px solid var(--pms-border-soft)}.feedback-status-tabs button{border:0;border-bottom:2px solid transparent;background:transparent;padding:4px 0;color:var(--pms-text-secondary);font:inherit;font-size:12px;cursor:pointer}.feedback-status-tabs button.active{color:var(--pms-primary);border-bottom-color:var(--pms-primary)}.feedback-status-tabs span{font-variant-numeric:tabular-nums}.feedback-error{color:var(--pms-danger)}.feedback-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.feedback-stats h3{font-size:13px}.feedback-stats section>div{display:flex;justify-content:space-between;border-bottom:1px solid var(--pms-border-soft);padding:8px 0;gap:8px}.feedback-stats span{overflow-wrap:anywhere}@media(max-width:600px){.feedback-stats{grid-template-columns:1fr}.feedback-summary{display:none}}
</style>
<style>.feedback-view{border:0;background:transparent;color:var(--pms-primary);font:inherit;cursor:pointer;padding:0 6px}.feedback-categories h3{font-size:13px;margin:16px 0 8px}.feedback-categories>div{display:grid;grid-template-columns:minmax(0,1fr) 120px 32px;gap:12px;align-items:center;padding:6px 0;border-bottom:1px solid var(--pms-border-soft)}.feedback-categories meter{width:100%;accent-color:var(--pms-primary)}.feedback-categories strong{text-align:right;font-variant-numeric:tabular-nums}</style>
