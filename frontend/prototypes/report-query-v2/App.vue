<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { Search, RefreshLeft, Download, Setting, Document, Menu } from '@element-plus/icons-vue'
import { PmsTextControl, PmsSelectControl, PmsDateControl } from '@/form-system'
import PmsReportPlans from '@/report-query/PmsReportPlans.vue'
import PmsReportConditions from '@/report-query/PmsReportConditions.vue'
import PmsReportQuerySurface from '@/report-query/PmsReportQuerySurface.vue'
import { cloneQuery, operatorLabels, type ReportCondition, type ReportField } from '@/report-query/state'
const reports = [{id:'inventory',name:'即时库存查询'}, {id:'purchase',name:'采购进度查询'}, {id:'stock',name:'物料收发明细'}]
const active = ref('inventory'), queried = ref(false), collapsed = ref(false)
const plans = ref<InstanceType<typeof PmsReportPlans>>()
const title = computed(()=>reports.find(r=>r.id===active.value)!.name)
const draft = reactive({material:'',organizations:[] as number[],organization:null as number|null,project:'',supplier:'',stock:'',dates:['2026-09-01','2026-09-24'],conditions:[] as ReportCondition[]})
const required = computed(()=>active.value==='stock')
const invalid = computed(()=>required.value && (!draft.material.trim() || !draft.organizations.length))
const fields = computed<ReportField[]>(()=>[
  {field:'material',label:'物料名称',type:'text'},
  {field:'spec',label:'规格型号',type:'text'},
  {field:'quantity',label:active.value==='purchase'?'申请数量':'数量',type:'number'},
  ...(active.value==='inventory'?[]:[{field:'date',label:active.value==='purchase'?'申请日期':'日期',type:'date' as const}]),
  {field:'status',label:active.value==='inventory'?'库存状态':'单据状态',type:'enum',options:active.value==='inventory'?[{value:'available',label:'可用'},{value:'frozen',label:'冻结'}]:[{value:'approved',label:'已审核'},{value:'review',label:'审核中'}]},
  {field:'note',label:'备注',type:'text'},
  ...(active.value==='purchase'?[{field:'progress',label:'采购进度',type:'enum' as const,options:[{value:'pending',label:'未下单'},{value:'partial',label:'部分下单'},{value:'done',label:'已完成'}]}]:[]),
])
const columns = computed(()=> active.value==='inventory'?['组织','仓库','物料编码','物料名称','规格型号','品牌','材质','数量','单位']:active.value==='purchase'?['项目编号','物料编码','物料名称','申请单编号','申请日期','申请数量','累计下单数量','累计入库数量','采购进度']:['物料编码','物料名称','日期','单据名称','单据编号','仓库名称','期初','收入','发出','结存'])
function reset() { Object.assign(draft,{material:'',organizations:[],organization:null,project:'',supplier:'',stock:'',dates:['2026-09-01','2026-09-24'],conditions:[]}); queried.value=false; plans.value?.clearSelection() }
function select(id:string) { active.value=id; reset() }
function restore(value:any) { Object.assign(draft,cloneQuery(value)); queried.value=false }
function cell(col:string,i:number) {
  const values:Record<string,string> = {'组织':'8吋半导体','仓库':'研发仓','仓库名称':'研发仓','物料编码':`1801020200${45+i%3}`,'物料名称':i%2?'接头':'PFA管','规格型号':'1/2"','品牌':'标准件','材质':'PFA','单位':'米','项目编号':'L_B-202608','申请单编号':`CGSQ${30949-i}`,'申请日期':'2026-09-24','日期':'2026-09-24','单据名称':i%2?'生产领料单':'直接调拨单','单据编号':`DOC2600${18508-i}`,'采购进度':'部分下单','数量':'20.00','申请数量':'20.00','累计下单数量':'10.00','累计入库数量':'6.00','收入':i%2?'':'6.00','发出':i%2?'6.00':'','期初':'','结存':i%2?'':'6.00'}
  return values[col]||''
}
</script>
<template>
  <div class="preview-app" :class="{'is-collapsed':collapsed}">
    <aside><div class="preview-brand"><span>P</span><strong>PMS 管理系统</strong></div><div class="preview-nav-label">报表中心</div><button v-for="r in reports" :key="r.id" :class="{active:active===r.id}" @click="select(r.id)"><el-icon><Document /></el-icon><span>{{r.name}}</span></button></aside>
    <header class="preview-header"><button aria-label="折叠菜单" @click="collapsed=!collapsed"><el-icon><Menu /></el-icon></button><strong>{{title}}</strong><span>交互样稿 · 模拟数据</span></header>
    <main>
      <PmsReportQuerySurface>
        <div class="pms-report-query-toolbar">
          <PmsReportPlans ref="plans" :key="active" :storage-key="`pms:query-v2-prototype:${active}`" :snapshot="()=>cloneQuery(draft)" @restore="restore" />
          <div class="pms-report-query-tools"><span class="pms-report-query-status">{{queried?'已查询':'尚未查询'}}</span><el-button :icon="Download" disabled>导出当前筛选</el-button><el-button disabled>导出任务</el-button><el-button :icon="Setting" disabled>列设置</el-button></div>
        </div>
        <form class="pms-report-query-fields" @submit.prevent="!invalid && (queried=true)">
          <div class="query-material"><PmsTextControl v-model="draft.material" size="compact" clearable :prefix-icon="Search" :placeholder="required?'物料编码 / 名称 / 规格（必填）':'物料编码 / 名称 / 规格'" aria-label="物料" /></div>
          <PmsTextControl v-if="active==='purchase'" v-model="draft.project" size="compact" clearable placeholder="项目编号" aria-label="项目编号" />
          <PmsSelectControl v-else-if="required" v-model="draft.organizations" size="compact" multiple collapse-tags collapse-tags-tooltip clearable :options="[{value:1,label:'8吋半导体'},{value:2,label:'Single'}]" placeholder="库存组织（必选）" aria-label="库存组织" />
          <PmsSelectControl v-else v-model="draft.organization" size="compact" clearable :options="[{value:1,label:'8吋半导体'},{value:2,label:'Single'}]" placeholder="全部授权组织" aria-label="库存组织" />
          <div v-if="active!=='inventory'" class="query-dates"><PmsDateControl v-model="draft.dates" size="compact" type="daterange" start-placeholder="起始日期" end-placeholder="截止日期" aria-label="日期范围" /></div>
          <PmsTextControl v-if="active==='purchase'" v-model="draft.supplier" size="compact" clearable placeholder="供应商" aria-label="供应商" />
          <PmsSelectControl v-else v-model="draft.stock" size="compact" clearable filterable :options="[{value:'研发仓',label:'研发仓'},{value:'原料仓',label:'原料仓'}]" placeholder="全部仓库" aria-label="仓库" />
          <el-button type="primary" native-type="submit" :icon="Search" :disabled="invalid">查询</el-button><el-button :icon="RefreshLeft" @click="reset">重置</el-button>
          <PmsReportConditions v-model="draft.conditions" :fields="fields" trigger-label="添加条件" />
        </form>
      </PmsReportQuerySurface>
      <div v-if="draft.conditions.length" class="preview-applied"><span v-for="c in draft.conditions" :key="c.id">{{fields.find(f=>f.field===c.field)?.label}} {{operatorLabels[c.operator]}} {{fields.find(f=>f.field===c.field)?.options?.find(o=>o.value===c.value)?.label ?? c.value}}{{c.operator==='between'?` 至 ${c.valueEnd}`:''}}<button :aria-label="`移除${c.field}条件`" @click="draft.conditions=draft.conditions.filter(v=>v.id!==c.id)">×</button></span></div>
      <div class="preview-table"><table><thead><tr><th v-for="c in columns" :key="c">{{c}}</th></tr></thead><tbody v-if="queried"><tr v-for="i in 30" :key="i"><td v-for="c in columns" :key="c">{{cell(c,i)}}</td></tr></tbody></table><div v-if="!queried" class="preview-empty">设置条件后，点击查询</div></div>
      <footer><span>{{queried?'共 30 条':'未查询'}}</span><span>1</span><span>50 条/页</span></footer>
    </main>
  </div>
</template>
<style>
html,body,#app { margin:0; height:100%; }
.pms-report-condition-popper .el-button { height:32px; min-height:32px; font-size:13px; font-weight:400; }
.preview-app { height:100%; display:grid; grid-template-columns:188px minmax(0,1fr); grid-template-rows:56px minmax(0,1fr); background:var(--pms-bg); color:var(--pms-text-primary); font:13px var(--pms-font); }
.preview-app aside { grid-row:1/3; background:white; border-right:1px solid var(--pms-border-soft); }
.preview-brand { height:56px; display:flex; align-items:center; gap:10px; padding:0 16px; border-bottom:1px solid var(--pms-border-soft); }
.preview-brand>span { border:1px solid var(--pms-border); border-radius:6px; padding:6px 10px; color:var(--pms-primary); }
.preview-nav-label { padding:24px 16px 12px; color:var(--pms-text-muted); }
.preview-app aside button { display:flex; align-items:center; gap:10px; width:calc(100% - 16px); margin:4px 8px; padding:12px; border:0; background:none; text-align:left; font:inherit; color:var(--pms-text-secondary); border-radius:6px; cursor:pointer; }
.preview-app aside button.active { background:var(--pms-primary-soft,#eeecff); color:var(--pms-primary); }
.preview-header { background:white; display:flex; align-items:center; gap:16px; padding:0 20px; border-bottom:1px solid var(--pms-border-soft); }
.preview-header>button { border:0; background:none; color:var(--pms-text-secondary); cursor:pointer; }
.preview-header>span { margin-left:auto; color:var(--pms-text-muted); font-size:12px; }
.preview-app main { margin:16px; padding:16px; background:white; border:1px solid var(--pms-border-soft); border-radius:8px; display:flex; flex-direction:column; min-width:0; min-height:0; }
.preview-table { position:relative; flex:1; min-height:0; overflow:auto; border:1px solid var(--pms-border-soft); border-radius:6px; }
.preview-table table { width:100%; border-collapse:collapse; table-layout:fixed; min-width:1050px; }
.preview-table th { background:#f7f8fb; height:36px; color:var(--pms-text-secondary); text-align:left; padding:0 12px; border-bottom:1px solid var(--pms-border); font-weight:500; position:sticky; top:0; }
.preview-table td { height:36px; padding:0 12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; border-bottom:1px solid var(--pms-border-soft); }
.preview-table tr:nth-child(even) { background:#fafbfd; }
.preview-empty { position:sticky; left:0; top:45%; width:100%; text-align:center; color:var(--pms-text-muted); }
.preview-app footer { display:flex; justify-content:space-between; padding-top:12px; color:var(--pms-text-secondary); }
.preview-applied { display:flex; gap:8px; flex-wrap:wrap; padding-bottom:8px; }
.preview-applied>span { padding:4px 8px; border:1px solid var(--pms-border-soft); border-radius:4px; }
.preview-applied button { border:0; background:none; color:var(--pms-text-muted); cursor:pointer; }
.preview-app.is-collapsed { grid-template-columns:52px minmax(0,1fr); }
.preview-app.is-collapsed aside strong,.preview-app.is-collapsed aside button span,.preview-app.is-collapsed .preview-nav-label { display:none; }
.preview-app.is-collapsed .preview-brand { padding:8px; }
@media(max-width:700px) { .preview-app { grid-template-columns:1fr; } .preview-app aside { display:none; } .preview-app main { margin:8px; padding:10px; } }
</style>
